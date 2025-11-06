#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import argparse
from typing import List, Dict, Any, Optional, Iterable

from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from google import genai
from pypdf import PdfReader  # pip install pypdf

# ============= Config (override by CLI) =============
MODEL_NAME         = "models/gemini-2.5-flash-lite"
OUTPUT_JSONL       = "qa_results_batch.jsonl"
PDF_ROOT           = "data"                 # where your PDFs live
MAX_CONTEXT_CHARS  = 32_000                 # keep prompt safe for flash-lite
TEMPERATURE        = 0.4                    # a bit creative, still grounded
POLL_SECS          = 20                     # batch polling interval
DISPLAY_NAME       = "topic-qa-batch"

# ======== Schemas ========
class TopicQA(BaseModel):
    question: str = Field(description="繁體中文問題")
    answer:   str = Field(description="繁體中文答案")
    evidence: str = Field(description="來源頁碼與 1–2 句短引文", default="")

class DocumentTopic(BaseModel):
    topic_title: str
    topic_summary: str
    starting_page_number: int
    ending_page_number: int

class OutlineRecord(BaseModel):
    filename: str
    document_title: str
    main_topics: List[DocumentTopic]

# ===================== Utilities =====================
def iter_jsonls(paths: List[str]) -> Iterable[Dict[str, Any]]:
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

def safe_load_outline(rec: Dict[str, Any]) -> Optional[OutlineRecord]:
    if "error" in rec:
        return None
    try:
        return TypeAdapter(OutlineRecord).validate_python(rec)
    except ValidationError:
        if {"filename", "document_title", "main_topics"} <= set(rec.keys()):
            try:
                topics = [DocumentTopic(**t) for t in rec["main_topics"]]
                return OutlineRecord(
                    filename=rec["filename"],
                    document_title=rec.get("document_title", ""),
                    main_topics=topics,
                )
            except Exception:
                return None
        return None

def extract_topic_text(pdf_path: str, start_page: int, end_page: int) -> str:
    """
    Extract plain text from 1-indexed [start_page, end_page] inclusive.
    Falls back to empty string if anything fails.
    """
    try:
        reader = PdfReader(pdf_path)
        start = max(1, start_page)
        end   = min(len(reader.pages), end_page)
        if end < start:
            return ""
        parts = []
        for i in range(start-1, end):
            try:
                parts.append(reader.pages[i].extract_text() or "")
            except Exception:
                parts.append("")
        return "\n".join(parts).strip()
    except Exception:
        return ""

def estimate_num_qas(topic_text: str, min_q=3, max_q=10) -> int:
    # ~1 QA per 500 Han chars, bounded
    n = max(min_q, min(max_q, len(topic_text) // 500))
    return n

def clamp(text: str, n: int) -> str:
    return text[:n]

# ================== Batch builder ==================
def build_inline_requests(
    outlines: List[OutlineRecord],
    pdf_root: str,
    max_context_chars: int,
    base_temperature: float,
    nqa_override: Optional[int],
) -> List[dict]:
    """Build inline GenerateContentRequest dicts; one per topic."""
    sys_instr = (
        "你是一位文件內容分析助教，請仔細閱讀提供的主題正文內容，"
        "根據其中的具體敘述與關鍵觀念，產生繁體中文的高品質問答。"
        "所有答案必須能在正文中找到明確依據，並於 evidence 欄中列出對應頁碼與 1 至 2 句短引文。"
        "請忽略前言、序言、目錄與致謝等導言內容。"
        "輸出為 JSON 陣列，每個元素含 question、answer、evidence 三個欄位，不可添加任何額外說明。"
    )

    reqs = []
    for rec in outlines:
        pdf_path = os.path.join(pdf_root, rec.filename)
        for idx, t in enumerate(rec.main_topics):
            # Extract topic text; fallback to summary
            topic_text = ""
            if os.path.exists(pdf_path):
                topic_text = extract_topic_text(pdf_path, t.starting_page_number, t.ending_page_number)
            if not topic_text:
                topic_text = t.topic_summary or ""

            topic_text = clamp(topic_text, max_context_chars)

            # decide QA count (adaptive by content length, but overridable)
            n_q = nqa_override if (nqa_override and nqa_override > 0) else estimate_num_qas(topic_text)

            user_text = (
                f"【文件標題】{rec.document_title}\n"
                f"【檔名】{rec.filename}\n"
                f"【主題】{t.topic_title}\n"
                f"【頁碼範圍】{t.starting_page_number}-{t.ending_page_number}\n\n"
                f"【主題摘要】\n{t.topic_summary}\n\n"
                f"【主題正文文本】（僅能根據此內容回答）\n"
                f"{topic_text}\n\n"
                f"任務：請產生 {n_q} 組高品質問答（繁體中文）。答案必須能在正文中找到依據，"
                f"並於 evidence 欄中列出對應頁碼與 1~2 句短引文。"
            )

            reqs.append({
                "contents": [{
                    "role": "user",
                    "parts": [{"text": user_text}],
                }],
                "config": {
                    "system_instruction": {"parts": [{"text": sys_instr}]},
                    "response_mime_type": "application/json",
                    # If your SDK supports it well, you can uncomment next line:
                    # "response_schema": List[TopicQA],
                    "temperature": float(base_temperature),
                },
                "metadata": {
                    # unique key for mapping back
                    "key": f"{rec.filename}::#{idx}::{t.topic_title[:60]}"
                },
            })
    return reqs

from dotenv import load_dotenv
# ================== Batch runner ==================
def run_batch_qa(
    outline_jsonls: List[str],
    pdf_root: str = PDF_ROOT,
    output_jsonl: str = OUTPUT_JSONL,
    model_name: str = MODEL_NAME,
    max_context_chars: int = MAX_CONTEXT_CHARS,
    temperature: float = TEMPERATURE,
    nqa: Optional[int] = None,
    display_name: str = DISPLAY_NAME,
    poll_secs: int = POLL_SECS,
):
    load_dotenv()  # Load .env if exists
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    # Load outlines
    outlines: List[OutlineRecord] = []
    for rec in iter_jsonls(outline_jsonls):
        orc = safe_load_outline(rec)
        if orc:
            outlines.append(orc)

    if not outlines:
        print("No valid outline records found. Exiting.")
        return

    # Build inline requests (one per topic)
    requests = build_inline_requests(
        outlines=outlines,
        pdf_root=pdf_root,
        max_context_chars=max_context_chars,
        base_temperature=temperature,
        nqa_override=nqa,
    )

    print(f"Submitting Batch with {len(requests)} topic requests...")
    job = client.batches.create(
        model=model_name,
        src=requests,
        config={"display_name": display_name},
    )
    print(f" -> Job: {job.name}")

    # Poll to completion
    terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
    while True:
        job = client.batches.get(name=job.name)
        state = getattr(job.state, "name", str(job.state))
        print(f"   state: {state}")
        if state in terminal:
            break
        time.sleep(poll_secs)

    if getattr(job.state, "name", "") != "JOB_STATE_SUCCEEDED":
        print(f"Batch ended with state: {getattr(job.state, 'name', job.state)}")
        return

    # Parse results
    inlined = getattr(job.dest, "inlined_responses", []) or []
    adapter = TypeAdapter(List[TopicQA])

    with open(output_jsonl, "w", encoding="utf-8") as outf:
        for resp in inlined:
            meta_key = getattr(resp, "metadata", {}).get("key", "")
            if getattr(resp, "error", None):
                outf.write(json.dumps({"key": meta_key, "error": str(resp.error)}, ensure_ascii=False) + "\n")
                continue

            payload = None
            # Try text first
            try:
                payload = json.loads(resp.response.text)
            except Exception:
                try:
                    parts = resp.response.candidates[0].content.parts
                    for p in parts:
                        if hasattr(p, "text"):
                            try:
                                payload = json.loads(p.text)
                                break
                            except Exception:
                                continue
                except Exception:
                    pass

            if payload is None:
                outf.write(json.dumps({"key": meta_key, "error": "no_json"}, ensure_ascii=False) + "\n")
                continue

            try:
                qas = adapter.validate_python(payload)
                rec = {"key": meta_key, "qas": [q.model_dump() for q in qas]}
            except Exception as e:
                rec = {"key": meta_key, "error": f"parse_error: {e}", "raw": payload}

            outf.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"✅ Wrote {output_jsonl}")

# ================== CLI ==================
def main():
    ap = argparse.ArgumentParser(description="Batch QA generation (evidence-based) from outline JSONLs")
    ap.add_argument("--outline", "-i", nargs="+", required=True,
                    help="One or more Stage-1 outline JSONL files")
    ap.add_argument("--pdf_root", default=PDF_ROOT, help="Directory where PDFs are stored")
    ap.add_argument("--out", default=OUTPUT_JSONL, help="Output QA JSONL path")
    ap.add_argument("--model", default=MODEL_NAME, help="Gemini model id")
    ap.add_argument("--max_chars", type=int, default=MAX_CONTEXT_CHARS, help="Max chars per topic context")
    ap.add_argument("--temp", type=float, default=TEMPERATURE, help="Temperature for QA generation")
    ap.add_argument("--nqa", type=int, default=None, help="Override QA count per topic (otherwise adaptive)")
    ap.add_argument("--name", default=DISPLAY_NAME, help="Batch display name")
    ap.add_argument("--poll", type=int, default=POLL_SECS, help="Polling interval seconds")
    args = ap.parse_args()

    run_batch_qa(
        outline_jsonls=args.outline,
        pdf_root=args.pdf_root,
        output_jsonl=args.out,
        model_name=args.model,
        max_context_chars=args.max_chars,
        temperature=args.temp,
        nqa=args.nqa,
        display_name=args.name,
        poll_secs=args.poll,
    )

if __name__ == "__main__":
    main()

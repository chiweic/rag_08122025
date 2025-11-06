#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple

from pydantic import BaseModel, Field, TypeAdapter, ValidationError
from google import genai

# ---------- config ----------
OUTLINE_JSONL        = "fgqj_chap4_outline_results.jsonl"   # ← Stage 1 output
QA_JSONL             = "fgqj_chap4_qa_results_with_refs.jsonl"    # ← This script's output
MODEL_NAME           = "models/gemini-2.5-flash-lite"
N_QA_PER_TOPIC       = 5
TEMPERATURE          = 0.4
MAX_RETRIES          = 3
RETRY_SLEEP_S        = 3
MAX_CONTEXT_CHARS    = 32_000   # keep prompt light; adjust up/down as you like

# Where to find PDFs (keys in outline are original filenames)
PDF_BASE_DIR         = "data"      # if outline has relative paths like "data/xxx.pdf", keep "."

# ---------- models ----------
class TopicQA(BaseModel):
    question: str
    answer: str
    evidence: List[Dict[str, Any]]  # e.g., [{"page": 12, "quote": "..."}, ...]

class DocumentTopic(BaseModel):
    topic_title: str
    topic_summary: str
    starting_page_number: int
    ending_page_number: int

class OutlineRecord(BaseModel):
    filename: str
    document_title: str
    main_topics: List[DocumentTopic]

# ---------- utils ----------
def iter_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def clamp(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    # try to cut at paragraph boundary
    cut = s.rfind("\n\n", 0, limit)
    if cut < 0:
        cut = limit
    return s[:cut]

def estimate_num_qas(topic_text: str) -> int:
    n_chars = len(topic_text)
    # ~1 QA per 300–500 Chinese characters, bounded between 3 and 10
    return max(3, min(10, n_chars // 400))

# ---------- PDF text extraction (PyMuPDF) ----------
def extract_text_from_pdf(
    pdf_path: str, start_page_1based: int, end_page_1based: int
) -> Tuple[str, List[int]]:
    """
    returns (text, page_index_list) for the inclusive 1-based range.
    page_index_list is the actual 1-based pages we read (for sanity logs).
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise RuntimeError(
            "PyMuPDF not installed. Please `pip install pymupdf`."
        ) from e

    # 
    #if not os.path.isabs(pdf_path):
    #    pdf_path = os.path.join(PDF_BASE_DIR, pdf_path)

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(pdf_path)

    start_i = max(1, start_page_1based)
    end_i   = max(start_i, end_page_1based)

    txt_chunks: List[str] = []
    with fitz.open(pdf_path) as doc:
        total = len(doc)
        start_i = min(start_i, total)
        end_i   = min(end_i, total)
        for p in range(start_i - 1, end_i):
            page = doc[p]
            # 'text' gives layout-aware lines; 'textpage.extractTEXT()' similar
            txt = page.get_text("text") or ""
            txt_chunks.append(txt)

    text = "\n".join(txt_chunks)
    return text, list(range(start_i, end_i + 1))

# ---------- LLM call ----------
def generate_qas_for_topic(
    client: genai.Client,
    document_title: str,
    filename: str,
    topic: DocumentTopic,
    topic_text: str,
    n_pairs: int = N_QA_PER_TOPIC,
    model_name: str = MODEL_NAME,
    temperature: float = TEMPERATURE,
) -> List[TopicQA]:

    system_instruction = (
        "你是一位嚴謹的知識助教。根據提供的『主題正文文本』產生與其高度相關的問答組。"
        "請務必以繁體中文撰寫、嚴格根據文本內容作答，不要臆測或引入外部資訊。"
        "每組問答需提供至少一則證據（包含頁碼與短句式引文），頁碼請使用提供的原始 PDF 頁碼。"
        "輸出為 JSON 陣列，每個元素包含 question, answer, evidence；"
        "evidence 為陣列，每個物件包含 page 與 quote（不超過 200 字）。"
        "不要輸出任何 JSON 以外的文字。"
    )

    prompt = (
        f"【文件標題】{document_title}\n"
        f"【檔名】{filename}\n"
        f"【主題】{topic.topic_title}\n"
        f"【頁碼範圍】{topic.starting_page_number}-{topic.ending_page_number}\n\n"
        f"【主題摘要】\n{topic.topic_summary}\n\n"
        f"【主題正文文本】（僅能根據此內容回答）\n"
        f"{clamp(topic_text, MAX_CONTEXT_CHARS)}\n\n"
        f"任務：請產生 {n_pairs} 組高品質問答（繁體中文）。答案必須能在正文中找到依據，"
        f"並於 evidence 中列出對應頁碼與 1~2 句短引文。"
    )

    last_err: Optional[Exception] = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = client.models.generate_content(
                model=model_name,
                contents=[{"role": "user", "parts": [{"text": prompt}]}],
                config={
                    "system_instruction": {"parts": [{"text": system_instruction}]},
                    "response_mime_type": "application/json",
                    "temperature": float(temperature),
                },
            )
            payload = None
            try:
                payload = json.loads(resp.text)
            except Exception:
                try:
                    parts = resp.candidates[0].content.parts
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
                raise ValueError("回覆中找不到可解析的 JSON。")

            adapter = TypeAdapter(List[TopicQA])
            qas: List[TopicQA] = adapter.validate_python(payload)
            return qas

        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_SLEEP_S)
            else:
                raise

    if last_err:
        raise last_err
    return []

from dotenv import load_dotenv
# ---------- main ----------
def main():
    load_dotenv()
    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    with open(QA_JSONL, "w", encoding="utf-8") as out_f:
        for rec in iter_jsonl(OUTLINE_JSONL):
            # skip error rows
            if "error" in rec:
                continue

            # tolerate slightly different shapes
            try:
                outline = TypeAdapter(OutlineRecord).validate_python(rec)
            except ValidationError:
                if "filename" in rec and "main_topics" in rec:
                    outline = OutlineRecord(
                        filename=rec["filename"],
                        document_title=rec.get("document_title", ""),
                        main_topics=[DocumentTopic(**t) for t in rec.get("main_topics", [])],
                    )
                else:
                    continue

            # locate the pdf – outline.filename may be relative/pathlike already
            pdf_path = outline.filename
            if not os.path.isabs(pdf_path) and not os.path.exists(pdf_path):
                # try prefix base dir if the filename is relative like "data/xxx.pdf"
                candidate = os.path.join(PDF_BASE_DIR, pdf_path)
                if os.path.exists(candidate):
                    pdf_path = candidate

            for topic in outline.main_topics:
                try:
                    
                    # extract topic text by page range (inclusive)
                    topic_text, pages_used = extract_text_from_pdf(
                        pdf_path,
                        topic.starting_page_number,
                        topic.ending_page_number
                    )

                    if not topic_text.strip():
                        raise ValueError("抽取文本為空，可能為影像掃描 PDF 或無可用文字。")

                    n_qas = estimate_num_qas(topic_text)
                    print(f"產生 {n_qas} 組問答：{outline.filename} - {topic.topic_title} (頁 {topic.starting_page_number}-{topic.ending_page_number})")

                    qas = generate_qas_for_topic(
                        client=client,
                        document_title=outline.document_title,
                        filename=outline.filename,
                        topic=topic,
                        topic_text=topic_text,
                        n_pairs=n_qas,
                        model_name=MODEL_NAME,
                        temperature=TEMPERATURE,
                    )

                    record = {
                        "filename": outline.filename,
                        "document_title": outline.document_title,
                        "topic_title": topic.topic_title,
                        "page_range": [topic.starting_page_number, topic.ending_page_number],
                        "pages_used": pages_used,
                        "qas": [qa.model_dump() for qa in qas],
                    }
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

                except Exception as e:
                    record = {
                        "filename": outline.filename,
                        "document_title": outline.document_title,
                        "topic_title": topic.topic_title,
                        "page_range": [topic.starting_page_number, topic.ending_page_number],
                        "error": str(e),
                    }
                    out_f.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"✅ 已輸出：{QA_JSONL}")

if __name__ == "__main__":
    main()

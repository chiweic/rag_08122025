import os
import json
import time
from typing import List, Dict, Any

from pydantic import BaseModel, Field, TypeAdapter
from google import genai
from google.genai import types


# ================================
# 1) 資料結構（繁體中文 + 起訖頁，數量不限）
# ================================
class DocumentTopic(BaseModel):
    """一個主題的標題、摘要與其在原始 PDF 的起訖頁碼。"""
    topic_title: str = Field(description="主題正式標題或主要段落標題。")
    topic_summary: str = Field(description="以繁體中文撰寫，約 3 至 4 句的主題內容摘要。")
    starting_page_number: int = Field(description="主題在原始 PDF 中的起始頁碼。")
    ending_page_number: int = Field(description="主題在原始 PDF 中的結束頁碼。")

class DocumentOutline(BaseModel):
    document_title: str = Field(description="PDF 文件的正式標題。")
    main_topics: List[DocumentTopic] = Field(description="依出現順序列出所有主要主題（數量不限，盡可能完整）。")


# ================================
# 2) 工具：將結果寫入 JSONL
# ================================
def write_results_to_jsonl(results: Dict[str, Any], output_path: str) -> None:
    """
    將 batch_extract_topics_from_pdfs_with_batch_api 的結果寫入 JSONL。
    每一行為一個檔案的結果：
      - 正常：{"filename": <檔名>, "document_title": "...", "main_topics": [ ... ] }
      - 錯誤：{"filename": <檔名>, "error": "...", "raw": {...可選} }
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for filename, value in results.items():
            record: Dict[str, Any] = {"filename": filename}
            if isinstance(value, DocumentOutline):
                record.update({
                    "document_title": value.document_title,
                    # pydantic v2：model_dump(); v1 可用 dict()
                    "main_topics": [t.model_dump() for t in value.main_topics],
                })
            elif isinstance(value, dict) and ("_parse_error" in value or "raw" in value):
                # 解析失敗但有原始 payload
                record.update({
                    "error": value.get("_parse_error", "parse_error"),
                    "raw": value.get("raw"),
                })
            else:
                # 其他錯誤字串或未知型別
                record.update({
                    "error": value if isinstance(value, str) else "unknown_error",
                })
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"\n✅ 已輸出 JSONL：{output_path}")


# ===============================================
# 3) 使用 Gemini Batch API（inline 請求）
#    - 預設模型：gemini-2.5-flash-lite
#    - 指令：繁體中文 + 不限主題數量 + 起訖頁碼
# ===============================================
def batch_extract_topics_from_pdfs_with_batch_api(
    file_paths: List[str],
    model_name: str = "models/gemini-2.5-flash-lite",   # ← 預設模型
    display_name: str = "pdf-outline-batch-zh-tw"
) -> Dict[str, Any]:
    """
    使用 Gemini Batch API 分析多份 PDF 文件，輸出繁體中文主題大綱，
    並包含每個主題在原始 PDF 的「起始與結束頁碼」。主題數量不限。
    """
    client = genai.Client()
    uploaded_files: list[tuple[str, types.File]] = []

    # 1) 上傳 PDF 檔案
    print(f"1) 上傳 {len(file_paths)} 份 PDF...")
    for path in file_paths:
        if not os.path.exists(path):
            print(f"   -> 跳過（找不到檔案）: {path}")
            continue
        up = client.files.upload(file=path)
        uploaded_files.append((path, up))
        print(f"   -> 已上傳 '{os.path.basename(path)}' 作為 {up.name}")

    if not uploaded_files:
        print("沒有可上傳的檔案，結束程序。")
        return {}

    # 2) 建立 inline 請求
    print("\n2) 建立批次請求...")
    system_instruction = (
        "你是一位專業的文件分析與索引專家。請仔細閱讀整份 PDF 文件，"
        "以繁體中文輸出清晰的結構化大綱，列出文件中的所有主要主題（數量不限，盡可能完整）。"
        "對於每個主題，請提供：正式標題、一段 3 至 4 句的繁體中文摘要、"
        "以及主題在原始 PDF 中的起始頁碼與結束頁碼。"
        "請忽略前言、序言、自序,致謝、出版資訊或目錄等導言部分，從正式內容開始分析。"
        "請務必依照提供的 JSON Schema 輸出結果。"
    )

    inline_requests: list[dict] = []
    for original_path, uploaded in uploaded_files:
        req = {
            "contents": [{
                "role": "user",
                "parts": [
                    {"text": "請分析此文件，並以繁體中文輸出所有主要主題（數量不限），含摘要與起訖頁碼。"},
                    {
                        "file_data": {
                            "file_uri": uploaded.uri,        # 以 Files API 的 URI 參考上傳的檔案
                            "mime_type": uploaded.mime_type, # 通常為 'application/pdf'
                        }
                    }
                ]
            }],
            "config": {
                "system_instruction": {"parts": [{"text": system_instruction}]},
                "response_mime_type": "application/json",
                "response_schema": DocumentOutline,
                "temperature": 0.0,
            },
            "metadata": {"key": os.path.basename(original_path)},
        }
        inline_requests.append(req)

    # 3) 建立 Batch 任務
    print(f"\n3) 建立批次任務 ({len(inline_requests)} 份文件)...")
    job = client.batches.create(
        model=model_name,
        src=inline_requests,
        config={"display_name": display_name},
    )
    print(f"   -> 任務已建立：{job.name}")

    # 4) 等待完成
    print("\n4) 等待任務完成...")
    terminal = {"JOB_STATE_SUCCEEDED", "JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"}
    while True:
        job = client.batches.get(name=job.name)
        state_name = getattr(job.state, "name", str(job.state))
        print(f"   -> 狀態：{state_name}")
        if state_name in terminal:
            break
        time.sleep(30)

    if getattr(job.state, "name", "") != "JOB_STATE_SUCCEEDED":
        print(f"任務失敗或未成功：{getattr(job.state, 'name', job.state)}")
        for _, up in uploaded_files:
            try:
                client.files.delete(name=up.name)
            except Exception:
                pass
        return {"_error": f"Batch job ended in {getattr(job.state, 'name', job.state)}"}

    # 5) 解析結果
    print("\n5) 解析結果...")
    results: Dict[str, Any] = {}
    inlined_responses = getattr(job.dest, "inlined_responses", []) or []
    for idx, inline_resp in enumerate(inlined_responses):
        key = os.path.basename(uploaded_files[idx][0]) if idx < len(uploaded_files) else f"item_{idx}"

        if getattr(inline_resp, "error", None):
            results[key] = f"錯誤：{inline_resp.error}"
            continue

        payload = None
        # 1) 嘗試直接抓 text
        try:
            text = inline_resp.response.text
            payload = json.loads(text)
        except Exception:
            # 2) 掃 parts 尋找 JSON
            try:
                parts = inline_resp.response.candidates[0].content.parts
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
            results[key] = "無法解析 JSON 結果。"
            continue

        try:
            outline = TypeAdapter(DocumentOutline).validate_python(payload)
            results[key] = outline
            print(f"   -> {key}: 成功解析 {len(outline.main_topics)} 個主題。")
        except Exception as e:
            results[key] = {"_parse_error": str(e), "raw": payload}
            print(f"   -> {key}: 解析錯誤 ({e})。")

    # 6) 清理上傳的檔案
    print("\n6) 清理上傳檔案...")
    for _, up in uploaded_files:
        try:
            client.files.delete(name=up.name)
            print(f"   -> 已刪除 {up.name}")
        except Exception as e:
            print(f"   -> 無法刪除 {up.name}: {e}")

    return results

import glob
# ==================
# 4) 範例執行
# ==================
if __name__ == "__main__":
    # ★ 你可以改成實際路徑
    PDF_FILE_PATHS = []
    for f in glob.glob("data/09*.pdf"):
        print(f"找到 PDF 檔案：{f}")
        PDF_FILE_PATHS.append(f)

    # 只測試一個檔案時可解開註解
    # PDF_FILE_PATHS=PDF_FILE_PATHS[:1]

    # ★ 輸出 JSONL 路徑（可自訂）
    OUTPUT_JSONL = "fgqj_chap9_outline_results.jsonl"

    actual_files = [p for p in PDF_FILE_PATHS if os.path.exists(p) and "path/to/your" not in p]
    if not actual_files:
        print("🚨 請更新 PDF_FILE_PATHS 為實際存在的檔案路徑。")
    else:
        out = batch_extract_topics_from_pdfs_with_batch_api(actual_files)

        print("\n" + "=" * 70)
        print("批次分析最終報告（主題數量不限）")
        print("=" * 70)
        for filename, result in out.items():
            if isinstance(result, DocumentOutline):
                print(f"\n--- {filename} ({result.document_title}) ---")
                for i, topic in enumerate(result.main_topics, start=1):
                    print(f"  {i}. {topic.topic_title}")
                    print(f"     -> 頁碼範圍：{topic.starting_page_number} - {topic.ending_page_number}")
                    print(f"     -> 摘要：{topic.topic_summary}")
            else:
                print(f"\n--- {filename} 錯誤或原始結果 ---")
                print(result)

        # ★ 寫入 JSONL
        write_results_to_jsonl(out, OUTPUT_JSONL)

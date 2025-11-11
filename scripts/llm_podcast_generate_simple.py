#!/usr/bin/env python3
"""
Simple Podcast Generation - Direct PDF to Dialogue Approach

This script takes a PDF document and generates a simple 2-speaker podcast dialogue
using a minimal prompt. It focuses on simplicity and natural conversation flow.

Approach:
- Ingest entire PDF text
- Use LLM with simple prompt to generate dialogue
- Output format: Speaker: [dialogue]

Usage:
    python llm_podcast_generate_simple.py --pdf path/to/document.pdf
    python llm_podcast_generate_simple.py --pdf path/to/document.pdf --max_chars 500

Author: DDM RAG Team
Created: 2025-11-10
"""

import os
import sys
import json
import logging
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================================
# PDF Text Extraction (reuse from llm_topic_detect.py)
# ================================

try:
    import pymupdf  # PyMuPDF
    from opencc import OpenCC
    PYMUPDF_AVAILABLE = True
    cc = OpenCC('s2t')  # Simplified -> Traditional Chinese converter
except ImportError:
    PYMUPDF_AVAILABLE = False
    logger.warning("PyMuPDF not available. Install with: pip install pymupdf")

def load_pdf_with_page_info(fname: str) -> Dict[str, Any]:
    """
    Load PDF and retain page number mapping (reused from llm_topic_detect.py).

    All text is automatically converted to Traditional Chinese.

    Args:
        fname: Path to PDF file

    Returns:
        Dict with keys:
            - 'full_text': Complete document text in Traditional Chinese
            - 'pages': List of page info dicts
            - 'total_pages': Total number of pages
    """
    if not PYMUPDF_AVAILABLE:
        raise ImportError("PyMuPDF 未安裝。請執行: pip install pymupdf")

    try:
        with pymupdf.open(fname) as doc:
            pages_info = []
            current_char_pos = 0

            for page_num, page in enumerate(doc, start=1):
                # Extract text and convert to Traditional Chinese
                text = page.get_text()
                text = cc.convert(text)  # Simplified -> Traditional Chinese

                start_char = current_char_pos
                end_char = current_char_pos + len(text)

                pages_info.append({
                    'text': text,
                    'page_num': page_num,
                    'start_char': start_char,
                    'end_char': end_char
                })

                current_char_pos = end_char + 2  # Add separator length (\n\n)

            full_text = '\n\n'.join([p['text'] for p in pages_info])

            return {
                'full_text': full_text,
                'pages': pages_info,
                'total_pages': len(pages_info)
            }
    except Exception as e:
        logger.error(f"載入 PDF 失敗 {fname}: {e}")
        raise

def extract_text_from_pdf(pdf_path: str, max_pages: Optional[int] = None) -> str:
    """
    Extract text content from PDF file (simplified wrapper).

    Args:
        pdf_path: Path to PDF file
        max_pages: Optional limit on number of pages to extract

    Returns:
        Extracted text content in Traditional Chinese
    """
    try:
        pdf_info = load_pdf_with_page_info(pdf_path)

        total_pages = pdf_info['total_pages']
        logger.info(f"PDF 總頁數: {total_pages}")

        # If max_pages specified, truncate the text
        if max_pages and max_pages < total_pages:
            # Find the end character position of the last page to include
            last_page = pdf_info['pages'][max_pages - 1]
            end_char = last_page['end_char']
            full_text = pdf_info['full_text'][:end_char]
            logger.info(f"提取頁數: {max_pages} (限制)")
        else:
            full_text = pdf_info['full_text']
            logger.info(f"提取頁數: {total_pages} (全部)")

        logger.info(f"提取文字長度: {len(full_text)} 字符")
        return full_text

    except Exception as e:
        logger.error(f"PDF 提取失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


# ================================
# LLM Integration
# ================================

def generate_podcast_with_llm(
    document_text: str,
    model: str = "deepseek-chat",
    max_chars: int = 300,
    temperature: float = 0.8
) -> str:
    """
    Generate podcast dialogue using LLM with simple prompt.

    Args:
        document_text: Source document text
        model: LLM model to use
        max_chars: Maximum character count for dialogue
        temperature: LLM temperature (higher = more creative)

    Returns:
        Generated podcast dialogue script
    """
    try:
        from openai import OpenAI

        # Initialize LLM client
        if model.startswith("deepseek"):
            api_key = os.getenv("DEEPSEEK_API_KEY")
            base_url = "https://api.deepseek.com"
        elif model.startswith("gpt"):
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = "https://api.openai.com/v1"
        else:
            # Custom LLM
            api_key = os.getenv("CUSTOM_LLM_API_KEY", "dummy")
            base_url = os.getenv("CUSTOM_LLM_BASE_URL", "http://area51r5:8000/v1")

        client = OpenAI(api_key=api_key, base_url=base_url)

        # Simple prompt (Traditional Chinese version)
        system_prompt = f"""你是一位富有創意的播客劇本作家。你的任務是將以下文檔內容轉換成一段簡短、引人入勝的雙人中文播客對話。

- **主持人:** 請將他們命名為「小明」和「小紅」。
- **格式:** 對話形式，而不是枯燥的朗讀。小明應該介紹主題，小紅應該補充見解或提出問題。他們需要自然地互動。
- **內容:** 總結文檔中的要點和最有趣的信息。
- **語言:** 整段對話必須使用繁體中文（Traditional Chinese）。
- **篇幅:** 保持在{max_chars}字以內。
- **輸出:** 只提供劇本，格式如下:
小明: [小明的台詞]
小紅: [小紅的台詞]"""

        user_prompt = f"--- 文档原文 ---\n{document_text}"

        logger.info(f"使用 LLM: {model}")
        logger.info(f"文檔長度: {len(document_text)} 字符，目標對話長度: {max_chars} 字")

        # Call LLM
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            # temperature=temperature,
            # max_tokens=2000
        )

        dialogue_script = response.choices[0].message.content.strip()

        logger.info(f"生成對話長度: {len(dialogue_script)} 字符")

        return dialogue_script

    except ImportError:
        logger.error("OpenAI SDK 未安裝。請執行: pip install openai")
        sys.exit(1)
    except Exception as e:
        logger.error(f"LLM 生成失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


# ================================
# Dialogue Parsing & Structuring
# ================================

def parse_dialogue_to_json(dialogue_script: str, pdf_path: str) -> Dict[str, Any]:
    """
    Parse simple dialogue script into structured JSON format.

    Args:
        dialogue_script: Raw dialogue text (format: "Speaker: content")
        pdf_path: Source PDF path for metadata

    Returns:
        Structured podcast JSON
    """
    lines = dialogue_script.strip().split('\n')

    dialogue_turns = []
    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Parse format: "小明: [content]" or "小红: [content]"
        if ':' in line or '：' in line:
            # Support both English and Chinese colons
            separator = ':' if ':' in line else '：'
            parts = line.split(separator, 1)

            if len(parts) == 2:
                speaker_name = parts[0].strip()
                content = parts[1].strip()

                # Map speaker name to role
                speaker_role = "anchor" if speaker_name == "小明" else "guest"

                dialogue_turns.append({
                    "speaker": speaker_role,
                    "speaker_name": speaker_name,
                    "content": content
                })

    # Build structured JSON
    pdf_name = Path(pdf_path).stem

    podcast_json = {
        "episode_title": f"{pdf_name} - 简单播客",
        "episode_summary": f"基于《{pdf_name}》的简短播客对话",
        "speakers": {
            "anchor": "小明",
            "guest": "小红"
        },
        "opening": [],
        "segments": [
            {
                "question_reference": "文档内容总结",
                "segment_title": "主要讨论",
                "dialogue": dialogue_turns,
                "duration_estimate": "1-2分钟"
            }
        ],
        "closing": [],
        "total_duration_estimate": "1-2分钟",
        "generation_method": "simple_prompt_approach"
    }

    return podcast_json


# ================================
# Main Entry Point
# ================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="简单播客生成工具 - 直接从 PDF 生成对话"
    )
    parser.add_argument(
        "--pdf",
        type=str,
        required=True,
        help="PDF 文件路径"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="podcasts",
        help="輸出目錄 (預設：podcasts)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="deepseek-chat",
        help="LLM 模型 (預設：deepseek-chat)"
    )
    parser.add_argument(
        "--max_chars",
        type=int,
        default=300,
        help="對話最大字數 (預設：300)"
    )
    parser.add_argument(
        "--max_pages",
        type=int,
        default=None,
        help="最大提取頁數 (預設：全部頁面)"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.8,
        help="LLM 溫度參數 (預設：0.8)"
    )

    args = parser.parse_args()

    # Validate PDF exists
    if not os.path.exists(args.pdf):
        logger.error(f"❌ PDF 文件不存在: {args.pdf}")
        sys.exit(1)

    logger.info(f"{'='*60}")
    logger.info(f"簡單播客生成工具 - 方法 2 (Simple Prompt Approach)")
    logger.info(f"{'='*60}")
    logger.info(f"PDF 文件: {args.pdf}")
    logger.info(f"LLM 模型: {args.model}")
    logger.info(f"目標字數: {args.max_chars} 字")

    # Step 1: Extract PDF text
    logger.info("\n[步驟 1/3] 提取 PDF 文字...")
    document_text = extract_text_from_pdf(args.pdf, max_pages=args.max_pages)

    if not document_text.strip():
        logger.error("❌ PDF 文字提取為空")
        sys.exit(1)

    # Step 2: Generate podcast dialogue with LLM
    logger.info("\n[步驟 2/3] 使用 LLM 生成播客對話...")
    dialogue_script = generate_podcast_with_llm(
        document_text=document_text,
        model=args.model,
        max_chars=args.max_chars,
        temperature=args.temperature
    )

    # Step 3: Parse and save as JSON
    logger.info("\n[步驟 3/3] 解析對話並保存 JSON...")
    podcast_json = parse_dialogue_to_json(dialogue_script, args.pdf)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Save JSON file
    pdf_basename = Path(args.pdf).stem
    output_json_path = os.path.join(
        args.output_dir,
        f"{pdf_basename}.podcast_simple.json"
    )

    with open(output_json_path, 'w', encoding='utf-8') as f:
        json.dump(podcast_json, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 播客 JSON 已保存: {output_json_path}")

    # Also save raw dialogue script for reference
    output_txt_path = os.path.join(
        args.output_dir,
        f"{pdf_basename}.podcast_simple.txt"
    )

    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write(dialogue_script)

    logger.info(f"✅ 原始對話腳本已保存: {output_txt_path}")

    # Print preview
    logger.info("\n" + "="*60)
    logger.info("生成對話預覽:")
    logger.info("="*60)
    print(dialogue_script)
    logger.info("="*60)

    logger.info(f"\n✅ 完成！共生成 {len(podcast_json['segments'][0]['dialogue'])} 輪對話")


if __name__ == "__main__":
    main()

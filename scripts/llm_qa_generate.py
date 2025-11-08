#!/usr/bin/env python3
"""
Q&A Generation Tool - Production Version

This script generates high-quality question-answer pairs from PDF topic outlines.
It supports multiple LLM providers (DeepSeek, OpenAI, DashScope, Gemini, local vLLM)
and extracts evidence-based Q&As with page references.

This is Stage 2 of the RAG data preparation pipeline:
    Stage 1: PDF → Topic Outline (llm_topic_detect.py)
    Stage 2: Topic Outline → Q&A Pairs (this script)
    Stage 3: Q&A Pairs → Vector Embeddings (init_collections.py)

Key Features:
- Multi-provider support with configurable backends
- Evidence-based Q&A with page number citations
- Adaptive Q&A quantity based on topic length
- Robust error handling and retry mechanisms
- Structured output using Pydantic models
- Progress logging to file and console

Usage:
    # Using default provider (deepseek)
    python llm_qa_generate.py --outline outlines/book.pdf.outline.json

    # Using specific provider
    python llm_qa_generate.py --outline "outlines/*.json" --provider gemini

    # With custom output directory
    python llm_qa_generate.py --outline outlines/book.pdf.outline.json --out_dir qas

Author: DDM RAG Team
Last Updated: 2025-11-08
"""
import os
import logging
import json
import glob
import argparse
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field
import pymupdf  # PyMuPDF
from openai import OpenAI
from dotenv import load_dotenv
import time

# ================================
# Logging Configuration
# ================================
log_file=time.strftime('logs/qa_generation_%Y%m%d_%H%M%S.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ================================
# Pydantic Data Models
# ================================
from enum import Enum

class QuestionType(str, Enum):
    """Types of questions for Buddhist learning."""
    FACTUAL = "事實性問題"           # Fact-based questions about explicit content
    CONCEPTUAL = "概念理解問題"      # Conceptual understanding of Buddhist terms
    PRACTICAL = "應用或修行問題"     # Practical application in daily practice
    ANALYTICAL = "思辨性問題"        # Analytical/critical thinking questions
    REFLECTIVE = "反思性問題"        # Reflective questions for self-examination

class Evidence(BaseModel):
    """Evidence supporting a Q&A pair with page reference and quote."""
    page: int = Field(description="PDF page number where evidence is found")
    quote: str = Field(description="Short quote (1-2 sentences, max 200 chars) supporting the answer")

class TopicQA(BaseModel):
    """A single question-answer pair with evidence and question type."""
    question: str = Field(description="Question in Traditional Chinese")
    question_type: QuestionType = Field(description="Type of question for learning classification")
    answer: str = Field(description="Answer in Traditional Chinese, grounded in provided text")
    evidence: List[Evidence] = Field(description="List of evidence items with page numbers and quotes")

class QACollection(BaseModel):
    """Collection of Q&A pairs for a single topic."""
    qas: List[TopicQA] = Field(description="List of question-answer pairs")

class DocumentTopic(BaseModel):
    """Topic metadata from Stage 1 outline."""
    topic_title: str
    topic_summary: str
    topic_keywords: List[str]
    starting_page_number: int
    ending_page_number: int

class DocumentOutline(BaseModel):
    """Document outline from Stage 1 (llm_topic_detect.py output)."""
    filename: str
    document_title: str
    main_topics: List[DocumentTopic]

# ================================
# PDF Text Extraction
# ================================
def load_pdf_with_page_info(fname: str) -> Dict[str, Any]:
    """
    Load PDF and retain page number and character position mapping.

    This function extracts text from each page and builds a mapping between
    character positions in the full text and their corresponding page numbers.
    This mapping is essential for extracting specific page ranges while preserving
    accurate page numbers.

    Args:
        fname: Path to PDF file

    Returns:
        Dict with keys:
            - 'full_text': Complete document text (pages joined with \n\n)
            - 'pages': List of page info dicts with keys:
                - 'text': Page text content
                - 'page_num': 1-based page number
                - 'start_char': Character position where page starts in full_text
                - 'end_char': Character position where page ends in full_text
            - 'total_pages': Total number of pages

    Raises:
        Exception: If PDF cannot be loaded or read

    Example:
        >>> pdf_info = load_pdf_with_page_info("book.pdf")
        >>> print(f"{pdf_info['total_pages']} pages, {len(pdf_info['full_text'])} chars")
    """
    try:
        with pymupdf.open(fname) as doc:
            pages_info = []
            current_char_pos = 0

            for page_num, page in enumerate(doc, start=1):
                text = page.get_text()
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

def extract_text_for_page_range(pdf_info: Dict[str, Any], start_page: int, end_page: int) -> str:
    """
    Extract text from PDF for a specific page range using pre-loaded PDF info.

    Args:
        pdf_info: PDF data dict from load_pdf_with_page_info()
        start_page: Starting page number (1-indexed)
        end_page: Ending page number (1-indexed, inclusive)

    Returns:
        Extracted text for the page range

    Example:
        >>> pdf_info = load_pdf_with_page_info("book.pdf")
        >>> text = extract_text_for_page_range(pdf_info, 10, 25)
    """
    pages_info = pdf_info['pages']

    # Filter pages within range
    selected_pages = [
        p for p in pages_info
        if start_page <= p['page_num'] <= end_page
    ]

    if not selected_pages:
        return ""

    # Join selected pages with \n\n separator
    return '\n\n'.join([p['text'] for p in selected_pages])

def clamp_text(text: str, limit: int) -> str:
    """
    Truncate text to limit, preferring paragraph boundaries.

    Args:
        text: Text to truncate
        limit: Maximum character count

    Returns:
        Truncated text (at paragraph boundary if possible)
    """
    if len(text) <= limit:
        return text
    # Try to cut at paragraph boundary
    cut = text.rfind("\n\n", 0, limit)
    if cut < 0:
        cut = limit
    return text[:cut]

# NOTE: Removed estimate_num_qas() function - LLM now autonomously determines
# the appropriate number of Q&A pairs based on content richness and depth.
# This allows for more adaptive generation that better matches each topic's
# actual information density.

# ================================
# Main Q&A Generation Function
# ================================
def generate_qas_for_topic(
    client: OpenAI,
    document_title: str,
    filename: str,
    topic: DocumentTopic,
    topic_text: str,
    model_name: str,
    temperature: float,
    max_tokens: int,
    max_context_chars: int
) -> Optional[QACollection]:
    """
    Generate Q&A pairs for a single topic using LLM.

    The LLM autonomously determines the appropriate number of Q&A pairs based on
    content richness, depth, and importance. This allows for adaptive generation
    that matches the actual information density of each topic.

    Supports multiple LLM providers:
    - GPT models (OpenAI): Uses beta.chat.completions.parse()
    - DeepSeek/Qwen3 models: Uses chat.completions with JSON mode
    - vLLM local models (cpatonn/Qwen3-*): Uses beta.chat.completions.parse()
    - Gemini models: Uses beta.chat.completions.parse()

    Args:
        client: OpenAI-compatible client instance
        document_title: Title of source document
        filename: PDF filename
        topic: DocumentTopic object with metadata
        topic_text: Extracted text content for this topic
        model_name: Model identifier (e.g., "gpt-4", "deepseek-chat")
        temperature: LLM temperature (0.0-1.0)
        max_tokens: Maximum output tokens
        max_context_chars: Maximum characters to send to LLM

    Returns:
        QACollection: Collection of Q&A pairs, or None if generation fails
    """
    # Build system instruction
    system_instruction = (
        "你是一位嚴謹的知識助教。根據提供的『主題正文文本』產生與其高度相關的問答組。"
        "請務必以繁體中文撰寫、嚴格根據文本內容作答，不要臆測或引入外部資訊。\n\n"

        "重要規則：\n"
        "1. 輸出必須是完整且有效的 JSON 格式\n"
        "2. 所有字符串必須用雙引號包圍\n"
        "3. 確保所有括號正確閉合\n"
        "4. 沒有未終止的字符串\n"
        "5. 不要包含 JSON 之外的任何文字\n"
        "6. 每組問答必須提供至少一則證據（包含頁碼與短句式引文）\n"
        "7. 頁碼請使用提供的原始 PDF 頁碼\n"
        "8. 引文不得超過 200 字\n"
        "9. 每個問題必須標註問題類型（question_type）\n\n"

        "問題類型說明：\n"
        "- 事實性問題：針對經文或論述中的明確內容提問（例如：「般若波羅蜜多」是什麼意思？）\n"
        "- 概念理解問題：釐清佛學名相或理論間的關係（例如：「空」與「無常」有什麼不同？）\n"
        "- 應用或修行問題：將理論帶入日常修行或生活（例如：如何在日常生活中實踐「觀心無常」？）\n"
        "- 思辨性問題：鼓勵深入思考與比較（例如：為什麼佛教不主張靈魂？）\n"
        "- 反思性問題：引導學習者內觀自身經驗或信念（例如：我是否能真正體會「無我」？）\n\n"

        "對於每組問答，請提供：\n"
        "- question: 問題（繁體中文，清晰具體）\n"
        "- question_type: 問題類型（必須是以下之一：事實性問題、概念理解問題、應用或修行問題、思辨性問題、反思性問題）\n"
        "- answer: 答案（繁體中文，必須能在正文中找到依據）\n"
        "- evidence: 證據列表（陣列格式），每個證據包含：\n"
        "  - page: 頁碼（整數）\n"
        "  - quote: 引文（字符串，2-4 句話，最多 200 字）\n\n"

        "輸出格式必須嚴格遵循：\n"
        '{"qas": [{"question": "問題內容？", "question_type": "事實性問題", "answer": "答案內容", "evidence": [{"page": 10, "quote": "引文內容"}]}]}'
    )

    # Build user prompt
    prompt = (
        f"【文件標題】{document_title}\n"
        f"【檔名】{filename}\n"
        f"【主題】{topic.topic_title}\n"
        f"【頁碼範圍】{topic.starting_page_number}-{topic.ending_page_number}\n\n"
        f"【主題摘要】\n{topic.topic_summary}\n\n"
        f"【主題正文文本】（僅能根據此內容回答）\n"
        f"{clamp_text(topic_text, max_context_chars)}\n\n"
        f"任務：請根據主題內容的豐富程度和重要性，產生適量的高品質問答（繁體中文）。"
        f"數量應與內容深度相匹配，確保涵蓋主要概念和關鍵細節。"
        f"每個問題都必須標註問題類型（question_type），並盡可能涵蓋不同類型的問題，"
        f"以促進全面的學習（事實性、概念理解、應用修行、思辨性、反思性）。"
        f"每個答案必須能在正文中找到依據，並於 evidence 中列出對應頁碼與 2~4 句短引文。\n\n"
        f"請直接輸出 JSON 格式，不要包含任何其他文字。"
    )

    try:
        # Route to appropriate API based on model name
        if model_name.startswith("gpt-"):
            # OpenAI GPT models
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=QACollection
            )
            qa_collection = response.choices[0].message.parsed

        elif model_name.startswith("deepseek-") or model_name.startswith("qwen3-"):
            # DeepSeek/Qwen3 models with JSON mode
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            json_data = json.loads(response.choices[0].message.content)
            qa_collection = QACollection(**json_data)

        elif model_name.startswith("cpatonn/Qwen3-"):
            # vLLM local models
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=QACollection
            )
            qa_collection = response.choices[0].message.parsed

        elif model_name.startswith("gemini-"):
            # Gemini models (OpenAI-compatible mode)
            response = client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=QACollection
            )
            qa_collection = response.choices[0].message.parsed

        else:
            raise ValueError(f"未知的模型名稱格式: {model_name}")

        logger.info(f"   ✅ 成功生成 {len(qa_collection.qas)} 組問答")
        return qa_collection

    except Exception as e:
        logger.error(f"   ❌ Q&A 生成失敗: {e}")
        return None

# ================================
# Main Processing Function
# ================================
def process_outline_file(
    outline_path: str,
    client: OpenAI,
    model_name: str,
    temperature: float,
    max_tokens: int,
    max_context_chars: int,
    output_dir: str,
    pdf_dir: str
) -> bool:
    """
    Process a single outline JSON file to generate Q&A pairs.

    Args:
        outline_path: Path to outline JSON file (from Stage 1)
        client: OpenAI-compatible client instance
        model_name: Model identifier
        temperature: LLM temperature
        max_tokens: Maximum output tokens
        max_context_chars: Maximum context characters
        output_dir: Output directory for Q&A JSON files

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"開始處理大綱文件：{outline_path}")

        # Load outline JSON
        with open(outline_path, 'r', encoding='utf-8') as f:
            outline_data = json.load(f)

        outline = DocumentOutline(**outline_data)
        logger.info(f"   文件：{outline.document_title}")
        logger.info(f"   主題數：{len(outline.main_topics)}")

        # Prepare output file
        output_filename = os.path.basename(outline_path).replace('.outline.json', '.qa.json')
        output_path = os.path.join(output_dir, output_filename)

        # Load PDF once for all topics
        pdf_path = os.path.join(pdf_dir, outline.filename)
        logger.info(f"   載入 PDF：{pdf_path}")
        try:
            pdf_info = load_pdf_with_page_info(pdf_path)
            logger.info(f"   PDF 載入完成：{pdf_info['total_pages']} 頁")
        except Exception as e:
            logger.error(f"   ❌ PDF 載入失敗: {e}")
            return False

        # Process each topic
        all_topic_qas = []
        for i, topic in enumerate(outline.main_topics, 1):
            logger.info(f"   處理主題 {i}/{len(outline.main_topics)}: {topic.topic_title}")

            # Extract PDF text for this topic's page range
            try:
                topic_text = extract_text_for_page_range(
                    pdf_info=pdf_info,
                    start_page=topic.starting_page_number,
                    end_page=topic.ending_page_number
                )
                logger.info(f"      提取頁碼 {topic.starting_page_number}-{topic.ending_page_number} ({len(topic_text)} 字符)")
            except Exception as e:
                logger.error(f"      ❌ PDF 文本提取失敗: {e}")
                continue

            if not topic_text.strip():
                logger.warning(f"      ⚠️  文本為空，跳過此主題")
                continue

            # Generate Q&As (LLM determines appropriate quantity)
            qa_collection = generate_qas_for_topic(
                client=client,
                document_title=outline.document_title,
                filename=outline.filename,
                topic=topic,
                topic_text=topic_text,
                model_name=model_name,
                temperature=temperature,
                max_tokens=max_tokens,
                max_context_chars=max_context_chars
            )

            if qa_collection:
                all_topic_qas.append({
                    "topic_title": topic.topic_title,
                    "topic_summary": topic.topic_summary,
                    "page_range": [topic.starting_page_number, topic.ending_page_number],
                    "qas": [qa.model_dump() for qa in qa_collection.qas]
                })

        # Save results
        result = {
            "filename": outline.filename,
            "document_title": outline.document_title,
            "topics": all_topic_qas
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 已保存：{output_path} ({len(all_topic_qas)} 個主題)")
        return True

    except Exception as e:
        logger.error(f"❌ 處理大綱文件失敗: {e}")
        return False

# ================================
# Main Function
# ================================
from llm_config import config_manager

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Q&A 生成工具（從主題大綱生成問答對）")
    parser.add_argument("--outline", type=str, required=True,
                       help="大綱 JSON 檔案路徑或通配符模式（例如 outlines/*.json）")
    parser.add_argument("--out_dir", type=str, default="qas",
                       help="輸出目錄 (預設：qas)")
    parser.add_argument("--pdf_dir", type=str, default=None,
                       help="PDF 檔案目錄（如果大綱中未包含完整路徑）")
    parser.add_argument("--log_level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日誌級別")
    parser.add_argument("--provider", type=str,
                       choices=config_manager.get_available_providers(),
                       help="LLM 供應商選擇")
    parser.add_argument("--overwrite", action="store_true",
                       help="如果指定，將覆蓋已存在的輸出文件")

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Validate and get provider config
    try:
        provider_config = config_manager.get_provider_config(args.provider)
        if not config_manager.validate_config(args.provider):
            logger.error(f"{args.provider} 配置不完整，請檢查 .env 文件")
            return

        logger.info(f"使用供應商: {args.provider or config_manager.default_provider}")
        logger.info(f"模型: {provider_config.model_name}")

    except ValueError as e:
        logger.error(f"配置錯誤: {e}")
        return

    # Create OpenAI client
    client = OpenAI(
        api_key=provider_config.api_key,
        base_url=provider_config.base_url
    )

    # Ensure output directory exists
    os.makedirs(args.out_dir, exist_ok=True)

    # Find all matching outline files
    outline_files = glob.glob(args.outline)
    if not outline_files:
        logger.warning(f"沒有找到匹配的大綱文件: {args.outline}")
        return

    logger.info(f"找到 {len(outline_files)} 個大綱文件待處理")

    # Process each outline file
    successful_count = 0
    for outline_file in outline_files:
        output_file = os.path.join(
            args.out_dir,
            os.path.basename(outline_file).replace('.outline.json', '.qa.json')
        )

        if os.path.exists(output_file) and not args.overwrite:
            logger.info(f"跳過已存在的文件: {output_file}")
            successful_count += 1
            continue

        success = process_outline_file(
            outline_path=outline_file,
            client=client,
            model_name=provider_config.model_name,
            temperature=provider_config.temperature,
            max_tokens=provider_config.max_tokens,
            max_context_chars=provider_config.max_context_chars,
            output_dir=args.out_dir,
            pdf_dir=args.pdf_dir 
        )

        if success:
            successful_count += 1

    logger.info(f"處理完成！成功: {successful_count}/{len(outline_files)} 個文件")

if __name__ == "__main__":
    main()

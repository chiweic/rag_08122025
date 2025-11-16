#!/usr/bin/env python3
"""
PDF Topic Extraction Tool - Production Version

This script extracts structured topic outlines from PDF documents using LLMs.
It supports multiple LLM providers (DeepSeek, OpenAI, DashScope, local vLLM)
and handles large documents through intelligent chunking and merging.

Key Features:
- Multi-provider support with configurable backends
- Automatic chunking for documents exceeding context limits
- Advanced topic deduplication using title similarity, page overlap, and keywords
- Robust JSON parsing with fallback mechanisms
- Structured output using Pydantic models
- Progress logging to file and console

Usage:
    # Using default provider (deepseek)
    python llm_topic_detect.py --pdf data/book.pdf

    # Using specific provider
    python llm_topic_detect.py --pdf "data/*.pdf" --provider openai

    # With custom output directory
    python llm_topic_detect.py --pdf data/book.pdf --out_dir custom_outlines

Author: DDM RAG Team
Last Updated: 2025-11-08
"""
import os
import logging
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple
import pymupdf  # PyMuPDF
import json
from difflib import SequenceMatcher
import glob
import argparse
from openai import OpenAI
import time
from opencc import OpenCC  # Simplified to Traditional Chinese conversion

# ================================
# 配置日誌
# ================================
log_file=time.strftime('logs/pdf_topic_extraction_%Y%m%d_%H%M%S.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        # timestamped log file
        logging.FileHandler(filename=log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ================================
# Chinese Conversion
# ================================
# Initialize OpenCC converter (Simplified to Traditional Chinese)
cc = OpenCC('s2t')  # s2t = Simplified to Traditional

# ================================
# Pydantic 資料模型
# ================================
class DocumentTopicBase(BaseModel):
    """LLM 生成的主題基礎模型（不包含 text）"""
    topic_title: str = Field(description="主題正式標題或主要段落標題。")
    topic_summary: str = Field(description="以繁體中文撰寫，一段簡短扼要的繁體中文摘要。")
    topic_keywords: List[str] = Field(description="主題相關的關鍵詞列表。")
    starting_page_number: int = Field(description="主題在原始 PDF 檔案中的起始頁碼（使用 PDF 檔案頁碼，非書籍內頁印刷頁碼）。")
    ending_page_number: int = Field(description="主題在原始 PDF 檔案中的結束頁碼（使用 PDF 檔案頁碼，非書籍內頁印刷頁碼）。")

class DocumentTopic(DocumentTopicBase):
    """完整主題模型（包含後處理的 text 字段）"""
    text: str = Field(default="", description="主題對應的文本內容（從起訖頁碼提取）。")

class DocumentChunkOutline(BaseModel):
    """LLM 用於單個文本塊的輸出格式（不包含 full_text 和 text）"""
    filename: str = Field(description="PDF 文件的檔名。")
    document_title: str = Field(description="PDF 文件的正式標題。")
    main_topics: List[DocumentTopicBase] = Field(description="依出現順序列出所有主要主題（數量不限，盡可能完整）。")

class DocumentOutline(BaseModel):
    """最終輸出格式（包含 full_text）"""
    filename: str = Field(description="PDF 文件的檔名。")
    document_title: str = Field(description="PDF 文件的正式標題。")
    full_text: str = Field(description="完整 PDF 文本內容（所有頁面）。")
    main_topics: List[DocumentTopic] = Field(description="依出現順序列出所有主要主題（數量不限，盡可能完整）。")


# ================================
# Topic Conversion Helper
# ================================
def convert_to_document_topic(base_topic: DocumentTopicBase) -> DocumentTopic:
    """
    Convert DocumentTopicBase to DocumentTopic with empty text field.

    Args:
        base_topic: DocumentTopicBase object from LLM

    Returns:
        DocumentTopic: Extended topic with text field (initially empty)
    """
    return DocumentTopic(
        topic_title=base_topic.topic_title,
        topic_summary=base_topic.topic_summary,
        topic_keywords=base_topic.topic_keywords,
        starting_page_number=base_topic.starting_page_number,
        ending_page_number=base_topic.ending_page_number,
        text=""  # Will be filled in post-processing
    )

# ================================
# Topic Similarity and Merging Functions
# ================================
def topics_similar(t1: DocumentTopicBase, t2: DocumentTopicBase, threshold: float = 0.7) -> bool:
    """
    Determine if two topics are similar based on multiple criteria.

    Uses a three-pronged approach:
    1. Title similarity (string matching)
    2. Page range overlap
    3. Keyword similarity

    Topics are considered similar if ANY of these conditions are met:
    - Title similarity >= threshold (default 70%)
    - Page overlap >= 2 pages AND keyword similarity >= 30%
    - Page overlap >= 3 pages AND title similarity >= 50%

    Args:
        t1: First DocumentTopic
        t2: Second DocumentTopic
        threshold: Minimum title similarity ratio (0.0-1.0), default 0.7

    Returns:
        bool: True if topics are similar, False otherwise

    Example:
        >>> topic1 = DocumentTopic(topic_title="佛教入門", ...)
        >>> topic2 = DocumentTopic(topic_title="佛教基礎", ...)
        >>> topics_similar(topic1, topic2)  # May return True if similar enough
    """
    # Calculate title similarity using SequenceMatcher (Ratcliff-Obershelp algorithm)
    title_similarity = SequenceMatcher(None, t1.topic_title.lower(), t2.topic_title.lower()).ratio()

    # Calculate page range overlap
    page_range1 = set(range(t1.starting_page_number, t1.ending_page_number + 1))
    page_range2 = set(range(t2.starting_page_number, t2.ending_page_number + 1))
    page_overlap = len(page_range1.intersection(page_range2))

    # Calculate keyword similarity (Jaccard similarity)
    keywords1 = set(t1.topic_keywords)
    keywords2 = set(t2.topic_keywords)
    keyword_similarity = len(keywords1.intersection(keywords2)) / max(len(keywords1), len(keywords2), 1)

    # Combined decision: high title similarity OR (page overlap AND keyword match)
    return (title_similarity >= threshold or
            (page_overlap >= 2 and keyword_similarity >= 0.3) or
            (page_overlap >= 3 and title_similarity >= 0.5))

def merge_topic_group(topics: List[DocumentTopicBase]) -> DocumentTopicBase:
    """
    Merge a group of similar topics into a single consolidated topic.

    Merging strategy:
    - Page range: Union (min start, max end)
    - Title: Most frequent title among group
    - Keywords: Union of all keywords, sorted by frequency, top 15
    - Summary: Longest summary (most comprehensive)

    Args:
        topics: List of DocumentTopicBase objects to merge (must not be empty)

    Returns:
        DocumentTopicBase: Single merged topic

    Raises:
        ValueError: If topics list is empty

    Example:
        >>> topics = [topic1, topic2, topic3]  # Similar topics from overlapping chunks
        >>> merged = merge_topic_group(topics)
        >>> print(f"Merged pages {merged.starting_page_number}-{merged.ending_page_number}")
    """
    if not topics:
        raise ValueError("主題列表不能為空")

    # Calculate merged page range (union of all page ranges)
    start_page = min(t.starting_page_number for t in topics)
    end_page = max(t.ending_page_number for t in topics)

    # Choose most common title (voting mechanism)
    titles = [t.topic_title for t in topics]
    chosen_title = max(set(titles), key=titles.count)

    # Merge keywords with frequency-based ranking
    all_keywords = list(set(kw for t in topics for kw in t.topic_keywords))
    keyword_freq = {}
    for topic in topics:
        for kw in topic.topic_keywords:
            keyword_freq[kw] = keyword_freq.get(kw, 0) + 1
    # Sort by frequency (descending) and limit to top 15
    all_keywords.sort(key=lambda x: keyword_freq.get(x, 0), reverse=True)

    # Choose longest summary (assumed to be most comprehensive)
    chosen_summary = max(topics, key=lambda t: len(t.topic_summary)).topic_summary

    return DocumentTopicBase(
        topic_title=chosen_title,
        topic_summary=chosen_summary,
        topic_keywords=all_keywords[:15],  # Limit to top 15 keywords
        starting_page_number=start_page,
        ending_page_number=end_page
    )

def merge_similar_topics(topics: List[DocumentTopicBase]) -> List[DocumentTopicBase]:
    """
    Merge all similar topics in a list using greedy clustering algorithm.

    Algorithm:
    1. Iterate through topics sequentially
    2. For each topic, find all similar topics (using topics_similar())
    3. Merge similar topics into one (using merge_topic_group())
    4. Mark merged topics as used to avoid double-processing
    5. Sort final topics by starting page number

    Time Complexity: O(n²) where n = number of topics
    Space Complexity: O(n)

    Args:
        topics: List of DocumentTopicBase objects (may contain duplicates/similar topics)

    Returns:
        List[DocumentTopicBase]: Deduplicated and merged topics, sorted by page number

    Example:
        >>> topics = [topic1, topic2, topic3, topic4]  # topic2 and topic3 are similar
        >>> merged = merge_similar_topics(topics)
        >>> len(merged)  # Returns 3 (topic2 and topic3 merged)
    """
    if not topics:
        return []

    merged = []
    used_indices = set()

    for i, topic in enumerate(topics):
        if i in used_indices:
            continue  # Already merged with another topic

        # Find all topics similar to current topic
        similar_indices = [i]
        for j in range(i + 1, len(topics)):
            if j not in used_indices and topics_similar(topic, topics[j]):
                similar_indices.append(j)
                used_indices.add(j)

        # Merge if multiple similar topics found
        similar_topics = [topics[idx] for idx in similar_indices]
        if len(similar_topics) == 1:
            merged.append(topic)  # No similar topics, keep as-is
        else:
            merged_topic = merge_topic_group(similar_topics)
            merged.append(merged_topic)

    # Sort by starting page number for document order
    return sorted(merged, key=lambda x: x.starting_page_number)

def find_chunk_overlap_regions(text_chunks: List[Dict]) -> List[Tuple[int, int, int, int]]:
    """
    Find overlapping page regions between consecutive text chunks.

    Args:
        text_chunks: List of chunk dicts with 'start_page' and 'end_page' keys

    Returns:
        List of tuples: (overlap_start_page, overlap_end_page, chunk1_idx, chunk2_idx)

    Example:
        >>> chunks = [
        ...     {'start_page': 1, 'end_page': 50},  # Chunk 0
        ...     {'start_page': 48, 'end_page': 100} # Chunk 1 (overlaps 48-50)
        ... ]
        >>> find_chunk_overlap_regions(chunks)
        [(48, 50, 0, 1)]
    """
    overlap_regions = []

    for i in range(len(text_chunks) - 1):
        current_chunk = text_chunks[i]
        next_chunk = text_chunks[i + 1]

        # Calculate overlapping page range
        overlap_start = max(current_chunk['start_page'], next_chunk['start_page'])
        overlap_end = min(current_chunk['end_page'], next_chunk['end_page'])

        if overlap_start <= overlap_end:
            overlap_regions.append((overlap_start, overlap_end, i, i + 1))

    return overlap_regions

def extract_topics_from_overlap_region(chunk_outlines: List[DocumentChunkOutline],
                                     overlap_region: Tuple[int, int, int, int]) -> List[DocumentTopicBase]:
    """
    Extract and merge topics from an overlapping region between two chunks.

    This helps deduplicate topics that were split across chunk boundaries.

    Args:
        chunk_outlines: List of DocumentChunkOutline objects from each chunk
        overlap_region: Tuple of (start_page, end_page, chunk1_idx, chunk2_idx)

    Returns:
        List[DocumentTopicBase]: Merged topics from the overlap region
    """
    overlap_start, overlap_end, chunk1_idx, chunk2_idx = overlap_region

    # Extract topics that fall within the overlap region from chunk 1
    topics1 = [t for t in chunk_outlines[chunk1_idx].main_topics
               if t.starting_page_number <= overlap_end and t.ending_page_number >= overlap_start]

    # Extract topics that fall within the overlap region from chunk 2
    topics2 = [t for t in chunk_outlines[chunk2_idx].main_topics
               if t.starting_page_number <= overlap_end and t.ending_page_number >= overlap_start]

    # Merge similar topics from both chunks
    overlap_topics = topics1 + topics2
    return merge_similar_topics(overlap_topics)

def merge_chunk_outlines(all_chunk_outlines: List[DocumentChunkOutline],
                        text_chunks: List[Dict], full_text: str) -> DocumentOutline:
    """
    Merge multiple chunk outlines into a single consolidated document outline.

    This two-phase approach handles large documents that were split into chunks:
    1. Phase 1: Process chunk overlap regions to merge topics split across boundaries
    2. Phase 2: Global deduplication of all topics

    Args:
        all_chunk_outlines: List of DocumentChunkOutline objects, one per chunk
        text_chunks: List of chunk metadata dicts (for finding overlaps)
        full_text: Complete PDF text content

    Returns:
        DocumentOutline: Single merged outline with deduplicated topics and full_text

    Raises:
        ValueError: If all_chunk_outlines is empty

    Processing Steps:
        1. Collect all topics from all chunks
        2. Find and process overlapping regions between chunks
        3. Merge topics globally using similarity detection
        4. Remove exact title duplicates
        5. Sort by page number for document order
    """
    if not all_chunk_outlines:
        raise ValueError("沒有可合併的大綱")

    if len(all_chunk_outlines) == 1:
        # Create final outline with full_text for single chunk case
        # Convert DocumentTopicBase to DocumentTopic
        converted_topics = [convert_to_document_topic(t) for t in all_chunk_outlines[0].main_topics]
        return DocumentOutline(
            filename=all_chunk_outlines[0].filename,
            document_title=all_chunk_outlines[0].document_title,
            full_text=full_text,
            main_topics=converted_topics
        )

    logger.info(f"開始合併 {len(all_chunk_outlines)} 個分塊的大綱...")

    # Collect all topics from all chunks
    all_topics = []
    for outline in all_chunk_outlines:
        all_topics.extend(outline.main_topics)

    # Sort by starting page number
    all_topics.sort(key=lambda t: t.starting_page_number)

    # Phase 1: Process chunk overlap regions
    overlap_regions = find_chunk_overlap_regions(text_chunks)
    logger.info(f"找到 {len(overlap_regions)} 個分塊重疊區域")

    # Extract topics from overlap regions
    overlap_topics = []
    for overlap_region in overlap_regions:
        region_topics = extract_topics_from_overlap_region(all_chunk_outlines, overlap_region)
        overlap_topics.extend(region_topics)

    # Phase 2: Global merge of all topics
    all_merged_topics = merge_similar_topics(all_topics)

    # If overlap processing succeeded, merge with global topics
    if overlap_topics:
        logger.info(f"從重疊區域提取了 {len(overlap_topics)} 個主題")
        final_topics = merge_similar_topics(all_merged_topics + overlap_topics)
    else:
        final_topics = all_merged_topics

    # Remove exact title duplicates (final cleanup)
    seen_titles = set()
    unique_topics = []
    for topic in final_topics:
        if topic.topic_title not in seen_titles:
            seen_titles.add(topic.topic_title)
            unique_topics.append(topic)

    # Sort by starting page number for document order
    unique_topics.sort(key=lambda t: t.starting_page_number)

    logger.info(f"合併完成: {len(all_topics)} 個原始主題 -> {len(unique_topics)} 個最終主題")

    # Convert DocumentTopicBase to DocumentTopic before creating final outline
    converted_topics = [convert_to_document_topic(t) for t in unique_topics]

    # Create final outline using first chunk's metadata and including full_text
    return DocumentOutline(
        filename=all_chunk_outlines[0].filename,
        document_title=all_chunk_outlines[0].document_title,
        full_text=full_text,
        main_topics=converted_topics
    )

# ================================
# Text Extraction Helper
# ================================
def extract_text_by_page_range(start_page: int, end_page: int, pages_info: List[Dict]) -> str:
    """
    Extract text content from a page range.

    Args:
        start_page: Starting page number (1-based, inclusive)
        end_page: Ending page number (1-based, inclusive)
        pages_info: List of page info dicts from load_pdf_with_page_info()

    Returns:
        str: Concatenated text from all pages in the range
    """
    text_parts = []
    for page in pages_info:
        if start_page <= page['page_num'] <= end_page:
            text_parts.append(page['text'])

    return '\n\n'.join(text_parts)


# ================================
# PDF Processing Functions
# ================================
def load_pdf_with_page_info(fname: str, remove_headers: bool = True) -> Dict[str, Any]:
    """
    Load PDF and retain page number and character position mapping.

    All text is automatically converted to Traditional Chinese to ensure consistency.

    This function extracts text from each page and builds a mapping between
    character positions in the full text and their corresponding page numbers.
    This mapping is essential for chunking while preserving accurate page numbers.

    Args:
        fname: Path to PDF file
        remove_headers: If True, attempt to remove common header/footer patterns (default: True)

    Returns:
        Dict with keys:
            - 'full_text': Complete document text with page markers (e.g., [PDF_PAGE_1], [PDF_PAGE_2])
                          This is what the LLM sees to determine page numbers
            - 'pages': List of page info dicts with keys:
                - 'text': Page text content in Traditional Chinese (without markers)
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
        import re

        # Common header/footer patterns to remove
        # These patterns match book title + page number (e.g., "學佛羣疑 18", "正信的佛教 42")
        header_patterns = [
            r'^[\u4e00-\u9fff]{2,10}\s+\d+\s*\n',  # Chinese title + number at start of page
            r'\n[\u4e00-\u9fff]{2,10}\s+\d+\s*$',  # Chinese title + number at end of page
            r'^\d+\s+[\u4e00-\u9fff]{2,10}\s*\n',  # Number + Chinese title at start
            r'\n\d+\s+[\u4e00-\u9fff]{2,10}\s*$',  # Number + Chinese title at end
        ]

        with pymupdf.open(fname) as doc:
            pages_info = []
            current_char_pos = 0

            for page_num, page in enumerate(doc, start=1):
                # Extract text and convert to Traditional Chinese
                text = page.get_text()
                text = cc.convert(text)  # Simplified -> Traditional Chinese

                # Remove common headers/footers if requested
                if remove_headers:
                    original_length = len(text)
                    for pattern in header_patterns:
                        text = re.sub(pattern, '', text, flags=re.MULTILINE)

                    # Log if significant text was removed (might indicate over-aggressive removal)
                    removed_chars = original_length - len(text)
                    if removed_chars > 50:  # More than 50 chars removed
                        logger.debug(f"Page {page_num}: Removed {removed_chars} chars (possible headers/footers)")

                start_char = current_char_pos
                end_char = current_char_pos + len(text)

                pages_info.append({
                    'text': text,
                    'page_num': page_num,
                    'start_char': start_char,
                    'end_char': end_char
                })

                current_char_pos = end_char + 2  # Add separator length (\n\n)

            # Create full_text WITH page markers for LLM processing and debugging
            # Format: [PDF_PAGE_1]\n<text>\n\n[PDF_PAGE_2]\n<text>...
            text_parts_with_markers = []
            for page in pages_info:
                marker = f"[PDF_PAGE_{page['page_num']}]"
                text_parts_with_markers.append(f"{marker}\n{page['text']}")

            full_text_with_markers = '\n\n'.join(text_parts_with_markers)

            return {
                'full_text': full_text_with_markers,  # With page markers for LLM
                'pages': pages_info,
                'total_pages': len(pages_info)
            }
    except Exception as e:
        logger.error(f"載入 PDF 失敗 {fname}: {e}")
        raise

def map_char_to_page(char_position: int, pages_info: List[Dict]) -> int:
    """
    Map a character position in full text to its corresponding page number.

    Args:
        char_position: Character index in the full_text string
        pages_info: List of page info dicts from load_pdf_with_page_info()

    Returns:
        int: 1-based page number containing the character position

    Note:
        If position is not found (edge case), returns last page or 1
    """
    for page in pages_info:
        if page['start_char'] <= char_position <= page['end_char']:
            return page['page_num']
    # Fallback: return last page or 1 if empty
    return pages_info[-1]['page_num'] if pages_info else 1

def produce_text_chunks(pdf_info: Dict[str, Any], max_context_chars: int) -> List[Dict[str, Any]]:
    """
    Split full text into chunks based on max_context_chars, preserving page mapping.

    Chunking strategy:
    1. If text fits in max_context_chars: single chunk
    2. Otherwise: split into overlapping chunks at natural boundaries
       - Chunk size: max_context_chars - 2000 (safety buffer)
       - Overlap: 1000 chars between consecutive chunks
       - Split at paragraph boundaries (\\n\\n) when possible
       - Fallback to sentence boundaries (。) if no paragraph break found

    Args:
        pdf_info: PDF data dict from load_pdf_with_page_info()
        max_context_chars: Maximum characters per chunk (e.g., 80000 for 80k tokens)

    Returns:
        List of chunk dicts with keys:
            - 'text': Chunk text content
            - 'chunk_num': 1-based chunk number
            - 'start_char': Character position where chunk starts
            - 'end_char': Character position where chunk ends
            - 'start_page': PDF page number where chunk starts
            - 'end_page': PDF page number where chunk ends
            - 'total_chunks': Total number of chunks

    Example:
        >>> chunks = produce_text_chunks(pdf_info, max_context_chars=80000)
        >>> for chunk in chunks:
        >>>     print(f"Chunk {chunk['chunk_num']}: pages {chunk['start_page']}-{chunk['end_page']}")
    """
    full_text = pdf_info['full_text']
    pages_info = pdf_info['pages']

    text_chunks_to_process = []

    if len(full_text) > max_context_chars:
        logger.info(f"文本過長（{len(full_text)} 字符），將分塊處理")

        # Conservative chunking strategy
        chunk_size = max_context_chars - 2000  # Leave safety margin
        overlap = 1000  # Overlap to prevent splitting topics

        start = 0
        chunk_num = 0

        while start < len(full_text):
            end = min(start + chunk_size, len(full_text))

            # Try to split at natural boundaries if not the last chunk
            if end < len(full_text):
                # First try: paragraph boundary (\n\n)
                paragraph_break = full_text.rfind("\n\n", start + chunk_size - 500, end)
                if paragraph_break > start + chunk_size // 2:
                    end = paragraph_break
                else:
                    # Second try: sentence boundary (。)
                    sentence_break = full_text.rfind("。", start + chunk_size - 200, end)
                    if sentence_break > start + chunk_size // 2:
                        end = sentence_break + 1

            chunk_text = full_text[start:end]

            # Map character positions to page numbers
            start_page = map_char_to_page(start, pages_info)
            end_page = map_char_to_page(min(end - 1, len(full_text) - 1), pages_info)

            chunk_num += 1
            text_chunks_to_process.append({
                'text': chunk_text,
                'chunk_num': chunk_num,
                'start_char': start,
                'end_char': end,
                'start_page': start_page,
                'end_page': end_page,
                'total_chunks': (len(full_text) + chunk_size - 1) // chunk_size
            })

            # Move to next chunk with overlap
            if end >= len(full_text):
                break
            start = end - overlap

    else:
        # Single chunk processing (text fits in context window)
        text_chunks_to_process.append({
            'text': full_text,
            'chunk_num': 1,
            'start_char': 0,
            'end_char': len(full_text),
            'start_page': 1,
            'end_page': pdf_info['total_pages'],
            'total_chunks': 1
        })

    return text_chunks_to_process

# ================================
# Main Processing Function
# ================================
def process_pdf_file(pdf_file: str, client: OpenAI, system_instruction: str,
                    model_name: str, temperature: float, max_tokens: int,
                    max_context_chars: int, timeout_secs: int) -> Optional[DocumentOutline]:
    """
    Process a single PDF file to extract structured topic outline using LLM.

    This is the main orchestration function that:
    1. Loads PDF and builds page mapping
    2. Chunks text if needed (based on max_context_chars)
    3. Sends each chunk to LLM for topic extraction
    4. Merges chunk results into final outline

    Supports multiple LLM providers:
    - GPT models (OpenAI): Uses client.responses.parse()
    - DeepSeek/Qwen3 models: Uses chat.completions with JSON mode
    - vLLM local models (cpatonn/Qwen3-*): Uses beta.chat.completions.parse()

    Args:
        pdf_file: Path to PDF file
        client: OpenAI-compatible client instance
        system_instruction: System prompt for LLM
        model_name: Model identifier (e.g., "gpt-4", "deepseek-chat")
        temperature: LLM temperature (0.0-1.0)
        max_tokens: Maximum output tokens
        max_context_chars: Max characters per chunk (triggers chunking if exceeded)
        timeout_secs: API timeout in seconds

    Returns:
        DocumentOutline: Structured outline with topics, or None if processing fails

    Processing Flow:
        PDF → load_pdf_with_page_info() → produce_text_chunks()
        → LLM processing (per chunk) → merge_chunk_outlines()
        → Final DocumentOutline

    Example:
        >>> from openai import OpenAI
        >>> client = OpenAI(api_key="sk-...")
        >>> outline = process_pdf_file(
        ...     pdf_file="book.pdf",
        ...     client=client,
        ...     system_instruction="Extract topics...",
        ...     model_name="gpt-4",
        ...     temperature=0.1,
        ...     max_tokens=4000,
        ...     max_context_chars=80000,
        ...     timeout_secs=120
        ... )
        >>> if outline:
        ...     print(f"Found {len(outline.main_topics)} topics")
    """
    try:
        logger.info(f"開始處理 PDF 文件：{pdf_file}")
        
        # 1) 載入 PDF 並獲取頁碼資訊
        pdf_info = load_pdf_with_page_info(pdf_file)
        logger.info(f"載入完成，共 {pdf_info['total_pages']} 頁，{len(pdf_info['full_text'])} 字符")
        
        # 2) 分塊處理
        text_chunks = produce_text_chunks(pdf_info, max_context_chars)
        logger.info(f"分成 {len(text_chunks)} 個塊進行處理")
        
        all_chunk_outlines = []
        document_title = None
        
        # 3) 處理每個文本塊
        for chunk in text_chunks:
            # 提取文本塊資訊
            chunk_text = chunk['text']
            chunk_num = chunk['chunk_num']
            total_chunks = chunk['total_chunks']
            
            logger.info(f"處理第 {chunk_num}/{total_chunks} 塊 (頁碼 {chunk['start_page']}-{chunk['end_page']})")
            
            # 構造更嚴格的提示詞
            prompt = (
                f"請分析以下 PDF 文件 filename:{os.path.basename(pdf_file)} 內容（共 {total_chunks} 部分，這是第 {chunk_num} 部分，對應原始 PDF 檔案頁碼約 {chunk['start_page']}-{chunk['end_page']} 頁），"
                f"並以繁體中文輸出主要主題，含摘要與起訖頁碼。\n\n"
                f"重要限制：\n"
                f"1. 請提取重要的主題\n"
                f"2. 每個主題摘要限制在 100 字以內\n"
                f"3. 關鍵詞限制在 5 個以內\n"
                f"4. 請確保輸出完整的、有效的 JSON 格式，所有字符串都正確終止\n"
                f"5. **頁碼識別**：文件內容中包含 [PDF_PAGE_N] 標記（例如 [PDF_PAGE_4]），請根據這些標記來確定主題的起始和結束頁碼\n\n"
                f"【文件內容】\n{chunk_text}\n\n"
                f"請直接輸出 JSON 格式，不要包含任何其他文字。確保 JSON 完整且語法正確。"
            )
            
            try:

                # OpenAI standard structure output parsing
                if model_name.startswith("gpt-"):
                    # using the new response API with DocumentChunkOutline (no full_text)
                    # noted, it won't take all these token, temperature etc.,
                    response = client.responses.parse(
                        model=model_name,
                        input=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        text_format=DocumentChunkOutline
                    )
                    # no parsing needed, directly get the parsed output
                    outline = response.output_parsed

                # deepseek structure output, specify json_object for structure output
                elif model_name.startswith("deepseek-") or model_name.startswith("qwen3-"):
                    # deepseek structure output
                    response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        stream=False,
                        timeout=timeout_secs,
                        response_format={"type": "json_object"}
                    )
                    # we do get something back from LLM
                    # 解析 JSON
                    json_data = json.loads(response.choices[0].message.content)
                    try:
                        outline = DocumentChunkOutline(**json_data)
                    except Exception as e:
                        raise ValueError(f"資料驗證失敗: {e}")

                # vllm local model structure output, or gemini use the parse function
                elif model_name.startswith("cpatonn/Qwen3-") or model_name.startswith("gemini-"):
                    # vllm structure output with DocumentChunkOutline (no full_text)
                    response = client.beta.chat.completions.parse(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=max_tokens,
                        temperature=temperature,
                        response_format=DocumentChunkOutline
                    )
                    outline = response.choices[0].message.parsed
                # if should not end up here
                else:
                    raise ValueError(f"未知的模型名稱格式: {model_name}")


                all_chunk_outlines.append(outline)
            
            except Exception as e:
                logger.error(f"LLM 處理失敗，使用備用方法: {e}")
                return None
                    
        # 4) 合併結果
        if not all_chunk_outlines:
            logger.error(f"無法從任何文本塊中提取主題: {pdf_file}")
            return None

        # 使用改進的合併策略
        try:
            final_outline = merge_chunk_outlines(all_chunk_outlines, text_chunks, pdf_info['full_text'])
            logger.info(f"合併完成: {len(all_chunk_outlines)} 個分塊 -> {len(final_outline.main_topics)} 個主題")
        except Exception as e:
            logger.error(f"合併失敗，使用簡單合併: {e}")
            # 備用簡單合併
            all_topics = []
            for outline in all_chunk_outlines:
                all_topics.extend(outline.main_topics)
            # Convert DocumentTopicBase to DocumentTopic
            converted_topics = [convert_to_document_topic(t) for t in all_topics[:20]]  # 限制主題數量
            final_outline = DocumentOutline(
                filename=os.path.basename(pdf_file),
                document_title=document_title or os.path.basename(pdf_file),
                full_text=pdf_info['full_text'],
                main_topics=converted_topics
            )

        # 5) 提取每個主題對應的文本內容
        logger.info(f"提取主題對應的文本內容...")
        for topic in final_outline.main_topics:
            topic.text = extract_text_by_page_range(
                topic.starting_page_number,
                topic.ending_page_number,
                pdf_info['pages']
            )

        logger.info(f"✅ 處理完成: {pdf_file} -> 提取 {len(final_outline.main_topics)} 個主題")
        return final_outline
        
    except Exception as e:
        logger.error(f"處理 PDF 文件失敗 {pdf_file}: {e}")
        return None

from llm_config import config_manager

def main():
    """主函數"""
    parser = argparse.ArgumentParser(description="PDF 主題提取工具（修復 JSON 錯誤和主題合併問題）")
    
    parser.add_argument("--pdf", type=str, required=True,
                       help="PDF 檔案路徑或通配符模式（例如 data/*.pdf）")
    parser.add_argument("--out_dir", type=str, default="outlines",
                       help="輸出 JSONL 目錄路徑 (預設：outlines)")
    parser.add_argument("--log_level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日誌級別")
    parser.add_argument("--provider", type=str, 
                       choices=config_manager.get_available_providers(),
                       help="LLM 供應商選擇")
    parser.add_argument("--provider_backup", type=str,
                        choices=config_manager.get_available_providers(),
                       help="備用 LLM 供應商選擇（當主要供應商失敗時使用）")
    parser.add_argument("--overwrite", action="store_true",
                       help="如果指定，將覆蓋已存在的輸出文件")
    
    args = parser.parse_args()
    
    # 設置日誌級別
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    # 更嚴格的系統指令
    system_instruction = (
        "你是一位專業的文件分析與索引專家。請仔細閱讀提供的文件內容，"
        "以繁體中文輸出清晰的結構化大綱。\n\n"

        "重要規則：\n"
        "1. 輸出必須是完整且有效的 JSON 格式\n"
        "2. 所有字符串必須用雙引號包圍\n"
        "3. 確保所有括號正確閉合\n"
        "4. 沒有未終止的字符串\n"
        "5. 所有輸出必須使用繁體中文\n"
        "6. 不要包含 JSON 之外的任何文字\n\n"

        "**頁碼識別方法**：\n"
        "文件內容中包含頁碼標記，格式為 [PDF_PAGE_N]（例如 [PDF_PAGE_4]、[PDF_PAGE_5]）。\n"
        "請根據這些標記來確定每個主題的起始和結束頁碼。\n"
        "例如：如果某主題從 [PDF_PAGE_4] 開始到 [PDF_PAGE_6] 結束，則 starting_page_number=4, ending_page_number=6。\n\n"

        "對於每個主題，請提供：\n"
        "- topic_title: 主題正式標題\n"
        "- topic_summary: 繁體中文摘要（簡短扼要）\n"
        "- topic_keywords: 關鍵詞列表（陣列格式）\n"
        "- starting_page_number: 起始頁碼（根據 [PDF_PAGE_N] 標記）\n"
        "- ending_page_number: 結束頁碼（根據 [PDF_PAGE_N] 標記）\n\n"

        "**重要：請忽略以下類型的內容，不要將它們當作主題提取：**\n"
        "- 前言、序言、自序、編者的話等導言性文字\n"
        "- 目錄、索引、參考書目\n"
        "- 致謝、版權聲明、出版資訊\n"
        "- 空白頁、封面頁\n\n"

        "**僅提取正文中的實質性主題**，即實際討論具體內容、理論、方法等的章節。\n\n"

        "❌ 錯誤範例（不要提取）：\n"
        "「自序：從體裁、目的與對象而言，這本書是我在一九六三年所寫...本書的內容，既是知識學問的，更是生活和實用的...」\n"
        "→ 這是作者介紹本書寫作緣起和結構，屬於序言，不是主題。\n\n"

        "✅ 正確範例（應該提取）：\n"
        "「信仰佛教一定要皈依三寶嗎？是的，信仰佛教和鬼神崇拜的民間信仰很不相同，信仰佛教必須三寶具足...」\n"
        "→ 這是實質性討論「皈依三寶」的佛法內容，應該提取為主題。\n\n"

        "輸出格式必須嚴格遵循：\n"
        '{"filename": "文件名", "document_title": "文件標題", "main_topics": [{"topic_title": "標題", "topic_summary": "摘要", "topic_keywords": ["關鍵詞1"], "starting_page_number": 1, "ending_page_number": 2}]}'
    )
    
    # 驗證並獲取供應商配置
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
    
    
    # 創建 OpenAI 客戶端
    client = OpenAI(
        api_key=provider_config.api_key,
        base_url=provider_config.base_url
    )

    # 處理所有匹配的 PDF 文件
    pdf_files = glob.glob(args.pdf)
    if not pdf_files:
        logger.warning(f"沒有找到匹配的 PDF 文件: {args.pdf}")
        return

    logger.info(f"找到 {len(pdf_files)} 個 PDF 文件待處理")

    # Create output directory with model name subdirectory
    # Format: {out_dir}/{model_name}/
    # Sanitize model name for use in path (replace slashes with underscores)
    safe_model_name = provider_config.model_name.replace('/', '_').replace('\\', '_')
    model_output_dir = os.path.join(args.out_dir, safe_model_name)
    os.makedirs(model_output_dir, exist_ok=True)

    logger.info(f"輸出目錄: {model_output_dir}")

    successful_count = 0
    for pdf_file in pdf_files:
        # Generate output filename: {basename}.outline.json
        output_filename = f"{os.path.basename(pdf_file)}.outline.json"
        out_file = os.path.join(model_output_dir, output_filename)
        if os.path.exists(out_file) and not args.overwrite:
            logger.info(f"跳過已存在的文件: {out_file}")
            successful_count += 1
            continue
        try:
            final_outline = process_pdf_file(
                pdf_file=pdf_file, 
                client=client, 
                system_instruction=system_instruction, 
                model_name=provider_config.model_name,
                temperature=provider_config.temperature,
                max_tokens=provider_config.max_tokens,
                max_context_chars=provider_config.max_context_chars,
                timeout_secs=provider_config.timeout
            )
            
            if final_outline:
                # 保存為 JSON 格式
                with open(out_file, "w", encoding="utf-8") as f:
                    # Use json.dumps with model_dump() for ensure_ascii control
                    import json as json_lib
                    json_str = json_lib.dumps(final_outline.model_dump(), ensure_ascii=False, indent=2)
                    f.write(json_str + "\n")
                
                successful_count += 1
                logger.info(f"✅ 已保存: {out_file}")
            else:
                logger.error(f"❌ 處理失敗: {pdf_file}")
                # try backup provider if specified
                if args.provider_backup:
                    logger.info(f"嘗試使用備用供應商: {args.provider_backup}")
                    try:
                        backup_provider_config = config_manager.get_provider_config(args.provider_backup)
                        if not config_manager.validate_config(args.provider_backup):
                            logger.error(f"{args.provider_backup} 配置不完整，請檢查 .env 文件")
                            continue
                        
                        backup_client = OpenAI(
                            api_key=backup_provider_config.api_key,
                            base_url=backup_provider_config.base_url
                        )
                        
                        final_outline = process_pdf_file(
                            pdf_file=pdf_file, 
                            client=backup_client, 
                            system_instruction=system_instruction, 
                            model_name=backup_provider_config.model_name,
                            temperature=backup_provider_config.temperature,
                            max_tokens=backup_provider_config.max_tokens,
                            max_context_chars=backup_provider_config.max_context_chars,
                            timeout_secs=backup_provider_config.timeout
                        )
                        
                        if final_outline:
                            # 保存為 JSON 格式
                            with open(out_file, "w", encoding="utf-8") as f:
                                # Use json.dumps with model_dump() for ensure_ascii control
                                json_str = json_lib.dumps(final_outline.model_dump(), ensure_ascii=False, indent=2)
                                f.write(json_str + "\n")
                            
                            successful_count += 1
                            logger.info(f"✅ 已保存 (備用供應商): {out_file}")
                        else:
                            logger.error(f"❌ 備用供應商處理失敗: {pdf_file}")
                    except Exception as e:
                        logger.error(f"❌ 備用供應商處理時發生錯誤: {e}")


        except Exception as e:
            logger.error(f"❌ 處理文件時發生錯誤 {pdf_file}: {e}")

    logger.info(f"\n✅ 處理完成！成功: {successful_count}/{len(pdf_files)} 個文件")
    logger.info(f"輸出目錄: {model_output_dir}")

if __name__ == "__main__":
    main()
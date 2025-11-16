#!/usr/bin/env python3
"""
Audio Topic Extraction Tool

This script extracts structured topic outlines from audio transcripts (SRT or JSON) using LLMs.
It's adapted from llm_topic_detect.py but works with audio timestamps instead of PDF pages.

Key Features:
- Multi-provider support with configurable backends (DeepSeek, OpenAI, DashScope, local vLLM)
- Supports both SRT and JSON transcript formats (auto-detected)
- Automatic chunking for long transcripts exceeding context limits
- Advanced topic deduplication using title similarity, timestamp overlap, and keywords
- Robust JSON parsing with fallback mechanisms
- Structured output using Pydantic models
- Progress logging to file and console

Input Formats:
    1. SRT format (subtitle format):
        1
        00:00:00,000 --> 00:00:05,500
        First subtitle text

        2
        00:00:05,500 --> 00:00:10,200
        Second subtitle text

    2. JSON format (with segments):
        {
            "segments": [
                {"start": 0.0, "end": 120.5, "text": "..."},
                {"start": 120.5, "end": 240.2, "text": "..."},
                ...
            ]
        }

Usage:
    # Using SRT files
    python audio_topic_detection.py --audio data/transcript.srt

    # Using JSON files with wildcard
    python audio_topic_detection.py --audio "data/*.json" --provider openai

    # With custom output directory
    python audio_topic_detection.py --audio data/transcript.srt --out_dir audio_outlines

Author: DDM RAG Team
Created: 2025-11-10
Updated: 2025-11-14 (Added SRT support)
"""

import os
import sys
import logging
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Tuple
import json
from difflib import SequenceMatcher
import glob
import argparse
from openai import OpenAI
import time
from opencc import OpenCC  # Simplified to Traditional Chinese conversion
from llm_config import config_manager

# ================================
# 配置日誌
# ================================
log_file = time.strftime('logs/audio_topic_extraction_%Y%m%d_%H%M%S.log')
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(filename=log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ================================
# Chinese Conversion
# ================================
cc = OpenCC('s2t')  # Simplified to Traditional

# ================================
# Pydantic 資料模型
# ================================
class AudioTopic(BaseModel):
    """一個主題的標題、摘要與其在音頻中的起訖時間。"""
    topic_title: str = Field(description="主題正式標題或主要段落標題。")
    topic_summary: str = Field(description="以繁體中文撰寫，一段簡短扼要的繁體中文摘要。")
    topic_keywords: List[str] = Field(description="主題相關的關鍵詞列表。")
    starting_timestamp: float = Field(description="主題在音頻中的起始時間（秒）。")
    ending_timestamp: float = Field(description="主題在音頻中的結束時間（秒）。")
    text: str = Field(default="", description="主題對應的逐字稿文本（從起訖時間戳提取）。")

class AudioChunkOutline(BaseModel):
    """LLM 用於單個文本塊的輸出格式（不包含 full_text）"""
    filename: str = Field(description="音頻文件的檔名。")
    audio_title: str = Field(description="音頻的正式標題。")
    main_topics: List[AudioTopic] = Field(description="依出現順序列出所有主要主題（數量不限，盡可能完整）。")

class AudioOutline(BaseModel):
    """最終輸出格式（包含 full_text）"""
    filename: str = Field(description="音頻文件的檔名。")
    audio_title: str = Field(description="音頻的正式標題。")
    full_text: str = Field(description="完整逐字稿原始文本（未修正）。")
    correct_text: str = Field(default="", description="完整逐字稿修正文本（LLM 修正後，如啟用修正功能）。")
    main_topics: List[AudioTopic] = Field(description="依出現順序列出所有主要主題（數量不限，盡可能完整）。")

# ================================
# Topic Similarity and Merging Functions
# ================================
def topics_similar(t1: AudioTopic, t2: AudioTopic, threshold: float = 0.7) -> bool:
    """
    Determine if two audio topics are similar based on multiple criteria.

    Uses a three-pronged approach:
    1. Title similarity (string matching)
    2. Timestamp range overlap
    3. Keyword similarity

    Topics are considered similar if ANY of these conditions are met:
    - Title similarity >= threshold (default 70%)
    - Timestamp overlap >= 60 seconds AND keyword similarity >= 30%
    - Timestamp overlap >= 120 seconds AND title similarity >= 50%

    Args:
        t1: First AudioTopic
        t2: Second AudioTopic
        threshold: Minimum title similarity ratio (0.0-1.0), default 0.7

    Returns:
        bool: True if topics are similar, False otherwise
    """
    # Calculate title similarity
    title_similarity = SequenceMatcher(None, t1.topic_title.lower(), t2.topic_title.lower()).ratio()

    # Calculate timestamp overlap (in seconds)
    overlap_start = max(t1.starting_timestamp, t2.starting_timestamp)
    overlap_end = min(t1.ending_timestamp, t2.ending_timestamp)
    timestamp_overlap = max(0, overlap_end - overlap_start)

    # Calculate keyword similarity (Jaccard similarity)
    keywords1 = set(t1.topic_keywords)
    keywords2 = set(t2.topic_keywords)
    keyword_similarity = len(keywords1.intersection(keywords2)) / max(len(keywords1), len(keywords2), 1)

    # Combined decision
    return (title_similarity >= threshold or
            (timestamp_overlap >= 60 and keyword_similarity >= 0.3) or
            (timestamp_overlap >= 120 and title_similarity >= 0.5))


def merge_topic_group(topics: List[AudioTopic]) -> AudioTopic:
    """
    Merge a group of similar topics into a single consolidated topic.

    Merging strategy:
    - Timestamp range: Union (min start, max end)
    - Title: Most frequent title among group
    - Keywords: Union of all keywords, sorted by frequency, top 15
    - Summary: Longest summary (most comprehensive)

    Args:
        topics: List of AudioTopic objects to merge (must not be empty)

    Returns:
        AudioTopic: Single merged topic
    """
    if not topics:
        raise ValueError("Cannot merge empty topic list")

    # Timestamp range: Union
    min_timestamp = min(t.starting_timestamp for t in topics)
    max_timestamp = max(t.ending_timestamp for t in topics)

    # Title: Most frequent
    from collections import Counter
    title_counts = Counter(t.topic_title for t in topics)
    merged_title = title_counts.most_common(1)[0][0]

    # Keywords: Union, sorted by frequency, top 15
    all_keywords = [kw for t in topics for kw in t.topic_keywords]
    keyword_counts = Counter(all_keywords)
    merged_keywords = [kw for kw, _ in keyword_counts.most_common(15)]

    # Summary: Longest (most comprehensive)
    merged_summary = max((t.topic_summary for t in topics), key=len)

    return AudioTopic(
        topic_title=merged_title,
        topic_summary=merged_summary,
        topic_keywords=merged_keywords,
        starting_timestamp=min_timestamp,
        ending_timestamp=max_timestamp
    )


def deduplicate_topics(topics: List[AudioTopic], similarity_threshold: float = 0.7) -> List[AudioTopic]:
    """
    Remove duplicate/similar topics using clustering approach.

    Uses connected components algorithm:
    1. Build similarity graph (topics = nodes, similar pairs = edges)
    2. Find connected components (groups of mutually similar topics)
    3. Merge each component into a single topic

    Args:
        topics: List of AudioTopic objects
        similarity_threshold: Minimum similarity to consider topics duplicates

    Returns:
        List[AudioTopic]: Deduplicated list, sorted by starting timestamp
    """
    if len(topics) <= 1:
        return topics

    n = len(topics)

    # Build adjacency list for similarity graph
    similar_groups = {}
    for i in range(n):
        similar_groups[i] = set()

    for i in range(n):
        for j in range(i + 1, n):
            if topics_similar(topics[i], topics[j], threshold=similarity_threshold):
                similar_groups[i].add(j)
                similar_groups[j].add(i)

    # Find connected components using DFS
    visited = set()
    components = []

    def dfs(node, component):
        visited.add(node)
        component.append(node)
        for neighbor in similar_groups[node]:
            if neighbor not in visited:
                dfs(neighbor, component)

    for i in range(n):
        if i not in visited:
            component = []
            dfs(i, component)
            components.append(component)

    # Merge each component
    merged_topics = []
    for component in components:
        topic_group = [topics[i] for i in component]
        merged = merge_topic_group(topic_group)
        merged_topics.append(merged)

    # Sort by starting timestamp
    merged_topics.sort(key=lambda t: t.starting_timestamp)

    logger.info(f"去重：{len(topics)} 個主題 → {len(merged_topics)} 個主題")
    return merged_topics


# ================================
# SRT Parsing Functions
# ================================
def parse_srt_time(time_str: str) -> float:
    """
    Parse SRT timestamp string to seconds.

    Format: HH:MM:SS,mmm (e.g., "00:01:23,456")

    Args:
        time_str: SRT timestamp string

    Returns:
        float: Time in seconds
    """
    # Split hours:minutes:seconds,milliseconds
    time_part, ms_part = time_str.strip().split(',')
    h, m, s = map(int, time_part.split(':'))
    ms = int(ms_part)

    return h * 3600 + m * 60 + s + ms / 1000.0


def load_srt_file(srt_path: str) -> Dict[str, Any]:
    """
    Load SRT subtitle file and convert to segment format.

    SRT format:
        1
        00:00:00,000 --> 00:00:05,500
        First subtitle text

        2
        00:00:05,500 --> 00:00:10,200
        Second subtitle text

    Args:
        srt_path: Path to SRT file

    Returns:
        Dict with keys:
            - 'full_text': Complete transcript text in Traditional Chinese
            - 'segments': List of segment info dicts
            - 'total_duration': Total duration in seconds
    """
    segments_info = []
    current_char_pos = 0

    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Split into subtitle blocks (separated by double newlines)
        blocks = content.strip().split('\n\n')

        for block in blocks:
            lines = block.strip().split('\n')

            if len(lines) < 3:
                continue  # Skip malformed blocks

            # Line 0: Subtitle number (skip)
            # Line 1: Timestamp range
            # Line 2+: Subtitle text

            timestamp_line = lines[1]
            text_lines = lines[2:]

            # Parse timestamps
            if '-->' not in timestamp_line:
                continue

            start_str, end_str = timestamp_line.split('-->')
            start_time = parse_srt_time(start_str)
            end_time = parse_srt_time(end_str)

            # Join text lines and convert to Traditional Chinese
            text = ' '.join(text_lines).strip()
            if not text:
                continue

            text = cc.convert(text)  # Simplified -> Traditional Chinese

            start_char = current_char_pos
            end_char = current_char_pos + len(text)

            segments_info.append({
                'text': text,
                'start': start_time,
                'end': end_time,
                'start_char': start_char,
                'end_char': end_char
            })

            current_char_pos = end_char + 2  # Add separator length (\n\n)

        if not segments_info:
            raise ValueError(f"No valid segments found in {srt_path}")

        full_text = '\n\n'.join([seg['text'] for seg in segments_info])
        total_duration = segments_info[-1]['end'] if segments_info else 0

        return {
            'full_text': full_text,
            'segments': segments_info,
            'total_duration': total_duration
        }

    except Exception as e:
        logger.error(f"載入 SRT 文件失敗 {srt_path}: {e}")
        raise


# ================================
# Audio Loading and Chunking
# ================================
def load_audio_with_timestamp_info(audio_file_path: str) -> Dict[str, Any]:
    """
    Load audio transcript (SRT or JSON) and retain timestamp information.

    Auto-detects format based on file extension:
    - .srt: SRT subtitle format
    - .json: JSON format with segments array

    All text is automatically converted to Traditional Chinese to ensure consistency.

    Args:
        audio_file_path: Path to audio transcript file (SRT or JSON)

    Returns:
        Dict with keys:
            - 'full_text': Complete transcript text in Traditional Chinese
            - 'segments': List of segment info dicts with keys:
                - 'text': Segment text content in Traditional Chinese
                - 'start': Starting timestamp (seconds)
                - 'end': Ending timestamp (seconds)
                - 'start_char': Character position where segment starts in full_text
                - 'end_char': Character position where segment ends in full_text
            - 'total_duration': Total audio duration in seconds

    Raises:
        Exception: If file cannot be loaded or parsed
    """
    file_ext = os.path.splitext(audio_file_path)[1].lower()

    # Auto-detect format
    if file_ext == '.srt':
        logger.info(f"檢測到 SRT 格式文件")
        return load_srt_file(audio_file_path)

    elif file_ext == '.json':
        logger.info(f"檢測到 JSON 格式文件")
        try:
            with open(audio_file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            segments = data.get('segments', [])
            if not segments:
                raise ValueError(f"No segments found in {audio_file_path}")

            segments_info = []
            current_char_pos = 0

            for seg in segments:
                # Extract and convert text to Traditional Chinese
                text = seg.get('text', '').strip()
                if not text:
                    continue

                text = cc.convert(text)  # Simplified -> Traditional Chinese

                start_time = float(seg.get('start', 0))
                end_time = float(seg.get('end', 0))

                start_char = current_char_pos
                end_char = current_char_pos + len(text)

                segments_info.append({
                    'text': text,
                    'start': start_time,
                    'end': end_time,
                    'start_char': start_char,
                    'end_char': end_char
                })

                current_char_pos = end_char + 2  # Add separator length (\n\n)

            full_text = '\n\n'.join([seg['text'] for seg in segments_info])
            total_duration = segments_info[-1]['end'] if segments_info else 0

            return {
                'full_text': full_text,
                'segments': segments_info,
                'total_duration': total_duration
            }

        except Exception as e:
            logger.error(f"載入音頻 JSON 失敗 {audio_file_path}: {e}")
            raise

    else:
        raise ValueError(f"不支持的文件格式: {file_ext}。僅支持 .srt 和 .json 文件")


def map_char_to_timestamp(char_position: int, segments_info: List[Dict]) -> Tuple[float, float]:
    """
    Map a character position in full text to its corresponding timestamp range.

    Args:
        char_position: Character index in the full_text string
        segments_info: List of segment info dicts from load_audio_with_timestamp_info()

    Returns:
        Tuple[float, float]: (start_time, end_time) containing the character position
    """
    for seg in segments_info:
        if seg['start_char'] <= char_position <= seg['end_char']:
            return (seg['start'], seg['end'])

    # Fallback: return last segment or (0, 0)
    if segments_info:
        return (segments_info[-1]['start'], segments_info[-1]['end'])
    return (0.0, 0.0)


def extract_text_by_timestamp(start_time: float, end_time: float, segments_info: List[Dict]) -> str:
    """
    Extract text content from segments that fall within the specified timestamp range.

    This helper function allows on-demand text extraction from topics using their timestamps,
    eliminating the need to store text in the JSON output files.

    Usage:
        audio_info = load_audio_with_timestamp_info('audio.json')
        topic_text = extract_text_by_timestamp(
            topic.starting_timestamp,
            topic.ending_timestamp,
            audio_info['segments']
        )

    Args:
        start_time: Starting timestamp (seconds)
        end_time: Ending timestamp (seconds)
        segments_info: List of segment dictionaries with 'start', 'end', and 'text' keys

    Returns:
        Concatenated text from segments within the timestamp range
    """
    text_parts = []

    for seg in segments_info:
        seg_start = seg['start']
        seg_end = seg['end']

        # Check if segment overlaps with the timestamp range
        if seg_end >= start_time and seg_start <= end_time:
            text_parts.append(seg['text'])

    return ' '.join(text_parts)


def produce_text_chunks(audio_info: Dict[str, Any], max_context_chars: int) -> List[Dict[str, Any]]:
    """
    Split full transcript into chunks based on max_context_chars, preserving timestamp mapping.

    Chunking strategy:
    1. If text fits in max_context_chars: single chunk
    2. Otherwise: split into overlapping chunks at natural boundaries
       - Chunk size: max_context_chars - 2000 (safety buffer)
       - Overlap: 1000 chars between consecutive chunks
       - Split at paragraph boundaries (\\n\\n) when possible
       - Fallback to sentence boundaries (。) if no paragraph break found

    Args:
        audio_info: Audio data dict from load_audio_with_timestamp_info()
        max_context_chars: Maximum characters per chunk

    Returns:
        List of chunk dicts, each with:
            - text: Chunk text content
            - chunk_num: 1-based chunk number
            - start_char: Starting character position in full_text
            - end_char: Ending character position in full_text
            - start_time: Starting timestamp (seconds)
            - end_time: Ending timestamp (seconds)
            - total_chunks: Total number of chunks
    """
    full_text = audio_info['full_text']
    segments_info = audio_info['segments']
    text_len = len(full_text)

    text_chunks_to_process = []

    if text_len > max_context_chars:
        # Multi-chunk processing
        chunk_size = max_context_chars - 2000  # Safety buffer
        overlap = 1000
        start_pos = 0
        chunk_num = 1

        while start_pos < text_len:
            end_pos = min(start_pos + chunk_size, text_len)

            # Find natural break point (paragraph or sentence boundary)
            if end_pos < text_len:
                # Try paragraph break first
                last_para = full_text.rfind('\n\n', start_pos, end_pos)
                if last_para > start_pos:
                    end_pos = last_para + 2
                else:
                    # Fallback to sentence boundary
                    last_sentence = full_text.rfind('。', start_pos, end_pos)
                    if last_sentence > start_pos:
                        end_pos = last_sentence + 1

            chunk_text = full_text[start_pos:end_pos]

            # Map to timestamps
            start_time, _ = map_char_to_timestamp(start_pos, segments_info)
            _, end_time = map_char_to_timestamp(end_pos - 1, segments_info)

            text_chunks_to_process.append({
                'text': chunk_text,
                'chunk_num': chunk_num,
                'start_char': start_pos,
                'end_char': end_pos,
                'start_time': start_time,
                'end_time': end_time,
                'total_chunks': -1  # Will be updated later
            })

            start_pos = end_pos - overlap
            chunk_num += 1

        # Update total_chunks
        total = len(text_chunks_to_process)
        for chunk in text_chunks_to_process:
            chunk['total_chunks'] = total

    else:
        # Single chunk processing
        start_time = segments_info[0]['start'] if segments_info else 0
        end_time = segments_info[-1]['end'] if segments_info else 0

        text_chunks_to_process.append({
            'text': full_text,
            'chunk_num': 1,
            'start_char': 0,
            'end_char': len(full_text),
            'start_time': start_time,
            'end_time': end_time,
            'total_chunks': 1
        })

    return text_chunks_to_process


# ================================
# Transcription Error Correction
# ================================
def correct_transcription_errors(text: str, client: OpenAI, model_name: str,
                                temperature: float, max_tokens: int, timeout_secs: int) -> str:
    """
    Use LLM to correct potential transcription errors in the text.

    This is particularly useful for:
    - Buddhist terminology that STT models might mishear
    - Homophones (同音字) in Chinese
    - Context-dependent word choices
    - Grammar and punctuation improvements

    Args:
        text: Original transcribed text
        client: OpenAI-compatible client instance
        model_name: Model identifier
        temperature: LLM temperature (recommend 0.3 for correction task)
        max_tokens: Maximum output tokens
        timeout_secs: API timeout in seconds

    Returns:
        str: Corrected text
    """
    try:
        correction_prompt = f"""請仔細檢查以下音頻逐字稿，修正可能的轉錄錯誤。

重要規則：
1. 保持原文的意思和語氣，只修正明顯的錯誤
2. 特別注意佛教專有名詞（如：般若、禪定、菩薩、阿羅漢等）
3. 修正同音字錯誤（如：在→再、做→作、的→得等）
4. 改善標點符號，使語意更清晰
5. 保持原文長度大致相同，不要大幅增減內容
6. 如果不確定，保持原文不變
7. 輸出純文本，不要添加任何說明或標記

原文：
{text}

請直接輸出修正後的文本："""

        # Use chat completion (no structured output needed)
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "你是一位專業的文字校對專家，特別擅長佛教文獻的校對。"},
                {"role": "user", "content": correction_prompt}
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout_secs
        )

        corrected_text = response.choices[0].message.content.strip()
        logger.info(f"   文本修正完成：{len(text)} → {len(corrected_text)} 字符")

        return corrected_text

    except Exception as e:
        logger.warning(f"文本修正失敗，使用原文: {e}")
        return text


# ================================
# Main Processing Function
# ================================
def process_audio_file(audio_file: str, client: OpenAI, system_instruction: str,
                      model_name: str, temperature: float, max_tokens: int,
                      max_context_chars: int, timeout_secs: int,
                      correct_errors: bool = False) -> Optional[AudioOutline]:
    """
    Process a single audio transcript JSON file to extract structured topic outline using LLM.

    This is the main orchestration function that:
    1. Loads audio JSON and builds timestamp mapping
    2. Optionally corrects transcription errors using LLM
    3. Chunks text if needed (based on max_context_chars)
    4. Sends each chunk to LLM for topic extraction
    5. Merges chunk results into final outline

    Supports multiple LLM providers:
    - GPT models (OpenAI): Uses client.beta.chat.completions.parse()
    - DeepSeek/Qwen3 models: Uses chat.completions with JSON mode
    - vLLM local models: Uses beta.chat.completions.parse()

    Args:
        audio_file: Path to audio transcript JSON file
        client: OpenAI-compatible client instance
        system_instruction: System prompt for LLM
        model_name: Model identifier (e.g., "gpt-4", "deepseek-chat")
        temperature: LLM temperature (0.0-1.0)
        max_tokens: Maximum output tokens
        max_context_chars: Max characters per chunk (triggers chunking if exceeded)
        timeout_secs: API timeout in seconds
        correct_errors: If True, use LLM to correct transcription errors before topic extraction

    Returns:
        AudioOutline: Structured outline with topics, or None if processing fails
    """
    try:
        logger.info(f"開始處理音頻文件：{audio_file}")

        # 1) 載入音頻 JSON 並獲取時間戳資訊
        audio_info = load_audio_with_timestamp_info(audio_file)
        logger.info(f"載入完成，總時長 {audio_info['total_duration']:.1f} 秒，{len(audio_info['full_text'])} 字符")

        # Keep original text
        original_text = audio_info['full_text']

        # 2) 可選：修正轉錄錯誤
        corrected_text = ""
        if correct_errors:
            logger.info(f"開始修正轉錄錯誤...")
            corrected_text = correct_transcription_errors(
                text=audio_info['full_text'],
                client=client,
                model_name=model_name,
                temperature=0.3,  # Lower temperature for correction task
                max_tokens=max_tokens,
                timeout_secs=timeout_secs
            )
            # Use corrected text for processing
            audio_info['full_text'] = corrected_text

            # Update segments to use corrected text
            # Split corrected text back into segments (approximate, maintains timestamps)
            corrected_parts = corrected_text.split('\n\n')
            for i, seg in enumerate(audio_info['segments']):
                if i < len(corrected_parts):
                    seg['text'] = corrected_parts[i]
        else:
            # If not correcting, use original text for processing
            corrected_text = original_text

        # 3) 分塊處理
        text_chunks = produce_text_chunks(audio_info, max_context_chars)
        logger.info(f"分成 {len(text_chunks)} 個塊進行處理")

        all_chunk_outlines = []
        audio_title = None

        # 4) 處理每個文本塊
        for chunk in text_chunks:
            chunk_text = chunk['text']
            chunk_num = chunk['chunk_num']
            total_chunks = chunk['total_chunks']

            logger.info(f"處理第 {chunk_num}/{total_chunks} 塊 (時間 {chunk['start_time']:.1f}s-{chunk['end_time']:.1f}s)")

            # 構造提示詞
            prompt = (
                f"請分析以下音頻逐字稿 filename:{os.path.basename(audio_file)} 內容（共 {total_chunks} 部分，這是第 {chunk_num} 部分，對應音頻時間約 {chunk['start_time']:.1f}-{chunk['end_time']:.1f} 秒），"
                f"並以繁體中文輸出所有主要主題（數量不限），含摘要與起訖時間戳。\n\n"
                f"重要：請確保輸出完整的、有效的 JSON 格式，所有字符串都正確終止。\n\n"
                f"【音頻逐字稿】\n{chunk_text}\n\n"
                f"請直接輸出 JSON 格式，不要包含任何其他文字。確保 JSON 完整且語法正確。"
            )

            # Call LLM based on model type
            try:
                # Prepare common parameters
                common_params = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt}
                    ],
                    "timeout": timeout_secs
                }

                # Use max_completion_tokens for newer OpenAI models, max_tokens for others
                # Also skip temperature for gpt-5 models (only support default value of 1)
                if 'gpt-5' in model_name.lower():
                    common_params["max_completion_tokens"] = max_tokens
                    # Don't set temperature for gpt-5 models
                elif 'gpt-4o' in model_name.lower():
                    common_params["max_completion_tokens"] = max_tokens
                    common_params["temperature"] = temperature
                else:
                    common_params["max_tokens"] = max_tokens
                    common_params["temperature"] = temperature

                if 'gpt' in model_name.lower() or 'cpatonn/qwen3' in model_name.lower()\
                    or 'gemini-' in model_name.lower():
                    # Use structured output API with AudioChunkOutline (no full_text)
                    common_params["response_format"] = AudioChunkOutline
                    completion = client.beta.chat.completions.parse(**common_params)
                    chunk_outline = completion.choices[0].message.parsed

                else:
                    # Use JSON mode for other models
                    common_params["response_format"] = {"type": "json_object"}
                    completion = client.chat.completions.create(**common_params)

                    # Parse JSON response
                    raw_json = completion.choices[0].message.content
                    parsed_data = json.loads(raw_json)
                    chunk_outline = AudioChunkOutline(**parsed_data)

                logger.info(f"第 {chunk_num} 塊完成，提取到 {len(chunk_outline.main_topics)} 個主題")

                if audio_title is None:
                    audio_title = chunk_outline.audio_title

                all_chunk_outlines.append(chunk_outline)

            except Exception as e:
                logger.error(f"第 {chunk_num} 塊處理失敗: {e}")
                continue

        if not all_chunk_outlines:
            error_msg = "所有塊處理均失敗"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

        # 5) 合併所有塊的結果
        merged_topics = []
        for outline in all_chunk_outlines:
            merged_topics.extend(outline.main_topics)

        # 6) 去重
        final_topics = deduplicate_topics(merged_topics, similarity_threshold=0.7)

        # 6.5) 提取每個主題對應的文本內容（使用修正後的文本）
        logger.info(f"提取主題對應的文本內容...")
        for topic in final_topics:
            # Extract text from corrected_text by finding segments in timestamp range
            topic.text = extract_text_by_timestamp(
                topic.starting_timestamp,
                topic.ending_timestamp,
                audio_info['segments']
            )

        # 7) 構造最終 AudioOutline（包含 full_text 和 correct_text）
        final_outline = AudioOutline(
            filename=os.path.basename(audio_file),
            audio_title=audio_title or os.path.splitext(os.path.basename(audio_file))[0],
            full_text=original_text,
            correct_text=corrected_text,
            main_topics=final_topics
        )

        logger.info(f"處理完成，最終提取 {len(final_topics)} 個主題")
        return final_outline

    except Exception as e:
        logger.error(f"處理音頻文件失敗 {audio_file}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Re-raise the exception so backup provider can be triggered
        raise


# ================================
# CLI Entry Point
# ================================
def main():
    """Main CLI entry point."""
    load_dotenv()

    parser = argparse.ArgumentParser(description="音頻主題提取工具 (支持 SRT 和 JSON 格式)")
    parser.add_argument('--audio', type=str, required=True, help="音頻轉錄文件路徑 (.srt 或 .json，支持萬用字元)")
    parser.add_argument('--out_dir', type=str, default='audio_outlines', help="輸出目錄")
    parser.add_argument('--provider', type=str,
                       choices=config_manager.get_available_providers(),
                       help="LLM 提供商", default='dashscope')
    parser.add_argument('--provider_backup', type=str,
                       choices=config_manager.get_available_providers(),
                       help="備用 LLM 供應商選擇（當主要供應商失敗時使用）")
    parser.add_argument('--timeout', type=int, default=120, help="API 超時（秒）")
    parser.add_argument('--log_level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help="日誌級別")
    parser.add_argument('--overwrite', action='store_true',
                       help="如果指定，將覆蓋已存在的輸出文件")
    parser.add_argument('--disable_correction', dest='correct_errors', action='store_false', default=True,
                       help="停用 LLM 文本修正功能（默認啟用修正）")
    
    args = parser.parse_args()

    # 設置日誌級別
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # 驗證並獲取供應商配置
    try:
        provider_config = config_manager.get_provider_config(args.provider)
        if not config_manager.validate_config(args.provider):
            logger.error(f"{args.provider} 配置不完整，請檢查 .env 文件")
            return

        logger.info(f"使用供應商: {args.provider or config_manager.default_provider}")
        logger.info(f"模型: {provider_config.model_name}")

        if args.correct_errors:
            logger.info(f"✅ 轉錄錯誤修正: 啟用（將在主題提取前先修正文本）")
        else:
            logger.info(f"⏭️  轉錄錯誤修正: 停用")

    except ValueError as e:
        logger.error(f"配置錯誤: {e}")
        return

    # 驗證並獲取備用供應商配置（如果指定）
    backup_provider_config = None
    backup_client = None
    backup_model_name = None

    if args.provider_backup:
        try:
            backup_provider_config = config_manager.get_provider_config(args.provider_backup)
            if not config_manager.validate_config(args.provider_backup):
                logger.warning(f"備用供應商 {args.provider_backup} 配置不完整，將不使用備用")
            else:
                backup_client = OpenAI(
                    api_key=backup_provider_config.api_key,
                    base_url=backup_provider_config.base_url
                )
                backup_model_name = backup_provider_config.model_name
                logger.info(f"備用供應商已配置: {args.provider_backup} (模型: {backup_model_name})")
        except ValueError as e:
            logger.warning(f"備用供應商配置錯誤: {e}，將不使用備用")

    # 創建 OpenAI 客戶端
    client = OpenAI(
        api_key=provider_config.api_key,
        base_url=provider_config.base_url
    )
    model_name = provider_config.model_name

    # System instruction
    system_instruction = (
        "你是一位專業的音頻內容分析專家。請仔細分析音頻逐字稿內容，"
        "以繁體中文輸出清晰的結構化主題大綱。\n\n"

        "重要規則：\n"
        "1. 輸出必須是完整且有效的 JSON 格式\n"
        "2. 所有字符串必須用雙引號包圍\n"
        "3. 確保所有括號正確閉合\n"
        "4. 沒有未終止的字符串\n"
        "5. 所有輸出必須使用繁體中文\n"
        "6. 不要包含 JSON 之外的任何文字\n\n"

        "對於每個主題，請提供：\n"
        "- topic_title: 主題正式標題\n"
        "- topic_summary: 繁體中文摘要（簡短扼要）\n"
        "- topic_keywords: 關鍵詞列表（陣列格式）\n"
        "- starting_timestamp: 起始時間戳（秒）\n"
        "- ending_timestamp: 結束時間戳（秒）\n\n"

        "輸出格式必須嚴格遵循：\n"
        '{"filename": "文件名", "audio_title": "音頻標題", "main_topics": [{"topic_title": "標題", "topic_summary": "摘要", "topic_keywords": ["關鍵詞1"], "starting_timestamp": 0.0, "ending_timestamp": 120.5}]}'
    )

    # Find audio files
    audio_files = glob.glob(args.audio)
    if not audio_files:
        logger.error(f"未找到匹配的音頻文件: {args.audio}")
        return

    logger.info(f"找到 {len(audio_files)} 個音頻文件待處理")

    # Create output directory with model name subdirectory
    # Format: {out_dir}/{model_name}/
    # Sanitize model name for use in path (replace slashes with underscores)
    safe_model_name = model_name.replace('/', '_').replace('\\', '_')
    model_output_dir = os.path.join(args.out_dir, safe_model_name)
    os.makedirs(model_output_dir, exist_ok=True)

    logger.info(f"輸出目錄: {model_output_dir}")

    # Process each audio file
    successful_count = 0
    for audio_file in audio_files:
        # Generate output filename: {basename}_outline.json
        basename = os.path.splitext(os.path.basename(audio_file))[0]
        output_filename = f"{basename}_outline.json"
        output_path = os.path.join(model_output_dir, output_filename)

        if os.path.exists(output_path) and not args.overwrite:
            logger.info(f"跳過已存在的文件: {output_path}")
            successful_count += 1
            continue

        outline = None

        # Try primary provider
        try:
            logger.info(f"使用主要供應商處理: {args.provider}")
            outline = process_audio_file(
                audio_file=audio_file,
                client=client,
                system_instruction=system_instruction,
                model_name=model_name,
                temperature=provider_config.temperature,
                max_tokens=provider_config.max_tokens,
                max_context_chars=provider_config.max_context_chars,
                timeout_secs=args.timeout,
                correct_errors=args.correct_errors
            )

        except Exception as e:
            logger.error(f"主要供應商處理失敗 {audio_file}: {e}")

            # Try backup provider if available
            if backup_client and backup_provider_config:
                logger.info(f"嘗試使用備用供應商: {args.provider_backup}")
                try:
                    outline = process_audio_file(
                        audio_file=audio_file,
                        client=backup_client,
                        system_instruction=system_instruction,
                        model_name=backup_model_name,
                        temperature=backup_provider_config.temperature,
                        max_tokens=backup_provider_config.max_tokens,
                        max_context_chars=backup_provider_config.max_context_chars,
                        timeout_secs=args.timeout,
                        correct_errors=args.correct_errors
                    )
                    logger.info(f"✅ 備用供應商處理成功")
                except Exception as backup_e:
                    logger.error(f"備用供應商也失敗 {audio_file}: {backup_e}")

        # Save results if successful
        if outline:
            try:
                # Save output
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(outline.model_dump(), f, ensure_ascii=False, indent=2)

                logger.info(f"✅ 已保存: {output_path}")
                successful_count += 1

                # Print summary
                print("\n" + "="*80)
                print(f"音頻: {outline.audio_title}")
                print(f"主題數: {len(outline.main_topics)}")
                print("="*80)
                for i, topic in enumerate(outline.main_topics, 1):
                    print(f"\n{i}. {topic.topic_title}")
                    print(f"   時間: {topic.starting_timestamp:.1f}s - {topic.ending_timestamp:.1f}s")
                    print(f"   摘要: {topic.topic_summary[:100]}...")
                    print(f"   關鍵詞: {', '.join(topic.topic_keywords[:5])}")
            except Exception as save_e:
                logger.error(f"保存失敗 {output_path}: {save_e}")
        else:
            logger.error(f"❌ 所有供應商均失敗，跳過文件: {audio_file}")

    logger.info(f"\n✅ 處理完成！成功: {successful_count}/{len(audio_files)}")
    logger.info(f"輸出目錄: {model_output_dir}")


if __name__ == '__main__':
    main()

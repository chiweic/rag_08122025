#!/usr/bin/env python3
"""
Reconstruct Original Documents from Chunks

This script reconstructs the original full-text documents from chunked JSONL files.
It groups chunks by their source identifier and concatenates them in order.

Supported chunk types:
- Audio chunks (audio_chunks.jsonl) - grouped by audio_id
- Text chunks (text_chunks.jsonl) - grouped by source book/document
- Event chunks (event_chunks.jsonl) - events are typically single items

Usage:
    # Reconstruct audio transcripts
    python reconstruct_from_chunks.py --input chunks/audio_chunks.jsonl --output reconstructed/audio

    # Reconstruct text documents
    python reconstruct_from_chunks.py --input chunks/text_chunks.jsonl --output reconstructed/text --source-key source

    # Export as JSON instead of TXT
    python reconstruct_from_chunks.py --input chunks/audio_chunks.jsonl --output reconstructed/audio --format json

    # Export both formats
    python reconstruct_from_chunks.py --input chunks/audio_chunks.jsonl --output reconstructed/audio --format both

    # Show statistics only (no export)
    python reconstruct_from_chunks.py --input chunks/audio_chunks.jsonl --stats-only

Author: DDM RAG Team
Created: 2025-11-10
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_jsonl(file_path: str) -> List[Dict[str, Any]]:
    """
    Load data from a JSONL file.

    Args:
        file_path: Path to JSONL file

    Returns:
        List of dictionaries, one per line
    """
    data = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError as e:
                logger.warning(f"跳過第 {line_num} 行: {e}")

    logger.info(f"✅ 加載 {len(data)} 個塊")
    return data


def group_chunks_by_source(
    chunks: List[Dict[str, Any]],
    source_key: str = 'audio_id'
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group chunks by their source identifier.

    Args:
        chunks: List of chunk dictionaries
        source_key: Key in metadata to group by (e.g., 'audio_id', 'source')

    Returns:
        Dictionary mapping source_id -> list of chunks
    """
    grouped = defaultdict(list)

    for chunk in chunks:
        metadata = chunk.get('metadata', {})
        source_id = metadata.get(source_key)

        if source_id:
            grouped[source_id].append(chunk)
        else:
            logger.warning(f"塊 {chunk.get('id')} 缺少 metadata.{source_key}")

    logger.info(f"✅ 按 '{source_key}' 分組為 {len(grouped)} 個來源")
    return dict(grouped)


def sort_chunks_by_index(
    chunks: List[Dict[str, Any]],
    index_key: str = 'chunk_index'
) -> List[Dict[str, Any]]:
    """
    Sort chunks by their index within a document.

    Args:
        chunks: List of chunk dictionaries
        index_key: Key in metadata containing the chunk index

    Returns:
        Sorted list of chunks
    """
    def get_index(chunk):
        metadata = chunk.get('metadata', {})
        return metadata.get(index_key, 0)

    return sorted(chunks, key=get_index)


def reconstruct_documents(
    chunks: List[Dict[str, Any]],
    source_key: str = 'audio_id',
    index_key: str = 'chunk_index',
    content_key: str = 'content',
    separator: str = '\n\n'
) -> Dict[str, Dict[str, Any]]:
    """
    Reconstruct original documents from chunks.

    Args:
        chunks: List of chunk dictionaries
        source_key: Metadata key to group chunks by
        index_key: Metadata key containing chunk order
        content_key: Key containing the actual text content
        separator: String to join chunks

    Returns:
        Dictionary mapping source_id -> reconstructed document info
    """
    # Group chunks by source
    grouped = group_chunks_by_source(chunks, source_key=source_key)

    reconstructed = {}

    for source_id, source_chunks in grouped.items():
        # Sort chunks by index
        sorted_chunks = sort_chunks_by_index(source_chunks, index_key=index_key)

        # Concatenate content
        full_text = separator.join([
            chunk.get(content_key, '') for chunk in sorted_chunks
        ])

        # Extract metadata from first chunk
        first_chunk_metadata = sorted_chunks[0].get('metadata', {}) if sorted_chunks else {}

        reconstructed[source_id] = {
            'source_id': source_id,
            'full_text': full_text,
            'chunks': sorted_chunks,
            'metadata': first_chunk_metadata,
            'total_chunks': len(sorted_chunks),
            'total_chars': len(full_text),
            'total_words': len(full_text.replace(' ', ''))  # Approximate for Chinese
        }

    logger.info(f"✅ 重建 {len(reconstructed)} 個文檔")
    return reconstructed


def print_statistics(reconstructed: Dict[str, Dict[str, Any]]):
    """Print statistics about reconstructed documents."""
    logger.info("\n" + "="*80)
    logger.info("重建統計")
    logger.info("="*80)

    total_docs = len(reconstructed)
    total_chunks = sum(doc['total_chunks'] for doc in reconstructed.values())
    total_chars = sum(doc['total_chars'] for doc in reconstructed.values())

    logger.info(f"文檔總數: {total_docs:,}")
    logger.info(f"塊總數: {total_chunks:,}")
    logger.info(f"字符總數: {total_chars:,}")
    logger.info(f"平均每文檔塊數: {total_chunks/total_docs:.1f}")
    logger.info(f"平均每文檔字符數: {total_chars/total_docs:,.0f}")

    # Top 10 longest documents
    logger.info("\n" + "-"*80)
    logger.info("前 10 個最長文檔:")
    logger.info("-"*80)

    sorted_docs = sorted(
        reconstructed.items(),
        key=lambda x: x[1]['total_chars'],
        reverse=True
    )

    for i, (source_id, doc_info) in enumerate(sorted_docs[:10], 1):
        metadata = doc_info['metadata']
        title = metadata.get('audio_title', metadata.get('title', source_id))
        logger.info(
            f"{i}. {title[:50]:<50} "
            f"{doc_info['total_chars']:>8,} 字符, "
            f"{doc_info['total_chunks']:>3} 塊"
        )

    logger.info("="*80)


def export_as_txt(
    reconstructed: Dict[str, Dict[str, Any]],
    output_dir: Path,
    include_metadata: bool = True
):
    """Export reconstructed documents as TXT files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for source_id, doc_info in reconstructed.items():
        metadata = doc_info['metadata']
        title = metadata.get('audio_title', metadata.get('title', source_id))

        # Sanitize filename
        safe_filename = "".join(
            c if c.isalnum() or c in (' ', '-', '_', '.') else '_'
            for c in title
        )
        safe_filename = safe_filename[:100]  # Limit length

        txt_path = output_dir / f"{safe_filename}.txt"

        with open(txt_path, 'w', encoding='utf-8') as f:
            if include_metadata:
                f.write("="*80 + "\n")
                f.write(f"標題: {title}\n")
                f.write(f"ID: {source_id}\n")

                if 'speaker' in metadata:
                    f.write(f"講者: {metadata['speaker']}\n")
                if 'section' in metadata:
                    f.write(f"分段: {metadata['section']}\n")
                if 'audio_url' in metadata:
                    f.write(f"音頻: {metadata['audio_url']}\n")

                f.write(f"總字數: {doc_info['total_chars']:,}\n")
                f.write(f"總片段: {doc_info['total_chunks']}\n")
                f.write("="*80 + "\n\n")

            f.write(doc_info['full_text'])

        logger.info(f"✅ TXT: {txt_path}")


def export_as_json(
    reconstructed: Dict[str, Dict[str, Any]],
    output_dir: Path,
    include_chunks: bool = False
):
    """Export reconstructed documents as JSON files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for source_id, doc_info in reconstructed.items():
        metadata = doc_info['metadata']
        title = metadata.get('audio_title', metadata.get('title', source_id))

        # Sanitize filename
        safe_filename = "".join(
            c if c.isalnum() or c in (' ', '-', '_', '.') else '_'
            for c in title
        )
        safe_filename = safe_filename[:100]

        json_path = output_dir / f"{safe_filename}.json"

        # Prepare export data
        export_data = {
            'source_id': doc_info['source_id'],
            'title': title,
            'full_text': doc_info['full_text'],
            'metadata': doc_info['metadata'],
            'statistics': {
                'total_chunks': doc_info['total_chunks'],
                'total_chars': doc_info['total_chars'],
                'total_words': doc_info['total_words']
            }
        }

        if include_chunks:
            export_data['chunks'] = doc_info['chunks']

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ JSON: {json_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="從塊重建原始文檔"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="輸入 JSONL 文件路徑 (例：chunks/audio_chunks.jsonl)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reconstructed",
        help="輸出目錄 (預設：reconstructed)"
    )
    parser.add_argument(
        "--source-key",
        type=str,
        default="audio_id",
        help="分組依據的元數據鍵 (預設：audio_id)"
    )
    parser.add_argument(
        "--index-key",
        type=str,
        default="chunk_index",
        help="排序依據的元數據鍵 (預設：chunk_index)"
    )
    parser.add_argument(
        "--content-key",
        type=str,
        default="content",
        help="內容文本鍵 (預設：content)"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=['txt', 'json', 'both'],
        default='txt',
        help="輸出格式 (預設：txt)"
    )
    parser.add_argument(
        "--separator",
        type=str,
        default="\n\n",
        help="塊之間的分隔符 (預設：\\n\\n)"
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="TXT 輸出不包含元數據頭"
    )
    parser.add_argument(
        "--include-chunks",
        action="store_true",
        help="JSON 輸出包含原始塊數據"
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="僅顯示統計，不導出文件"
    )

    args = parser.parse_args()

    logger.info("="*80)
    logger.info("文檔重建工具")
    logger.info("="*80)
    logger.info(f"輸入: {args.input}")
    logger.info(f"輸出: {args.output}")
    logger.info(f"格式: {args.format}")
    logger.info(f"分組依據: {args.source_key}")

    # Load chunks
    logger.info("\n[步驟 1/3] 加載塊...")
    chunks = load_jsonl(args.input)

    if not chunks:
        logger.error("❌ 未找到塊數據")
        sys.exit(1)

    # Reconstruct documents
    logger.info("\n[步驟 2/3] 重建文檔...")
    reconstructed = reconstruct_documents(
        chunks=chunks,
        source_key=args.source_key,
        index_key=args.index_key,
        content_key=args.content_key,
        separator=args.separator
    )

    # Print statistics
    print_statistics(reconstructed)

    # Export if not stats-only mode
    if not args.stats_only:
        logger.info("\n[步驟 3/3] 導出文件...")
        output_dir = Path(args.output)

        if args.format in ('txt', 'both'):
            export_as_txt(
                reconstructed,
                output_dir,
                include_metadata=not args.no_metadata
            )

        if args.format in ('json', 'both'):
            export_as_json(
                reconstructed,
                output_dir,
                include_chunks=args.include_chunks
            )

        logger.info(f"\n✅ 完成！文件已保存到: {output_dir}")
    else:
        logger.info("\n✅ 統計完成（未導出文件）")


if __name__ == "__main__":
    main()

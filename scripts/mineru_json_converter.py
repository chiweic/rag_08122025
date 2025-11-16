#!/usr/bin/env python3
"""
MinerU JSON to load_pdf_with_page_info Format Converter

This script converts MinerU JSON output to the same format as load_pdf_with_page_info(),
allowing pdf_topic_detection.py to use MinerU-extracted content as input.

Usage:
    from mineru_json_converter import load_mineru_json

    doc_data = load_mineru_json('mineru_output/zh/document.json')
    # Returns same format as load_pdf_with_page_info():
    # {
    #     'full_text': "...",  # With [PDF_PAGE_N] markers
    #     'pages': [...],      # List of page dicts
    #     'total_pages': N
    # }

Author: DDM RAG Team
Created: 2025-11-15
"""

import json
from pathlib import Path
from typing import Dict, Any, List


def load_mineru_json(json_path: str) -> Dict[str, Any]:
    """
    Load MinerU JSON output and convert to load_pdf_with_page_info format.

    Args:
        json_path: Path to MinerU JSON file

    Returns:
        Dict with keys:
            - 'full_text': Complete document text with page markers (e.g., [PDF_PAGE_1], [PDF_PAGE_2])
            - 'pages': List of page info dicts with keys:
                - 'text': Page text content (without markers)
                - 'page_num': 1-based page number
                - 'start_char': Character position where page starts in full_text
                - 'end_char': Character position where page ends in full_text
            - 'total_pages': Total number of pages

    Raises:
        FileNotFoundError: If JSON file doesn't exist
        ValueError: If JSON structure is invalid
    """
    json_path = Path(json_path)
    if not json_path.exists():
        raise FileNotFoundError(f"MinerU JSON file not found: {json_path}")

    # Load JSON
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract content_list from the first document in results
    content_list = None
    for doc_name, doc_data in data.get('results', {}).items():
        if 'content_list' in doc_data:
            content_list = json.loads(doc_data['content_list'])
            break

    if content_list is None:
        raise ValueError(f"No content_list found in MinerU JSON: {json_path}")

    # Group content blocks by page_idx
    pages_dict = {}
    for block in content_list:
        page_idx = block.get('page_idx', -1)
        if page_idx == -1:
            continue

        if page_idx not in pages_dict:
            pages_dict[page_idx] = []

        # Only include text blocks
        if block.get('type') == 'text':
            text = block.get('text', '')
            if text:
                pages_dict[page_idx].append(text)

    # Build pages list with character positions
    pages = []
    full_text_parts = []
    current_pos = 0

    # Sort page indices to ensure correct order
    sorted_page_indices = sorted(pages_dict.keys())

    for page_idx in sorted_page_indices:
        page_num = page_idx + 1  # Convert 0-indexed to 1-based

        # Add page marker
        page_marker = f"[PDF_PAGE_{page_num}]\n"
        full_text_parts.append(page_marker)
        current_pos += len(page_marker)

        # Combine text blocks for this page
        page_text = '\n'.join(pages_dict[page_idx])

        # Record start position
        start_char = current_pos

        # Add page text
        full_text_parts.append(page_text)
        current_pos += len(page_text)

        # Add newline between pages
        full_text_parts.append('\n')
        current_pos += 1

        # Record end position (before the newline)
        end_char = current_pos - 1

        # Add page info
        pages.append({
            'text': page_text,
            'page_num': page_num,
            'start_char': start_char,
            'end_char': end_char
        })

    # Build full text
    full_text = ''.join(full_text_parts)

    return {
        'full_text': full_text,
        'pages': pages,
        'total_pages': len(pages)
    }


def test_converter():
    """Test the converter with a sample file."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python mineru_json_converter.py <mineru_json_file>")
        sys.exit(1)

    json_path = sys.argv[1]

    print(f"Loading MinerU JSON: {json_path}")
    result = load_mineru_json(json_path)

    print(f"\n{'='*60}")
    print(f"Conversion Results")
    print(f"{'='*60}")
    print(f"Total pages: {result['total_pages']}")
    print(f"Full text length: {len(result['full_text'])} characters")
    print(f"\nFirst 500 characters of full_text:")
    print(result['full_text'][:500])
    print(f"\n{'='*60}")
    print(f"Page Information (first 3 pages)")
    print(f"{'='*60}")

    for page in result['pages'][:3]:
        print(f"\nPage {page['page_num']}:")
        print(f"  - Char range: {page['start_char']}-{page['end_char']}")
        print(f"  - Text length: {len(page['text'])} chars")
        print(f"  - First 100 chars: {page['text'][:100]}")


if __name__ == '__main__':
    test_converter()

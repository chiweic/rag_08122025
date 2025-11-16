#!/usr/bin/env python3
"""
Quick test to verify header removal and page number detection works correctly.

This script loads a PDF with the new header removal preprocessing and shows:
1. Whether headers like "學佛羣疑 18" are being removed
2. What the actual page ranges look like for the first few pages
"""

import pymupdf
from opencc import OpenCC
import re

cc = OpenCC('s2t')  # Simplified to Traditional Chinese

def test_header_removal(pdf_path: str):
    """Test header removal on a PDF file."""

    # Common header/footer patterns (same as in pdf_topic_detection.py)
    header_patterns = [
        r'^[\u4e00-\u9fff]{2,10}\s+\d+\s*\n',  # Chinese title + number at start of page
        r'\n[\u4e00-\u9fff]{2,10}\s+\d+\s*$',  # Chinese title + number at end of page
        r'^\d+\s+[\u4e00-\u9fff]{2,10}\s*\n',  # Number + Chinese title at start
        r'\n\d+\s+[\u4e00-\u9fff]{2,10}\s*$',  # Number + Chinese title at end
    ]

    print(f"Testing header removal on: {pdf_path}")
    print("=" * 80)

    with pymupdf.open(pdf_path) as doc:
        # Test first 15 pages to see the pattern
        for page_num in range(1, min(16, len(doc) + 1)):
            page = doc[page_num - 1]

            # Extract and convert text
            original_text = page.get_text()
            text = cc.convert(original_text)

            # Apply header removal
            cleaned_text = text
            for pattern in header_patterns:
                cleaned_text = re.sub(pattern, '', cleaned_text, flags=re.MULTILINE)

            removed_chars = len(text) - len(cleaned_text)

            # Show first 150 chars of original and cleaned
            original_preview = text[:150].replace('\n', '\\n')
            cleaned_preview = cleaned_text[:150].replace('\n', '\\n')

            print(f"\nPage {page_num}:")
            print(f"  Removed {removed_chars} chars")

            if removed_chars > 0:
                print(f"  ORIGINAL: {original_preview}...")
                print(f"  CLEANED:  {cleaned_preview}...")
            else:
                print(f"  No headers detected")
                print(f"  TEXT: {cleaned_preview}...")

    print("\n" + "=" * 80)
    print("Test complete!")


if __name__ == "__main__":
    test_header_removal("/home/chiweic/repo/rag_08122025/data/05.03.pdf")

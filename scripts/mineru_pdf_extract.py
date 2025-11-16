#!/usr/bin/env python3
"""
MinerU PDF Extraction Tool

This script extracts structured content from PDF files using the MinerU API.
MinerU provides high-quality PDF parsing with support for tables, formulas, and multiple languages.

Features:
- Extract markdown content from PDFs
- Support for tables and mathematical formulas
- Multiple language support (Chinese, English, etc.)
- Batch processing with parallel requests
- Auto-retry on failures
- Progress tracking and logging

Usage:
    # Extract single PDF
    python mineru_pdf_extract.py --pdf document.pdf

    # Extract multiple PDFs (wildcard)
    python mineru_pdf_extract.py --pdf "data/*.pdf"

    # Specify custom output directory
    python mineru_pdf_extract.py --pdf document.pdf --out_dir mineru_output

    # Process with custom page range
    python mineru_pdf_extract.py --pdf document.pdf --start_page 10 --end_page 50

Author: DDM RAG Team
Created: 2025-11-15
"""

import os
import sys
import json
import glob
import logging
import argparse
import requests
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time

# ================================
# Logging Configuration
# ================================
log_file = time.strftime('logs/mineru_pdf_extract_%Y%m%d_%H%M%S.log')
os.makedirs('logs', exist_ok=True)

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
# Language Detection
# ================================
def detect_language(text: str) -> str:
    """
    Detect the primary language of the text based on character analysis.

    Args:
        text: Text content to analyze

    Returns:
        str: Language code - "zh" (Chinese), "en" (English), "zh,en" (mixed), or "unknown"
    """
    if not text or len(text.strip()) < 10:
        return "unknown"

    # Remove markdown formatting, URLs, and common non-text elements
    clean_text = re.sub(r'[#*_`\[\](){}]', '', text)
    clean_text = re.sub(r'https?://\S+', '', clean_text)
    clean_text = re.sub(r'!\[.*?\]\(.*?\)', '', clean_text)  # Remove image markdown

    # Count different character types
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', clean_text))
    english_chars = len(re.findall(r'[a-zA-Z]', clean_text))
    total_chars = chinese_chars + english_chars

    if total_chars == 0:
        return "unknown"

    chinese_ratio = chinese_chars / total_chars
    english_ratio = english_chars / total_chars

    # Determine language based on ratios
    if chinese_ratio > 0.3 and english_ratio > 0.3:
        return "zh,en"  # Mixed content
    elif chinese_ratio > 0.2:
        return "zh"  # Primarily Chinese
    elif english_ratio > 0.5:
        return "en"  # Primarily English
    else:
        return "unknown"


# ================================
# Progress Counter
# ================================
class ProgressCounter:
    """Thread-safe progress counter for parallel processing."""

    def __init__(self, total: int):
        self.total = total
        self.success = 0
        self.failed = 0
        self.lock = Lock()

    def increment_success(self):
        with self.lock:
            self.success += 1

    def increment_failed(self):
        with self.lock:
            self.failed += 1

    def get_progress(self):
        with self.lock:
            return self.success, self.failed, self.success + self.failed


# ================================
# MinerU API Client
# ================================
class MinerUClient:
    """Client for interacting with MinerU PDF parsing API."""

    def __init__(self, base_url: str = "http://area51r5:8000"):
        """
        Initialize MinerU client.

        Args:
            base_url: Base URL of MinerU API server
        """
        self.base_url = base_url.rstrip('/')
        self.parse_endpoint = f"{self.base_url}/file_parse"

    def extract_pdf(
        self,
        pdf_path: str,
        start_page: int = 0,
        end_page: int = 99999,
        lang_list: str = "ch",
        parse_method: str = "auto",
        backend: str = "pipeline",
        table_enable: bool = True,
        formula_enable: bool = True,
        return_md: bool = True,
        return_content_list: bool = True,
        return_middle_json: bool = False,
        return_model_output: bool = False,
        return_images: bool = False,
        response_format_zip: bool = False,
        timeout: int = 300
    ) -> Dict[str, Any]:
        """
        Extract content from a PDF file using MinerU API.

        Args:
            pdf_path: Path to PDF file
            start_page: Starting page number (0-indexed)
            end_page: Ending page number (0-indexed, 99999 for all pages)
            lang_list: Language list (e.g., "ch", "en", "ch,en")
            parse_method: Parsing method ("auto", "ocr", "txt")
            backend: Backend to use ("pipeline" recommended)
            table_enable: Enable table extraction
            formula_enable: Enable formula extraction
            return_md: Return markdown content
            return_content_list: Return structured content list
            return_middle_json: Return intermediate JSON
            return_model_output: Return model output
            return_images: Return extracted images
            response_format_zip: Return as ZIP file
            timeout: Request timeout in seconds

        Returns:
            Dict containing extraction results

        Raises:
            requests.exceptions.RequestException: If API request fails
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # Prepare multipart form data
        files = {
            'files': (
                os.path.basename(pdf_path),
                open(pdf_path, 'rb'),
                'application/pdf'
            )
        }

        data = {
            'start_page_id': str(start_page),
            'end_page_id': str(end_page),
            'lang_list': lang_list,
            'parse_method': parse_method,
            'backend': backend,
            'table_enable': str(table_enable).lower(),
            'formula_enable': str(formula_enable).lower(),
            'return_md': str(return_md).lower(),
            'return_content_list': str(return_content_list).lower(),
            'return_middle_json': str(return_middle_json).lower(),
            'return_model_output': str(return_model_output).lower(),
            'return_images': str(return_images).lower(),
            'response_format_zip': str(response_format_zip).lower(),
            'output_dir': './output',
            'server_url': 'string'
        }

        try:
            response = requests.post(
                self.parse_endpoint,
                files=files,
                data=data,
                timeout=timeout
            )
            response.raise_for_status()

            return response.json()

        finally:
            # Close file handle
            files['files'][1].close()


# ================================
# PDF Processing Functions
# ================================
def process_single_pdf(
    pdf_path: str,
    client: MinerUClient,
    output_dir: str,
    start_page: int,
    end_page: int,
    lang_list: str,
    progress: Optional[ProgressCounter] = None,
    overwrite: bool = False
) -> tuple[str, bool, str]:
    """
    Process a single PDF file with MinerU.

    Args:
        pdf_path: Path to PDF file
        client: MinerU client instance
        output_dir: Output directory for results
        start_page: Starting page number
        end_page: Ending page number
        lang_list: Language list
        progress: Progress counter for tracking
        overwrite: Whether to overwrite existing files

    Returns:
        Tuple of (pdf_path, success, error_message)
    """
    pdf_name = os.path.basename(pdf_path)
    pdf_stem = os.path.splitext(pdf_name)[0]

    # Output path (JSON only)
    json_output = os.path.join(output_dir, f"{pdf_stem}.json")

    # Skip if already processed (unless overwrite)
    if not overwrite and os.path.exists(json_output):
        if progress:
            progress.increment_success()
            success, failed, total = progress.get_progress()
            logger.info(f"⏭️  [{total}/{progress.total}] Skipped (already exists): {pdf_name}")
        else:
            logger.info(f"⏭️  Skipped (already exists): {pdf_name}")
        return (pdf_path, True, "")

    try:
        logger.info(f"🔄 Extracting: {pdf_name}")

        # Call MinerU API
        result = client.extract_pdf(
            pdf_path=pdf_path,
            start_page=start_page,
            end_page=end_page,
            lang_list=lang_list
        )

        # Extract markdown content and detect language
        md_content_text = ""
        if 'results' in result:
            # Navigate to md_content in MinerU response structure
            for doc_name, doc_data in result.get('results', {}).items():
                if 'md_content' in doc_data:
                    md_content_text = doc_data['md_content']
                    break

        # Detect language from markdown content
        detected_language = detect_language(md_content_text) if md_content_text else "unknown"

        # Add language field to result
        result['language'] = detected_language

        # Save JSON result with language field
        with open(json_output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        if progress:
            progress.increment_success()
            success, failed, total = progress.get_progress()
            logger.info(f"✅ [{total}/{progress.total}] Success: {pdf_name} (Language: {detected_language})")
        else:
            logger.info(f"✅ Success: {pdf_name} (Language: {detected_language})")

        return (pdf_path, True, "")

    except Exception as e:
        error_msg = str(e)
        if progress:
            progress.increment_failed()
            success, failed, total = progress.get_progress()
            logger.error(f"❌ [{total}/{progress.total}] Failed: {pdf_name} - {error_msg}")
        else:
            logger.error(f"❌ Failed: {pdf_name} - {error_msg}")

        return (pdf_path, False, error_msg)


def process_pdfs_batch(
    pdf_files: List[str],
    output_dir: str,
    base_url: str,
    start_page: int,
    end_page: int,
    lang_list: str,
    max_workers: int,
    overwrite: bool
) -> None:
    """
    Process multiple PDF files in parallel.

    Args:
        pdf_files: List of PDF file paths
        output_dir: Output directory
        base_url: MinerU API base URL
        start_page: Starting page number
        end_page: Ending page number
        lang_list: Language list
        max_workers: Maximum parallel workers
        overwrite: Whether to overwrite existing files
    """
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"{'='*60}")
    logger.info(f"MinerU PDF Extraction")
    logger.info(f"{'='*60}")
    logger.info(f"Total PDFs: {len(pdf_files)}")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"API endpoint: {base_url}")
    logger.info(f"Page range: {start_page} to {end_page}")
    logger.info(f"Languages: {lang_list}")
    logger.info(f"Max workers: {max_workers}")
    logger.info(f"Overwrite: {overwrite}")
    logger.info(f"{'='*60}\n")

    # Initialize progress counter
    progress = ProgressCounter(total=len(pdf_files))

    # Initialize client
    client = MinerUClient(base_url=base_url)

    # Process PDFs in parallel
    failed_pdfs = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_pdf = {
            executor.submit(
                process_single_pdf,
                pdf_path,
                client,
                output_dir,
                start_page,
                end_page,
                lang_list,
                progress,
                overwrite
            ): pdf_path
            for pdf_path in pdf_files
        }

        # Wait for completion
        for future in as_completed(future_to_pdf):
            pdf_path = future_to_pdf[future]
            try:
                pdf_path, success, error_msg = future.result()
                if not success:
                    failed_pdfs.append((pdf_path, error_msg))
            except Exception as e:
                logger.error(f"Unexpected error for {pdf_path}: {e}")
                failed_pdfs.append((pdf_path, str(e)))

    # Final summary
    success_count, failed_count, _ = progress.get_progress()

    logger.info(f"\n{'='*60}")
    logger.info(f"Extraction complete!")
    logger.info(f"{'='*60}")
    logger.info(f"Total: {len(pdf_files)} PDFs")
    logger.info(f"✅ Successful: {success_count}")
    logger.info(f"❌ Failed: {failed_count}")

    if failed_pdfs:
        logger.info(f"\nFailed PDFs:")
        for pdf_path, error_msg in failed_pdfs:
            logger.info(f"  - {os.path.basename(pdf_path)}: {error_msg}")

    logger.info(f"{'='*60}")


# ================================
# CLI Entry Point
# ================================
def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract structured content from PDFs using MinerU API"
    )

    # Required arguments
    parser.add_argument(
        '--pdf',
        type=str,
        required=True,
        help='PDF file path or wildcard pattern (e.g., "data/*.pdf")'
    )

    # Optional arguments
    parser.add_argument(
        '--out_dir',
        type=str,
        default='mineru_output',
        help='Output directory for extracted content (default: mineru_output)'
    )
    parser.add_argument(
        '--base_url',
        type=str,
        default='http://area51r5:8000',
        help='MinerU API base URL (default: http://area51r5:8000)'
    )
    parser.add_argument(
        '--start_page',
        type=int,
        default=0,
        help='Starting page number (0-indexed, default: 0)'
    )
    parser.add_argument(
        '--end_page',
        type=int,
        default=99999,
        help='Ending page number (0-indexed, default: 99999 for all pages)'
    )
    parser.add_argument(
        '--lang_list',
        type=str,
        default='ch',
        help='Language list: ch (Chinese), en (English), ch,en (both), etc. (default: ch)'
    )
    parser.add_argument(
        '--max_workers',
        type=int,
        default=2,
        help='Maximum parallel workers (default: 2, recommended: 1-4)'
    )
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite existing output files'
    )

    args = parser.parse_args()

    # Find matching PDF files
    pdf_files = glob.glob(args.pdf)

    if not pdf_files:
        logger.error(f"No PDF files found matching: {args.pdf}")
        sys.exit(1)

    # Process PDFs
    process_pdfs_batch(
        pdf_files=pdf_files,
        output_dir=args.out_dir,
        base_url=args.base_url,
        start_page=args.start_page,
        end_page=args.end_page,
        lang_list=args.lang_list,
        max_workers=args.max_workers,
        overwrite=args.overwrite
    )


if __name__ == '__main__':
    main()

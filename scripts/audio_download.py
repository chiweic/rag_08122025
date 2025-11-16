#!/usr/bin/env python3
"""
Audio Download Script

Download audio files from raw_data/audio_links.json and update the JSON with local file paths.

Input: raw_data/audio_links.json
Output: Updated audio_links.json with "downloaded_to" field for each audio file

Structure:
{
  "audios": [
    {
      "category": "...",
      "title": "...",
      "audio_files": [
        {
          "filename": "s01-u01-01",
          "title": "...",
          "url": "https://...",
          "downloaded_to": "/absolute/path/to/file.mp3"  # Added by this script
        }
      ]
    }
  ]
}
"""

import json
import os
import time
import logging
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from urllib.parse import urlparse

# ================================
# Configuration and Logging
# ================================
log_file = time.strftime('logs/audio_download_%Y%m%d_%H%M%S.log')
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
# Thread-Safe Progress Tracking
# ================================
class ProgressCounter:
    def __init__(self, total):
        self.total = total
        self.success = 0
        self.failed = 0
        self.skipped = 0
        self.lock = Lock()

    def increment_success(self):
        with self.lock:
            self.success += 1

    def increment_failed(self):
        with self.lock:
            self.failed += 1

    def increment_skipped(self):
        with self.lock:
            self.skipped += 1

    def get_progress(self):
        with self.lock:
            return self.success, self.failed, self.skipped, self.success + self.failed + self.skipped


# ================================
# Download Functions
# ================================
def download_single_audio(
    audio_file: Dict,
    out_dir: str,
    progress: ProgressCounter,
    overwrite: bool = False
) -> Tuple[str, bool, str, str]:
    """
    Download a single audio file.

    Args:
        audio_file: Audio file dict with filename, title, url
        out_dir: Output directory for audio files
        progress: Progress counter for thread-safe tracking
        overwrite: If True, re-download existing files

    Returns:
        Tuple of (filename, success, local_path, error_message)
    """
    filename = audio_file.get('filename', 'unknown')
    title = audio_file.get('title', 'Unknown')
    url = audio_file.get('url', '')

    if not url:
        progress.increment_failed()
        error_msg = "No URL provided"
        logger.error(f"❌ {filename}: {error_msg}")
        return (filename, False, "", error_msg)

    # Determine file extension from URL
    parsed_url = urlparse(url)
    ext = os.path.splitext(parsed_url.path)[1] or '.mp3'

    # Construct local file path
    local_filename = f"{filename}{ext}"
    local_path = os.path.join(out_dir, local_filename)
    absolute_path = os.path.abspath(local_path)

    # Check if file already exists
    if os.path.exists(local_path) and not overwrite:
        progress.increment_skipped()
        success, failed, skipped, total = progress.get_progress()
        logger.info(f"⏭️  [{total}/{progress.total}] {filename}: Already exists")
        return (filename, True, absolute_path, "")

    try:
        # Download file with requests
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        # Save to file
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        progress.increment_success()
        success, failed, skipped, total = progress.get_progress()
        logger.info(f"✅ [{total}/{progress.total}] {filename}: {title[:40]}")
        return (filename, True, absolute_path, "")

    except requests.exceptions.RequestException as e:
        progress.increment_failed()
        success, failed, skipped, total = progress.get_progress()
        error_msg = f"Download error: {str(e)}"
        logger.error(f"❌ [{total}/{progress.total}] {filename}: {error_msg}")
        return (filename, False, "", error_msg)

    except Exception as e:
        progress.increment_failed()
        success, failed, skipped, total = progress.get_progress()
        error_msg = str(e)
        logger.error(f"❌ [{total}/{progress.total}] {filename}: {error_msg}")
        return (filename, False, "", error_msg)


def download_audios(
    input_json: str = 'raw_data/audio_links.json',
    out_dir: str = 'audio_data',
    overwrite: bool = False,
    max_workers: int = 4
):
    """
    Download all audio files from audio_links.json and update the JSON with local paths.

    Args:
        input_json: Path to audio links JSON file
        out_dir: Output directory for audio files
        overwrite: If True, re-download existing files; if False, skip existing (auto-resume)
        max_workers: Maximum number of parallel downloads (default: 4)
    """
    # Expand user path
    out_dir = os.path.expanduser(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    input_path = Path(input_json)
    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    # Load audio links JSON
    logger.info(f"Loading audio links from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    audios = data.get('audios', [])

    # Count total audio files
    total_files = sum(len(audio['audio_files']) for audio in audios)

    logger.info(f"{'='*60}")
    logger.info(f"Audio Download (Parallel)")
    logger.info(f"{'='*60}")
    logger.info(f"Total audio groups: {len(audios)}")
    logger.info(f"Total audio files: {total_files}")
    logger.info(f"Output directory: {out_dir}")
    logger.info(f"Max parallel workers: {max_workers}")

    if not overwrite:
        logger.info(f"Auto-resume enabled: existing files will be skipped")
    else:
        logger.info(f"Overwrite enabled: all files will be re-downloaded")

    logger.info(f"{'='*60}\n")

    if total_files == 0:
        logger.info("No audio files to download")
        return

    # Initialize progress counter
    progress = ProgressCounter(total=total_files)

    # Collect all audio files with metadata for parallel processing
    tasks = []
    for audio_group in audios:
        for audio_file in audio_group.get('audio_files', []):
            tasks.append((audio_file, audio_group))

    logger.info(f"Starting parallel audio download for {len(tasks)} files...")
    logger.info(f"{'='*60}\n")

    # Use ThreadPoolExecutor for parallel downloads
    failed_files = []
    download_results = {}  # filename -> (success, local_path)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all download tasks
        future_to_audio = {
            executor.submit(download_single_audio, audio_file, out_dir, progress, overwrite): audio_file
            for audio_file, _ in tasks
        }

        # Wait for all tasks to complete
        for future in as_completed(future_to_audio):
            audio_file = future_to_audio[future]
            try:
                filename, success, local_path, error_msg = future.result()
                download_results[filename] = (success, local_path)

                if not success:
                    failed_files.append((filename, error_msg))

            except Exception as e:
                filename = audio_file.get('filename', 'unknown')
                logger.error(f"Unexpected error for {filename}: {e}")
                failed_files.append((filename, str(e)))
                download_results[filename] = (False, "")

    # Update JSON with local paths
    logger.info(f"\n{'='*60}")
    logger.info(f"Updating JSON with local file paths...")
    logger.info(f"{'='*60}\n")

    updated_count = 0
    for audio_group in audios:
        for audio_file in audio_group.get('audio_files', []):
            filename = audio_file.get('filename', '')
            if filename in download_results:
                success, local_path = download_results[filename]
                if success and local_path:
                    audio_file['downloaded_to'] = local_path
                    updated_count += 1

    # Save updated JSON
    output_path = input_path
    logger.info(f"Saving updated JSON to {output_path}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # Final summary
    success_count, failed_count, skipped_count, _ = progress.get_progress()

    logger.info(f"\n{'='*60}")
    logger.info(f"Audio download complete!")
    logger.info(f"{'='*60}")
    logger.info(f"Total files: {total_files}")
    logger.info(f"✅ Downloaded: {success_count}")
    logger.info(f"⏭️  Skipped (already exist): {skipped_count}")
    logger.info(f"❌ Failed: {failed_count}")
    logger.info(f"📝 Updated JSON entries: {updated_count}")
    logger.info(f"Output directory: {out_dir}")
    logger.info(f"Updated JSON: {output_path}")

    if failed_files:
        logger.info(f"\nFailed files:")
        for filename, error_msg in failed_files:
            logger.info(f"  - {filename}: {error_msg}")

    logger.info(f"{'='*60}")


# ================================
# Main Entry Point
# ================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Download audio files from audio_links.json and update with local paths (parallel)"
    )
    parser.add_argument('--input', default='raw_data/audio_links.json',
                       help='Input audio links JSON file (default: raw_data/audio_links.json)')
    parser.add_argument('--out_dir', required=True,
                       help='Output directory for downloaded audio files (required)')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing audio files (default: skip existing and auto-resume)')
    parser.add_argument('--max_workers', type=int, default=4,
                       help='Maximum number of parallel downloads (default: 4, recommended: 2-8)')

    args = parser.parse_args()

    download_audios(
        input_json=args.input,
        out_dir=args.out_dir,
        overwrite=args.overwrite,
        max_workers=args.max_workers
    )

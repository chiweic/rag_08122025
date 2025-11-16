# download using yt_dlp
# 
# 

import yt_dlp
from typing import List, Dict


# ================================
# Helper Functions
# ================================
from pathlib import Path
def load_deduplicated_videos(input_path: Path) -> List[Dict]:
    """
    Load video metadata and filter out duplicates.

    Returns only videos without 'duplication' field (non-duplicates).
    """
    logger.info(f"Loading video metadata from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_videos = data.get('videos', [])
    non_duplicate_videos = [v for v in all_videos if 'duplication' not in v]

    logger.info(f"Total videos: {len(all_videos)}")
    logger.info(f"Non-duplicate videos: {len(non_duplicate_videos)}")
    logger.info(f"Duplicate videos (skipped): {len(all_videos) - len(non_duplicate_videos)}")

    return non_duplicate_videos

import json
from pathlib import Path
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Thread-safe counter for progress tracking
class ProgressCounter:
    def __init__(self, total):
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


def download_single_video(video: Dict, out_dir: str, progress: ProgressCounter) -> tuple[str, bool, str]:
    """
    Download audio for a single video.

    Args:
        video: Video metadata dict with video_id, url, title
        out_dir: Output directory for audio files
        progress: Progress counter for thread-safe tracking

    Returns:
        Tuple of (video_id, success, error_message)
    """
    video_id = video['video_id']
    url = video['url']
    title = video.get('title', 'Unknown')

    ydl_opts = {
        'outtmpl': f'{out_dir}/%(id)s.%(ext)s',
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,  # Suppress yt-dlp output for cleaner logging
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            error_code = ydl.download([url])

        if error_code == 0:
            progress.increment_success()
            success, failed, total = progress.get_progress()
            logger.info(f"✅ [{total}/{progress.total}] {video_id}: {title[:50]}")
            return (video_id, True, "")
        else:
            progress.increment_failed()
            success, failed, total = progress.get_progress()
            error_msg = f"yt-dlp returned error code {error_code}"
            logger.error(f"❌ [{total}/{progress.total}] {video_id}: {error_msg}")
            return (video_id, False, error_msg)

    except Exception as e:
        progress.increment_failed()
        success, failed, total = progress.get_progress()
        error_msg = str(e)
        logger.error(f"❌ [{total}/{progress.total}] {video_id}: {error_msg}")
        return (video_id, False, error_msg)


def extract_audio(input_path: str, out_dir: str, overwrite: bool = False, max_workers: int = 4):
    """
    Extract audio from YouTube videos with parallel downloading.

    Args:
        input_path: Path to video metadata JSON file
        out_dir: Output directory for extracted audio files
        overwrite: If True, re-extract audio for existing files; if False, skip existing (auto-resume)
        max_workers: Maximum number of parallel downloads (default: 4)
    """
    # Expand user path (~/repository/audio_data -> /home/user/repository/audio_data)
    out_dir = os.path.expanduser(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    videos = load_deduplicated_videos(Path(input_path))

    logger.info(f"{'='*60}")
    logger.info(f"YouTube Audio Extraction (Parallel)")
    logger.info(f"{'='*60}")
    logger.info(f"Total videos to process: {len(videos)}")
    logger.info(f"Output directory: {out_dir}")
    logger.info(f"Max parallel workers: {max_workers}")

    # Filter out videos that already have extracted audio (unless overwrite=True)
    if not overwrite:
        videos_to_process = []
        skipped_count = 0

        for video in videos:
            video_id = video['video_id']
            audio_path = os.path.join(out_dir, f"{video_id}.mp3")

            if os.path.exists(audio_path):
                skipped_count += 1
            else:
                videos_to_process.append(video)

        logger.info(f"Auto-resume: Skipped {skipped_count} videos with existing audio")
        logger.info(f"Remaining to extract: {len(videos_to_process)} videos")
        logger.info(f"{'='*60}\n")

        videos = videos_to_process
    else:
        logger.info(f"Overwrite enabled: All {len(videos)} videos will be processed")
        logger.info(f"{'='*60}\n")

    if not videos:
        logger.info("✅ No videos to process - all audio files already exist!")
        return

    logger.info(f"Starting parallel audio extraction for {len(videos)} videos...")
    logger.info(f"{'='*60}\n")

    # Initialize progress counter
    progress = ProgressCounter(total=len(videos))

    # Use ThreadPoolExecutor for parallel downloads
    failed_videos = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all download tasks
        future_to_video = {
            executor.submit(download_single_video, video, out_dir, progress): video
            for video in videos
        }

        # Wait for all tasks to complete
        for future in as_completed(future_to_video):
            video = future_to_video[future]
            try:
                video_id, success, error_msg = future.result()
                if not success:
                    failed_videos.append((video_id, error_msg))
            except Exception as e:
                logger.error(f"Unexpected error for {video.get('video_id', 'unknown')}: {e}")
                failed_videos.append((video.get('video_id', 'unknown'), str(e)))

    # Final summary
    success_count, failed_count, _ = progress.get_progress()

    logger.info(f"\n{'='*60}")
    logger.info(f"Audio extraction complete!")
    logger.info(f"{'='*60}")
    logger.info(f"Total: {len(videos)} videos")
    logger.info(f"✅ Successful: {success_count}")
    logger.info(f"❌ Failed: {failed_count}")

    if failed_videos:
        logger.info(f"\nFailed videos:")
        for video_id, error_msg in failed_videos:
            logger.info(f"  - {video_id}: {error_msg}")

    logger.info(f"{'='*60}")

import time
import os
import logging
# ================================
# Configuration and Logging
# ================================
log_file = time.strftime('logs/youtube_audio_extract_%Y%m%d_%H%M%S.log')
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

if __name__ == "__main__":


    import argparse

    parser = argparse.ArgumentParser(description="YT Audio extraction using yt_dlp - Batch process videos from metadata JSON (parallel)")
    parser.add_argument('--input', default='raw_data/video_metadata_records_dedup.json',
                       help='Input video metadata JSON file with list of videos to process')
    parser.add_argument('--out_dir', default='~/repository/audio_data',
                       help='Output directory for extracted audio files')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing audio files (default: skip existing and auto-resume)')
    parser.add_argument('--max_workers', type=int, default=4,
                       help='Maximum number of parallel downloads (default: 4, recommended: 2-8)')

    args = parser.parse_args()

    extract_audio(
        input_path=args.input,
        out_dir=args.out_dir,
        overwrite=args.overwrite,
        max_workers=args.max_workers
    )
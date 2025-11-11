#!/usr/bin/env python3
"""
Video Deduplication Script

Remove duplicate videos based on title name matching.
Problem: Videos from https://www.youtube.com/@DDMTV01/videos may have duplicates
         where some titles contain "DVD" at the end while others don't.

Rationale:
1. Find list of videos that have "DVD" at end of title
2. For each DVD video, check if a non-DVD version exists (matching title without DVD)
3. If match found, mark the nono-DVD version with {"duplication": "video_id_of_dvd_version"}

Input: raw_data/video_metadata_records.json
Output: raw_data/video_metadata_records_dedup.json
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def normalize_title(title: str) -> str:
    """
    Normalize title for comparison by:
    1. Removing "DVD" suffix (with optional whitespace)
    2. Stripping whitespace
    3. Converting to lowercase for case-insensitive comparison

    Args:
        title: Original video title

    Returns:
        Normalized title for comparison
    """
    # Remove DVD suffix (case-insensitive, with optional whitespace before)
    normalized = re.sub(r'\s*DVD\s*$', '', title, flags=re.IGNORECASE)
    return normalized.strip().lower()


def find_duplicates(videos: List[Dict]) -> Dict[str, str]:
    """
    Find duplicate videos where non-DVD versions match DVD versions.

    Args:
        videos: List of video records

    Returns:
        Dictionary mapping non-DVD video_id -> DVD video_id for duplicates
    """
    # Build index of normalized titles to video info
    # normalized_title -> [(video_id, original_title, has_dvd), ...]
    title_index: Dict[str, List[tuple]] = defaultdict(list)

    for video in videos:
        video_id = video['video_id']
        title = video['title']
        normalized = normalize_title(title)
        has_dvd = title.strip().upper().endswith('DVD')

        title_index[normalized].append((video_id, title, has_dvd))

    # Find duplicates
    duplicates = {}

    for normalized_title, video_list in title_index.items():
        if len(video_list) < 2:
            continue

        # Separate DVD and non-DVD versions
        dvd_videos = [v for v in video_list if v[2]]  # has_dvd=True
        non_dvd_videos = [v for v in video_list if not v[2]]  # has_dvd=False

        if not dvd_videos or not non_dvd_videos:
            continue

        # Mark non-DVD versions as duplicates of the first DVD version
        # (DVD version is the "canonical" one to keep)
        canonical_dvd_video_id = dvd_videos[0][0]

        for non_dvd_video_id, non_dvd_title, _ in non_dvd_videos:
            duplicates[non_dvd_video_id] = canonical_dvd_video_id
            logger.info(f"Found duplicate: '{non_dvd_title}' -> DVD video_id: {canonical_dvd_video_id}")

    return duplicates


def mark_duplicates(videos: List[Dict], duplicates: Dict[str, str]) -> List[Dict]:
    """
    Add duplication field to non-DVD videos that have DVD duplicates.

    Args:
        videos: List of video records
        duplicates: Dictionary mapping non-DVD video_id -> DVD video_id

    Returns:
        Updated list of video records with duplication field added
    """
    updated_videos = []

    for video in videos:
        video_id = video['video_id']

        if video_id in duplicates:
            # This is a non-DVD version with a DVD duplicate
            video['duplication'] = duplicates[video_id]

        updated_videos.append(video)

    return updated_videos


def main():
    """Main execution function."""
    # Input/output paths
    input_path = Path(__file__).parent.parent / "raw_data" / "video_metadata_records.json"
    output_path = Path(__file__).parent.parent / "raw_data" / "video_metadata_records_dedup.json"

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    # Load video data
    logger.info(f"Loading video data from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    videos = data.get('videos', [])
    logger.info(f"Loaded {len(videos)} videos")

    # Analyze DVD distribution
    dvd_count = sum(1 for v in videos if v['title'].strip().upper().endswith('DVD'))
    non_dvd_count = len(videos) - dvd_count
    logger.info(f"Videos with DVD suffix: {dvd_count}")
    logger.info(f"Videos without DVD suffix: {non_dvd_count}")

    # Find duplicates
    logger.info("Finding duplicates...")
    duplicates = find_duplicates(videos)
    logger.info(f"Found {len(duplicates)} duplicate non-DVD videos")

    # Mark duplicates
    logger.info("Marking duplicates...")
    updated_videos = mark_duplicates(videos, duplicates)

    # Update data structure
    data['videos'] = updated_videos

    # Save output
    logger.info(f"Saving deduplicated data to {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info("✅ Deduplication complete!")
    logger.info(f"Output saved to: {output_path}")

    # Summary statistics
    marked_count = sum(1 for v in updated_videos if 'duplication' in v)
    logger.info(f"\nSummary:")
    logger.info(f"  Total videos: {len(updated_videos)}")
    logger.info(f"  Marked as duplicates: {marked_count}")
    logger.info(f"  Unique videos: {len(updated_videos) - marked_count}")


if __name__ == "__main__":
    main()

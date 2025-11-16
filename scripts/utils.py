# utilities from scripts
import logging
import json
from pathlib import Path
from typing import List, Dict 
# ================================
# Helper Functions
# ================================

logger = logging.getLogger(__name__)

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


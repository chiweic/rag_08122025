#!/usr/bin/env python3
"""
Video Speech-to-Text (STT) Processing Script

This script processes non-duplicate videos from video_metadata_records_dedup.json,
downloads/transcribes them using LLM-based STT, and produces timestamped JSON output.

Process:
1. Load deduplicated video metadata
2. Filter videos without duplication field (non-duplicates)
3. For each video:
   - Send video URL to STT service (LLM or dedicated STT API)
   - Get timestamped transcription
   - Save to JSON with segments format

Output Format:
    {
        "video_id": "abc123",
        "url": "https://www.youtube.com/watch?v=...",
        "title": "Video Title",
        "channel": "Channel Name",
        "transcribed_at": "2025-11-11T12:00:00",
        "segments": [
            {"start": 0.0, "end": 5.2, "text": "Transcribed text here"},
            {"start": 5.2, "end": 10.8, "text": "More transcribed text"},
            ...
        ]
    }

Usage:
    # Process all non-duplicate videos
    python video_stt.py

    # Process with specific provider
    python video_stt.py --provider openai

    # Process limited number for testing
    python video_stt.py --limit 5

    # Resume from specific video ID
    python video_stt.py --resume abc123

    # Use backup provider
    python video_stt.py --provider dashscope --provider_backup openai

Note: Currently uses OpenAI Whisper API for STT. For other providers,
      you may need to implement custom STT logic.

Input: raw_data/video_metadata_records_dedup.json
Output: video_transcripts/{video_id}.json

Author: DDM RAG Team
Created: 2025-11-11
"""

import os
import sys
import json
import logging
import argparse
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from dotenv import load_dotenv

# For downloading YouTube videos
# For OpenAI Whisper API
from openai import OpenAI

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from llm_config import config_manager

load_dotenv()

# ================================
# Configuration and Logging
# ================================
log_file = time.strftime('logs/video_stt_%Y%m%d_%H%M%S.log')
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
# Helper Functions
# ================================

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


def transcribe_with_whisper(audio_file: Path, client: OpenAI) -> Optional[List[Dict]]:
    """
    Transcribe audio file using OpenAI Whisper API.

    Args:
        audio_file: Path to audio file
        client: OpenAI client instance

    Returns:
        List of segments with timestamps, or None if failed
        Format: [{"start": 0.0, "end": 5.2, "text": "..."}, ...]
    """
    try:
        logger.info(f"Transcribing {audio_file.name} with Whisper API...")

        with open(audio_file, 'rb') as f:
            # Call Whisper API with timestamp granularity
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )

        # Extract segments
        segments = []
        if hasattr(transcript, 'segments') and transcript.segments:
            for seg in transcript.segments:
                segments.append({
                    "start": seg['start'],
                    "end": seg['end'],
                    "text": seg['text'].strip()
                })
        else:
            # Fallback if segments not available
            logger.warning("No segments in Whisper response, creating single segment")
            segments.append({
                "start": 0.0,
                "end": 0.0,
                "text": transcript.text
            })

        logger.info(f"✅ Transcription complete: {len(segments)} segments")
        return segments

    except Exception as e:
        logger.error(f"Whisper transcription failed for {audio_file}: {e}")
        return None


def process_video(
    video: Dict,
    output_dir: Path,
    temp_dir: Path,
    client: OpenAI,
    skip_existing: bool = True
) -> bool:
    """
    Process a single video: download, transcribe, save JSON.

    Args:
        video: Video metadata dict
        output_dir: Directory to save transcript JSON
        temp_dir: Directory for temporary audio files
        client: OpenAI client for Whisper API
        skip_existing: Skip if transcript already exists

    Returns:
        True if successful, False otherwise
    """
    video_id = video['video_id']
    url = video['url']
    title = video['title']

    output_file = output_dir / f"{video_id}.json"

    # Skip if already processed
    if skip_existing and output_file.exists():
        logger.info(f"⏭️  Skipping {video_id} (already exists)")
        return True

    logger.info(f"🎬 Processing: {title}")
    logger.info(f"   Video ID: {video_id}")
    logger.info(f"   URL: {url}")

    # Step 1: Download audio
    audio_file = download_youtube_audio(url, temp_dir)
    if not audio_file:
        logger.error(f"❌ Failed to download audio for {video_id}")
        return False

    # Step 2: Transcribe
    segments = transcribe_with_whisper(audio_file, client)
    if not segments:
        logger.error(f"❌ Failed to transcribe {video_id}")
        # Clean up audio file
        audio_file.unlink(missing_ok=True)
        return False

    # Step 3: Save transcript JSON
    transcript_data = {
        "video_id": video_id,
        "url": url,
        "title": title,
        "channel": video.get('channel', ''),
        "channel_url": video.get('channel_url', ''),
        "transcribed_at": datetime.now().isoformat(),
        "segments": segments
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(transcript_data, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ Saved transcript: {output_file}")

    # Clean up audio file
    audio_file.unlink(missing_ok=True)
    logger.info(f"🗑️  Cleaned up: {audio_file}")

    return True

from google import genai
from google.genai import types
from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """Single segment of transcribed audio with timestamps."""
    start: float = Field(description="Start time in seconds (floating point number)")
    end: float = Field(description="End time in seconds (floating point number)")
    text: str = Field(description="Transcribed text in Traditional Chinese for this segment")


class VideoTranscript(BaseModel):
    """Complete video transcript with timestamped segments."""
    segments: List[TranscriptSegment] = Field(
        description="List of transcript segments with timestamps, ordered chronologically"
    )


def clean_segments(segments: List[Dict]) -> List[Dict]:
    """
    Clean up transcription segments by removing duplicates and merging short fragments.

    Args:
        segments: List of segments with start, end, text fields

    Returns:
        Cleaned list of segments
    """
    if not segments:
        return []

    cleaned = []
    prev_text = None
    accumulated_text = []
    accumulated_start = None

    for seg in segments:
        text = seg.get('text', '').strip()
        start = seg.get('start', 0.0)
        end = seg.get('end', 0.0)

        # Skip empty segments
        if not text:
            continue

        # Skip exact duplicates
        if text == prev_text:
            logger.warning(f"Skipping duplicate segment at {start}s: '{text}'")
            continue

        # Check if segment is too short (< 3 characters, likely a fragment)
        # questionable, as we may have quite a few of those
        #if len(text) < 3:
        #    logger.warning(f"Found short fragment at {start}s: '{text}'")
            # Accumulate short fragments
        #    if accumulated_start is None:
        #        accumulated_start = start
        #    accumulated_text.append(text)
        #    continue

        # If we have accumulated fragments, merge them with current segment
        if accumulated_text:
            text = ''.join(accumulated_text) + text
            start = accumulated_start
            accumulated_text = []
            accumulated_start = None

        cleaned.append({
            'start': start,
            'end': end,
            'text': text
        })
        prev_text = text

    # Handle any remaining accumulated text
    if accumulated_text and cleaned:
        # Merge with last segment
        cleaned[-1]['text'] += ''.join(accumulated_text)
        cleaned[-1]['end'] = segments[-1].get('end', cleaned[-1]['end'])

    logger.info(f"Cleaned segments: {len(segments)} -> {len(cleaned)} (removed {len(segments) - len(cleaned)} duplicates/fragments)")
    return cleaned


def transcribe_video_gemini(
    video: Dict,
    client: genai.Client,
    provider_config: Any,
    output_dir: Path,
    prompt: str,
    overwrite: bool = False
) -> bool:
    """
    Transcribe a single video using Gemini with structured output.

    Args:
        video: Video metadata dict with video_id, url, title
        client: Gemini client instance
        provider_config: Provider configuration with model_name, temperature
        output_dir: Directory to save transcript JSON
        prompt: Transcription prompt
        overwrite: If True, overwrite existing transcript files; if False, skip existing files

    Returns:
        True if successful, False otherwise
    """
    video_id = video['video_id']
    url = video['url']
    title = video.get('title', '')

    output_file = output_dir / f"{video_id}.json"

    # Skip if already processed (unless overwrite=True)
    if output_file.exists() and not overwrite:
        logger.info(f"⏭️  Skipping {video_id} - already transcribed (use --overwrite to reprocess)")
        return True

    logger.info(f"🎬 Processing: {title}")
    logger.info(f"   Video ID: {video_id}")
    logger.info(f"   URL: {url}")

    try:
        # Use structured output with Pydantic schema
        response = client.models.generate_content(
            model=provider_config.model_name,
            contents=[
                types.Content(
                    parts=[
                        types.Part(file_data=types.FileData(file_uri=url)),
                        types.Part(text=prompt)
                    ]
                )
            ],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": VideoTranscript.model_json_schema(),
                "temperature": provider_config.temperature,
                "max_output_tokens": provider_config.max_tokens
            },
        )
        
        # Check if response was truncated due to token limit
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason

            # finish_reason values: STOP=1, MAX_TOKENS=3, SAFETY=2, RECITATION=4, OTHER=5
            if finish_reason == 3:  # MAX_TOKENS
                logger.warning(f"⚠️  Response truncated due to max_output_tokens limit")
                logger.warning(f"   Video may be too long for single transcription")
                # Save partial response for debugging
                debug_file = output_dir / f"{video_id}_truncated.txt"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logger.warning(f"   Partial response saved to: {debug_file}")

        # Parse response using Pydantic model
        try:
            transcript = VideoTranscript.model_validate_json(response.text)
        except Exception as parse_error:
            # Save raw response for debugging
            debug_file = output_dir / f"{video_id}_parse_error.txt"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(f"Error: {parse_error}\n\n")
                f.write("Raw response:\n")
                f.write(response.text)
            logger.error(f"❌ JSON parsing failed. Raw response saved to: {debug_file}")
            raise

        # Convert Pydantic models to dict for processing
        segments = [seg.model_dump() for seg in transcript.segments]

        logger.info(f"✅ Parsed {len(segments)} segments")

        # Clean segments
        cleaned_segments = clean_segments(segments)

        # Save to file
        output_data = {
            'video_id': video_id,
            'url': url,
            'title': title,
            'channel': video.get('channel', ''),
            'transcribed_at': datetime.now().isoformat(),
            'transcription_model': provider_config.model_name,
            'temperature': provider_config.temperature,
            'segments': cleaned_segments
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Saved: {output_file}")

        # Statistics
        total_duration = cleaned_segments[-1]['end'] if cleaned_segments else 0
        logger.info(f"   Segments: {len(cleaned_segments)}, Duration: {total_duration/60:.1f} min")

        return True

    except Exception as e:
        logger.error(f"❌ Failed to transcribe {video_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def process_videos_batch(
    input_json: str = 'raw_data/video_metadata_records_dedup.json',
    output_dir: str = 'video_transcripts',
    provider: str = 'gemini',
    limit: Optional[int] = None,
    overwrite: bool = False
):
    """
    Process all non-duplicate videos from video metadata JSON.

    Args:
        input_json: Path to deduplicated video metadata JSON
        output_dir: Directory to save transcript JSON files
        provider: LLM provider to use (default: gemini)
        limit: Maximum number of videos to process (for testing)
        overwrite: If True, overwrite existing transcript files; if False, skip existing files (auto-resume)
    """
    # Setup
    input_path = Path(input_json)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    # Load video metadata
    logger.info(f"Loading video metadata from {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    all_videos = data.get('videos', [])

    # Filter non-duplicate videos
    non_duplicate_videos = [v for v in all_videos if 'duplication' not in v]

    logger.info(f"Total videos: {len(all_videos)}")
    logger.info(f"Non-duplicate videos: {len(non_duplicate_videos)}")
    logger.info(f"Duplicate videos (skipped): {len(all_videos) - len(non_duplicate_videos)}")

    # Handle limit
    if limit:
        non_duplicate_videos = non_duplicate_videos[:limit]
        logger.info(f"Limiting to first {limit} videos")

    if not non_duplicate_videos:
        logger.error("No videos to process")
        return

    # Log resume behavior
    if not overwrite:
        logger.info(f"Auto-resume enabled: existing transcripts will be skipped")
    else:
        logger.info(f"Overwrite enabled: all videos will be reprocessed")

    
    # gemini can take yourube url as input
    if provider == 'gemini':

        # Initialize Gemini client
        provider_config = config_manager.get_provider_config(provider)
        client = genai.Client(api_key=provider_config.api_key)

        logger.info(f"Using model: {provider_config.model_name}")
        logger.info(f"Temperature: {provider_config.temperature}")

        # Transcription prompt
        prompt = """你是一位專業的語音辨識專家。請仔細聆聽影片內容，生成準確且高品質的繁體中文逐字稿。

**重要提示**：此影片包含硬編碼字幕（hardcoded subtitles），你可以參考這些字幕來確保轉錄的準確性，但請務必依照以下要求重新組織和輸出：

轉錄要求：
1. **完整轉錄**：逐字記錄所有說話內容，不要遺漏或省略任何字句。可參考影片中的硬編碼字幕確保用字準確。
2. **自然分段**：每個片段應包含完整的句子或語意單元（約 5-15 秒長度）。不要機械性地複製字幕的分段方式，而是根據語意和自然語調重新分段。
3. **避免重複**：不要產生重複的片段，確保每段文字都是獨特且有意義的內容。即使字幕出現重複，也只記錄一次。
4. **語意完整**：每個片段的文字應該是完整的語句，不要在句子中間斷開。
5. **準確時間戳**：確保時間戳連續且不重疊，精確對應說話時間（而非字幕顯示時間）。
6. **文字修正**：如果發現字幕有錯字或不通順之處，請根據聲音內容修正為正確的繁體中文。

請將影片中的所有說話內容轉錄為帶有時間戳的繁體中文文字。利用硬編碼字幕提高準確度，但要重新組織為自然、完整的語意片段，不要產生只有幾個字的碎片。"""

        # Process videos
        logger.info(f"{'='*60}")
        logger.info(f"Starting batch video transcription: {len(non_duplicate_videos)} videos")
        logger.info(f"{'='*60}")

        success_count = 0
        failure_count = 0

        for idx, video in enumerate(non_duplicate_videos, 1):
            logger.info(f"\n[{idx}/{len(non_duplicate_videos)}] Processing video...")

            try:
                success = transcribe_video_gemini(
                    video=video,
                    client=client,
                    provider_config=provider_config,
                    output_dir=output_path,
                    prompt=prompt,
                    overwrite=overwrite
                )

                if success:
                    success_count += 1
                else:
                    failure_count += 1

            except Exception as e:
                logger.error(f"Unexpected error processing video {video.get('video_id', 'unknown')}: {e}")
                failure_count += 1

            # Progress update every 10 videos
            if idx % 10 == 0:
                logger.info(f"\n{'='*60}")
                logger.info(f"Progress: {idx}/{len(non_duplicate_videos)} videos processed")
                logger.info(f"Success: {success_count}, Failures: {failure_count}")
                logger.info(f"{'='*60}\n")

    elif provider == 'dashscope':

        from funasr import AutoModel
        model_name='paraformer-zh'
        model = AutoModel(model=model_name, #odel_revision="v2.0.4",
                  vad_model="fsmn-vad", #vad_model_revision="v2.0.4",
                  punc_model="ct-punc-c", #punc_model_revision="v2.0.4",
                  # spk_model="cam++", spk_model_revision="v2.0.2",
                  )
        
        logger.info(f"Using FunASR model: paraformer-zh v2.0.4")

        success_count = 0
        failure_count = 0

        for idx, video in enumerate(non_duplicate_videos, 1):
            logger.info(f"\n[{idx}/{len(non_duplicate_videos)}] Processing video...")

            video_id = video['video_id']
            title = video.get('title', '')

            # Check if transcript already exists
            output_file = output_path / f"{video_id}.json"
            if output_file.exists() and not overwrite:
                logger.info(f"⏭️  Skipping {video_id} - already transcribed (use --overwrite to reprocess)")
                success_count += 1
                continue

            logger.info(f"🎬 Processing: {title}")
            logger.info(f"   Video ID: {video_id}")

            audio_extracted_path = os.path.join('/home/chiweic/repository/audio_data', video['video_id']+'.mp3')
            logger.info(f"   Audio path: {audio_extracted_path}")

            if not Path(audio_extracted_path).exists():
                logger.error(f"❌ Audio file does not exist: {audio_extracted_path}")
                failure_count += 1
                continue

            try:
                # FunASR transcription
                logger.info(f"   Transcribing with FunASR...")
                res = model.generate(
                    input=audio_extracted_path,
                    batch_size_s=300,
                    sentence_timestamp=True,  # Enable sentence-level timestamps with text
                    #hotword='魔搭'
                )

                # Parse FunASR result
                # FunASR returns: [{'key': 'audio_file', 'text': '...', 'timestamp': [[start_ms, end_ms, 'word'], ...]}]
                if not res or len(res) == 0:
                    logger.error(f"❌ FunASR returned empty result")
                    failure_count += 1
                    continue

                result = res[0]
                full_text = result.get('text', '')
                timestamps = result.get('timestamp', [])
                sentence_info = result.get('sentence_info', [])  # FunASR returns sentence_info with sentence_timestamp=True

                logger.info(f"✅ Transcription complete: {len(full_text)} characters")

                # Debug: Log what keys are in the result
                logger.info(f"   Result keys: {list(result.keys())}")
                logger.info(f"   Has sentence_info: {len(sentence_info) if sentence_info else 0}")
                logger.info(f"   Has timestamps: {len(timestamps) if timestamps else 0}")

                # Debug: Show first sentence if available
                if sentence_info and len(sentence_info) > 0:
                    logger.info(f"   First sentence sample: {sentence_info[0]}")

                # Convert FunASR timestamp format to our segment format
                segments = []

                # Try sentence-level timestamps first (if available)
                if sentence_info and len(sentence_info) > 0:
                    logger.info(f"   Using sentence-level timestamps ({len(sentence_info)} sentences)")
                    for sent in sentence_info:
                        if isinstance(sent, dict):
                            start = sent.get('start', 0) / 1000.0  # Convert ms to seconds
                            end = sent.get('end', 0) / 1000.0
                            text = sent.get('text', '')
                            if text:
                                segments.append({
                                    'start': start,
                                    'end': end,
                                    'text': text
                                })

                # Otherwise use word-level timestamps
                elif timestamps and len(timestamps) > 0:
                    logger.info(f"   Using word-level timestamps ({len(timestamps)} words)")
                    for ts in timestamps:
                        # FunASR timestamp format: [start_ms, end_ms] (no text)
                        start_ms, end_ms = ts[0], ts[1]
                        # Timestamps only contain timing, text needs to be extracted separately
                        segments.append({
                                'start': start_ms / 1000.0,  # Convert ms to seconds
                                'end': end_ms / 1000.0,
                                'text': ''  # Text will be populated later
                            })

                # If we have word-level segments without text, we need to extract text from full_text
                # For now, create a single segment with the full text
                if not segments or (segments and not segments[0].get('text')):
                    logger.warning(f"⚠️  No sentence-level timestamps available, creating single segment with full text")
                    segments = [{
                        'start': 0.0,
                        'end': 0.0,
                        'text': full_text
                    }]

                logger.info(f"   Parsed {len(segments)} segments")

                # Clean segments (remove duplicates, merge fragments)
                cleaned_segments = clean_segments(segments)

                # Save to file in same format as Gemini
                output_data = {
                    'video_id': video_id,
                    'url': video.get('url', ''),
                    'title': title,
                    'channel': video.get('channel', ''),
                    'transcribed_at': datetime.now().isoformat(),
                    'transcription_model': 'funasr-paraformer-zh-v2.0.4',
                    'segments': cleaned_segments,
                    'full_text': full_text
                }

                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)

                logger.info(f"✅ Saved: {output_file}")

                # Statistics
                if cleaned_segments:
                    total_duration = cleaned_segments[-1]['end'] if cleaned_segments[-1]['end'] > 0 else 0
                    logger.info(f"   Segments: {len(cleaned_segments)}, Duration: {total_duration/60:.1f} min")

                success_count += 1

            except Exception as e:
                logger.error(f"❌ Failed to transcribe {video_id}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                failure_count += 1

            # Progress update every 10 videos
            if idx % 10 == 0:
                logger.info(f"\n{'='*60}")
                logger.info(f"Progress: {idx}/{len(non_duplicate_videos)} videos processed")
                logger.info(f"Success: {success_count}, Failures: {failure_count}")
                logger.info(f"{'='*60}\n")



    # Final summary
    logger.info(f"{'='*60}")
    logger.info(f"Batch Video Transcription Complete!")
    logger.info(f"{'='*60}")
    logger.info(f"Total videos processed: {len(non_duplicate_videos)}")
    logger.info(f"Successful: {success_count}")
    logger.info(f"Failed: {failure_count}")
    logger.info(f"Output directory: {output_path}")
    logger.info(f"Log file: {log_file}")
    logger.info(f"{'='*60}\n")


if __name__ == "__main__":
    
    import argparse

    parser = argparse.ArgumentParser(description="Convert audio to text using local LLM/ASR API")
    
    # user will need to build up json that contain multiple
    # {
    # "audios": [
    #    {audio_src: absoulete path of the audio}
    #    {srt: absoulete path on the target output in srt format}
    # ]
    # }

    parser.add_argument('--input', default='raw_data/video_metadata_records_dedup.json',
                       help='Input video metadata JSON file with list of videos to process')
    args = parser.parse_args()

    #process_videos_batch(
    #    input_json=args.input,
    #    output_dir=args.out_dir,
    #    provider=args.provider,
    #    limit=args.limit,
    #    overwrite=args.overwrite
    #)


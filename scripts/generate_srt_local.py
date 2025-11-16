#!/usr/bin/env python3
"""
Generate SRT from a JSON mapping of {audio_src, srt_tgt}.

Local-only version:
- whisper_local (openai-whisper)
- faster_whisper (faster-whisper, CTranslate2 backend)

Usage:
  python generate_srt_local.py \
      --mapping audio_srt_map.json \
      --provider faster_whisper \
      --language zh
"""

import argparse
import json
import os
from dataclasses import dataclass
from typing import List, Optional
import time
import logging

# ================================
# Configuration and Logging
# ================================
log_file = time.strftime('logs/generate_srt_local_%Y%m%d_%H%M%S.log')
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

# -------------------------
# Data structures
# -------------------------

@dataclass
class Segment:
    start: float
    end: float
    text: str


# -------------------------
# Helpers
# -------------------------

def seconds_to_srt_time(t: float) -> str:
    if t < 0:
        t = 0.0
    hours = int(t // 3600)
    minutes = int((t % 3600) // 60)
    seconds = int(t % 60)
    millis = int(round((t - int(t)) * 1000))
    return f"{hours:02}:{minutes:02}:{seconds:02},{millis:03}"


def write_srt(segments: List[Segment], srt_path: str):
    os.makedirs(os.path.dirname(srt_path), exist_ok=True)
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{seconds_to_srt_time(seg.start)} --> {seconds_to_srt_time(seg.end)}\n")
            f.write(seg.text.strip() + "\n\n")


# -------------------------
# Local STT: openai-whisper
# -------------------------

class WhisperLocalTranscriber:
    def __init__(self, model_size="small"):
        try:
            import whisper
        except ImportError:
            raise RuntimeError("Install: pip install openai-whisper")

        logger.info(f"Loading Whisper model ({model_size})...")
        self.model = whisper.load_model(model_size)
        logger.info(f"✅ Whisper model loaded")

    def transcribe(self, audio_path: str, language: Optional[str]) -> List[Segment]:
        result = self.model.transcribe(audio_path, language=language)

        segments = [
            Segment(float(s["start"]), float(s["end"]), s["text"])
            for s in result.get("segments", [])
        ]

        if not segments:
            segments = [Segment(0, 0, result.get("text", ""))]

        return segments


# -------------------------
# Local STT: faster-whisper
# -------------------------

class FasterWhisperTranscriber:
    def __init__(self, model_size="medium"):
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise RuntimeError("Install: pip install faster-whisper")

        logger.info(f"Loading Faster-Whisper model ({model_size})...")
        self.model = WhisperModel(model_size, device="auto", compute_type="auto")
        logger.info(f"✅ Faster-Whisper model loaded")

    def transcribe(self, audio_path: str, language: Optional[str]) -> List[Segment]:
        segments_raw, _ = self.model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True
        )

        segments = []
        for seg in segments_raw:
            segments.append(Segment(seg.start, seg.end, seg.text))

        return segments


# -------------------------
# Local STT: funasr - from Alibaba
# -------------------------

class FunASRTranscriber:
    def __init__(self, model_size=None):
        """
        Initialize FunASR transcriber.

        Note: model_size parameter is ignored for FunASR as it uses a fixed model (paraformer-zh).
        """
        try:
            from funasr import AutoModel
        except ImportError:
            raise RuntimeError("Install: pip install funasr")

        logger.info(f"Loading FunASR model (paraformer-zh v2.0.4)...")
        # paraformer-zh is a multi-functional asr model
        # use vad, punc, spk or not as you need
        self.model = AutoModel(
            model="paraformer-zh",
            model_revision="v2.0.4",
            vad_model="fsmn-vad",
            vad_model_revision="v2.0.4",
            punc_model="ct-punc-c",
            punc_model_revision="v2.0.4",
            # spk_model="cam++", spk_model_revision="v2.0.2",
        )
        logger.info(f"✅ FunASR model loaded")

    def transcribe(self, audio_path: str, language: Optional[str]) -> List[Segment]:
        res = self.model.generate(
            input=audio_path,
            batch_size_s=300,
            sentence_timestamp=True,
            #hotword='魔搭'
        )

        result = res[0]
        sentence_info = result.get('sentence_info', [])  # FunASR returns sentence_info with sentence_timestamp=True
        timestamps = result.get('timestamp', [])

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
                            segments.append(Segment(start, end, text))

                return segments
            else:
                return []
        else:
            return []


# -------------------------
# Provider dispatcher
# -------------------------

def get_transcriber(provider: str, model_size: str):
    """
    Initialize transcriber model once.

    Args:
        provider: "whisper_local", "faster_whisper", or "funasr"
        model_size: Model size string (e.g., "small", "medium", "large")

    Returns:
        Transcriber instance with transcribe() method
    """
    if provider == "whisper_local":
        return WhisperLocalTranscriber(model_size=model_size)
    elif provider == "faster_whisper":
        return FasterWhisperTranscriber(model_size=model_size)
    elif provider == "funasr":
        return FunASRTranscriber(model_size=model_size)
    else:
        raise ValueError(f"Unknown provider: {provider}")


# -------------------------
# Main
# -------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mapping", default='audio_to_srt_map.json')
    parser.add_argument("--provider", choices=["whisper_local", "faster_whisper", "funasr"], default='funasr')
    parser.add_argument("--language", default="zh")
    parser.add_argument("--model", default=None, help="override model name")
    args = parser.parse_args()

    # Load mapping file
    with open(args.mapping, "r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info(f"{'='*60}")
    logger.info(f"SRT Generation - Local Transcription")
    logger.info(f"{'='*60}")
    logger.info(f"Provider: {args.provider}")
    logger.info(f"Language: {args.language}")
    logger.info(f"Total files: {len(data)}")
    logger.info(f"{'='*60}\n")

    # Determine model size based on provider
    if args.provider == "whisper_local":
        model_size = args.model or "small"
    elif args.provider == "faster_whisper":
        model_size = args.model or "medium"
    elif args.provider == "funasr":
        # FunASR uses fixed model (paraformer-zh), model_size is ignored
        model_size = None
        if args.model:
            logger.warning(f"⚠️  FunASR uses fixed model 'paraformer-zh', ignoring --model argument: {args.model}")
    else:
        model_size = "medium"

    # Initialize transcriber ONCE (this loads the model)
    transcriber = get_transcriber(args.provider, model_size)

    logger.info(f"Processing {len(data)} audio files...\n")

    success_count = 0
    failed_count = 0

    # Process all audio files with the same model instance
    for idx, item in enumerate(data, start=1):
        audio = item["audio_src"]
        srt = item["srt_tgt"]

        try:
            logger.info(f"[{idx}/{len(data)}] Transcribing: {audio}")

            # Use the same transcriber instance for all files
            segments = transcriber.transcribe(audio, args.language)

            write_srt(segments, srt)
            logger.info(f"✅ [{idx}/{len(data)}] Saved: {srt}\n")
            success_count += 1

        except Exception as e:
            logger.error(f"❌ [{idx}/{len(data)}] Failed: {audio}")
            logger.error(f"   Error: {e}\n")
            failed_count += 1

    logger.info(f"{'='*60}")
    logger.info(f"SRT generation complete!")
    logger.info(f"{'='*60}")
    logger.info(f"Total: {len(data)} files")
    logger.info(f"✅ Successful: {success_count}")
    logger.info(f"❌ Failed: {failed_count}")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()

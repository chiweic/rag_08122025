#!/usr/bin/env python3
"""
Podcast Audio Generation Tool - Multi-Provider TTS Integration

This script converts podcast scripts (JSON) into audio files using multiple TTS providers.
It supports multi-speaker dialogue with configurable voice profiles.

Supported TTS Providers:
- DashScope (Alibaba Cloud CosyVoice-v2)
- Google Gemini (Text-to-Speech with multi-speaker support)
- ElevenLabs (High-quality neural TTS)

Key Features:
- Multi-provider TTS support (DashScope, Gemini, ElevenLabs)
- Multi-speaker voice mapping
- Audio segment generation with metadata
- Batch processing for multiple podcast episodes
- Gemini: Multi-speaker batch generation
- DashScope/ElevenLabs: Individual segment generation

Usage:
    # Generate audio using DashScope (default)
    python llm_podcast_audio.py --podcast podcasts/05.03.pdf.podcast.json

    # Generate audio using Gemini (multi-speaker)
    python llm_podcast_audio.py --podcast podcasts/05.03.pdf.podcast.json --provider gemini

    # Generate audio using ElevenLabs
    python llm_podcast_audio.py --podcast podcasts/05.03.pdf.podcast.json --provider elevenlabs

    # Batch process all podcasts
    python llm_podcast_audio.py --podcast "podcasts/*.podcast.json" --provider dashscope

    # Custom output directory
    python llm_podcast_audio.py --podcast podcasts/05.03.pdf.podcast.json --out_dir audio_output

Author: DDM RAG Team
Last Updated: 2025-11-11
"""
import os
import sys
import logging
import json
import glob
import argparse
import time
import base64
from typing import List, Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from abc import ABC, abstractmethod

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv()

# ================================
# Logging Configuration
# ================================
log_file = time.strftime('logs/podcast_audio_%Y%m%d_%H%M%S.log')
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

# Provider-specific imports (conditional)
try:
    import dashscope
    from dashscope.audio.tts_v2 import SpeechSynthesizer, AudioFormat
    DASHSCOPE_AVAILABLE = True
except ImportError:
    DASHSCOPE_AVAILABLE = False
    logger.warning("DashScope SDK not available. Install with: pip install dashscope")

try:
    from google import genai
    from google.genai import types
    import wave
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    logger.warning("Google Gemini SDK not available. Install with: pip install google-generativeai")

try:
    from elevenlabs.client import ElevenLabs
    ELEVENLABS_AVAILABLE = True
except ImportError:
    ELEVENLABS_AVAILABLE = False
    logger.warning("ElevenLabs SDK not available. Install with: pip install elevenlabs")

# ================================
# Configuration
# ================================

# API Keys
DASHSCOPE_API_KEY = os.getenv('DASHSCOPE_API_KEY', '')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY', '')

# Voice Profiles for different providers
DASHSCOPE_VOICE_PROFILES = {
    "anchor": "longanwen",         # 龍安雯 - Anchor voice (主持人)
    "guest": "longxiaochun"        # 龍小春 - Professional clear voice (來賓)
}

GEMINI_VOICE_PROFILES = {
    "anchor": "Zephyr",            # Calm, professional voice
    "guest": "Charon"                # Warm, authoritative voice
}

ELEVENLABS_VOICE_PROFILES = {
    "anchor": "9lHjugDhwqoxA5MhX0az",  # Professional female voice
    "guest": "BrbEfHMQu0fyclQR7lfh"   # Clear male voice
}

# Audio segment naming
SEGMENT_FILENAME_TEMPLATE = "{episode_id}_seg_{segment_num:03d}_{speaker}.{format}"

# ================================
# TTS Provider Abstract Class
# ================================

class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    def generate_audio(self, text: str, voice: str, output_path: str) -> bool:
        """
        Generate audio from text.

        Args:
            text: Text to synthesize
            voice: Voice identifier
            output_path: Path to save audio file

        Returns:
            bool: True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_voice_profiles(self) -> Dict[str, str]:
        """Get voice profile mappings for this provider."""
        pass

    @abstractmethod
    def get_audio_format(self) -> str:
        """Get audio format extension (e.g., 'mp3', 'wav')."""
        pass

    def supports_multi_speaker(self) -> bool:
        """Check if provider supports multi-speaker batch generation."""
        return False

    def generate_episode_audio(self, podcast_data: Dict[str, Any], output_path: str) -> bool:
        """
        Generate full episode audio with multi-speaker support (optional).

        Args:
            podcast_data: Complete podcast episode data
            output_path: Path to save the full episode audio file

        Returns:
            bool: True if successful, False otherwise
        """
        return False  # Default: not supported

# ================================
# DashScope TTS Provider
# ================================

class DashScopeTTSProvider(TTSProvider):
    """DashScope (Alibaba Cloud) TTS provider implementation."""

    def __init__(self, api_key: str):
        """Initialize DashScope provider."""
        if not DASHSCOPE_AVAILABLE:
            raise ImportError("DashScope SDK not available. Install with: pip install dashscope")

        self.api_key = api_key
        dashscope.api_key = api_key
        self.model = "cosyvoice-v2"
        self.audio_format = AudioFormat.MP3_22050HZ_MONO_256KBPS
        self.volume = 50
        self.speech_rate = 1.0
        self.pitch_rate = 1.0

    def generate_audio(self, text: str, voice: str, output_path: str) -> bool:
        """Generate audio using DashScope TTS API v2."""
        try:
            logger.info(f"生成音頻片段: {output_path[:50]}... (voice: {voice})")

            # Create SpeechSynthesizer instance with parameters
            synthesizer = SpeechSynthesizer(
                model=self.model,
                voice=voice,
                format=self.audio_format,
                volume=self.volume,
                speech_rate=self.speech_rate,
                pitch_rate=self.pitch_rate
            )

            # Call TTS API with text
            audio_data = synthesizer.call(text)

            # Check if synthesis was successful
            if audio_data is not None:
                # Save audio to file
                with open(output_path, 'wb') as f:
                    f.write(audio_data)

                logger.info(f"   ✅ 已保存: {output_path}")
                return True
            else:
                logger.error(f"   ❌ TTS 合成失敗: No audio data returned")
                return False

        except Exception as e:
            logger.error(f"   ❌ 生成音頻片段時發生錯誤: {e}")
            return False

    def get_voice_profiles(self) -> Dict[str, str]:
        """Get DashScope voice profiles."""
        return DASHSCOPE_VOICE_PROFILES

    def get_audio_format(self) -> str:
        """Get audio format extension."""
        return "mp3"


# ================================
# Gemini TTS Provider
# ================================

class GeminiTTSProvider(TTSProvider):
    """Google Gemini TTS provider implementation with multi-speaker support."""

    def __init__(self, api_key: str):
        """Initialize Gemini provider."""
        if not GEMINI_AVAILABLE:
            raise ImportError("Google Gemini SDK not available. Install with: pip install google-generativeai")

        self.api_key = api_key
        self.client = genai.Client(api_key=api_key)

    def supports_multi_speaker(self) -> bool:
        """Gemini supports multi-speaker batch generation."""
        return True

    def generate_episode_audio(self, podcast_data: Dict[str, Any], output_path: str) -> bool:
        """Generate full episode audio using Gemini's multi-speaker TTS (2-step process)."""
        try:
            logger.info(f"🎙️ 使用 Gemini 多人對話模式生成完整音頻: {output_path}")

            # Get speaker names from podcast data
            speakers = podcast_data.get('speakers', {})
            anchor_name = speakers.get('anchor', '主持人')
            guest_name = speakers.get('guest', '來賓')

            # Configure multi-speaker voice mapping
            voice_profiles = self.get_voice_profiles()

            logger.info(f"   配置多人對話：{anchor_name} ({voice_profiles['anchor']}) + {guest_name} ({voice_profiles['guest']})")

            # Step 1: Use Gemini LLM to format the conversation transcript
            logger.info(f"   步驟 1/2: 格式化對話腳本...")
            conversation_script = self._build_conversation_script(podcast_data)

            # Generate formatted transcript using Gemini LLM
            transcript_prompt = f"""Format the following podcast conversation for TTS.
The speakers are {anchor_name} and {guest_name}.
Output the conversation in this exact format:
{anchor_name}: [their dialogue]
{guest_name}: [their dialogue]

Conversation to format:
{conversation_script}"""

            transcript_response = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=transcript_prompt
            )

            formatted_transcript = transcript_response.text
            logger.info(f"   ✅ 腳本格式化完成 ({len(formatted_transcript)} 字符)")

            # Step 2: Generate speech with multi-speaker config
            logger.info(f"   步驟 2/2: 生成多人對話音頻...")
            tts_response = self.client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=formatted_transcript,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=[
                                types.SpeakerVoiceConfig(
                                    speaker=anchor_name,
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                            voice_name=voice_profiles['anchor']
                                        )
                                    )
                                ),
                                types.SpeakerVoiceConfig(
                                    speaker=guest_name,
                                    voice_config=types.VoiceConfig(
                                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                            voice_name=voice_profiles['guest']
                                        )
                                    )
                                ),
                            ]
                        )
                    )
                )
            )

            # Extract audio data
            audio_data = tts_response.candidates[0].content.parts[0].inline_data.data

            # Save as WAV file
            self._save_wav_file(output_path, audio_data)

            logger.info(f"   ✅ 已保存完整音頻: {output_path}")
            return True

        except Exception as e:
            logger.error(f"   ❌ Gemini 多人對話生成失敗: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _build_conversation_script(self, podcast_data: Dict[str, Any]) -> str:
        """Build conversation script with speaker labels for multi-speaker TTS."""
        speakers = podcast_data.get('speakers', {})
        anchor_name = speakers.get('anchor', '主持人')
        guest_name = speakers.get('guest', '來賓')

        script_lines = []

        # Add opening
        for turn in podcast_data.get('opening', []):
            speaker_role = turn.get('speaker')
            speaker_label = anchor_name if speaker_role == 'anchor' else guest_name
            content = turn.get('content', '')
            script_lines.append(f"{speaker_label}: {content}")

        # Add segments
        for segment in podcast_data.get('segments', []):
            for turn in segment.get('dialogue', []):
                speaker_role = turn.get('speaker')
                speaker_label = anchor_name if speaker_role == 'anchor' else guest_name
                content = turn.get('content', '')
                script_lines.append(f"{speaker_label}: {content}")

        # Add closing
        for turn in podcast_data.get('closing', []):
            speaker_role = turn.get('speaker')
            speaker_label = anchor_name if speaker_role == 'anchor' else guest_name
            content = turn.get('content', '')
            script_lines.append(f"{speaker_label}: {content}")

        # Join with TTS instruction prefix
        conversation = "\n".join(script_lines)
        return f"TTS the following conversation between {anchor_name} and {guest_name}:\n{conversation}"

    def _save_wav_file(self, filename: str, pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2):
        """Save PCM audio data as WAV file."""
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm_data)

    def generate_audio(self, text: str, voice: str, output_path: str) -> bool:
        """Generate audio using Google Gemini TTS API (single speaker fallback)."""
        try:
            logger.info(f"生成音頻片段 (Gemini): {output_path[:50]}... (voice: {voice})")

            # Use Gemini's text-to-speech model
            response = self.client.models.generate_content(
                model="gemini-2.0-flash-tts",
                contents=f"<|SPEECH|>{text}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice
                            )
                        )
                    )
                )
            )

            # Extract audio data
            audio_data = response.candidates[0].content.parts[0].inline_data.data

            # Save as WAV file
            self._save_wav_file(output_path, audio_data)

            logger.info(f"   ✅ 已保存 (Gemini): {output_path}")
            return True

        except Exception as e:
            logger.error(f"   ❌ Gemini 生成音頻片段時發生錯誤: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_voice_profiles(self) -> Dict[str, str]:
        """Get Gemini voice profiles."""
        return GEMINI_VOICE_PROFILES

    def get_audio_format(self) -> str:
        """Get audio format extension."""
        return "wav"


# ================================
# ElevenLabs TTS Provider
# ================================

class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs TTS provider implementation."""

    def __init__(self, api_key: str):
        """Initialize ElevenLabs provider."""
        if not ELEVENLABS_AVAILABLE:
            raise ImportError("ElevenLabs SDK not available. Install with: pip install elevenlabs")

        self.api_key = api_key
        self.client = ElevenLabs(
            api_key=api_key,
            base_url="https://api.elevenlabs.io"
        )
        self.model = "eleven_multilingual_v2"  # Supports multiple languages including Chinese
        self.output_format = "mp3_44100_128"

    def generate_audio(self, text: str, voice: str, output_path: str) -> bool:
        """Generate audio using ElevenLabs TTS API."""
        try:
            logger.info(f"生成音頻片段 (ElevenLabs): {output_path[:50]}... (voice_id: {voice[:8]}...)")

            # Generate audio using ElevenLabs text_to_speech API
            audio_generator = self.client.text_to_speech.convert(
                voice_id=voice,
                output_format=self.output_format,
                text=text,
                model_id=self.model
            )

            # Save audio to file
            # The convert method returns a generator of audio chunks
            with open(output_path, 'wb') as f:
                for chunk in audio_generator:
                    f.write(chunk)

            logger.info(f"   ✅ 已保存 (ElevenLabs): {output_path}")
            return True

        except Exception as e:
            logger.error(f"   ❌ ElevenLabs 生成音頻片段時發生錯誤: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def get_voice_profiles(self) -> Dict[str, str]:
        """Get ElevenLabs voice profiles."""
        return ELEVENLABS_VOICE_PROFILES

    def get_audio_format(self) -> str:
        """Get audio format extension."""
        return "mp3"


# ================================
# Provider Factory
# ================================

def create_tts_provider(provider_name: str) -> TTSProvider:
    """
    Create TTS provider instance based on provider name.

    Args:
        provider_name: Provider name ('dashscope', 'gemini', or 'elevenlabs')

    Returns:
        TTSProvider: Provider instance

    Raises:
        ValueError: If provider is not supported or API key is missing
    """
    provider_name = provider_name.lower()

    if provider_name == "dashscope":
        if not DASHSCOPE_API_KEY:
            raise ValueError("DASHSCOPE_API_KEY not found in environment variables")
        return DashScopeTTSProvider(DASHSCOPE_API_KEY)

    elif provider_name == "gemini":
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        return GeminiTTSProvider(GEMINI_API_KEY)

    elif provider_name == "elevenlabs":
        if not ELEVENLABS_API_KEY:
            raise ValueError("ELEVENLABS_API_KEY not found in environment variables")
        return ElevenLabsTTSProvider(ELEVENLABS_API_KEY)

    else:
        raise ValueError(f"Unsupported TTS provider: {provider_name}. Choose 'dashscope', 'gemini', or 'elevenlabs'")


# ================================
# Legacy function for backward compatibility
# ================================

def generate_audio_segment(
    text: str,
    voice: str,
    output_path: str,
    provider: TTSProvider = None,
    **kwargs
) -> bool:
    """
    Legacy wrapper function for backward compatibility.
    Uses provider-based architecture internally.

    Args:
        text: Text content to synthesize
        voice: Voice identifier
        output_path: Path to save the audio file
        provider: TTSProvider instance (if None, creates DashScope provider)
        **kwargs: Additional arguments (ignored for compatibility)

    Returns:
        bool: True if generation successful, False otherwise
    """
    if provider is None:
        # Default to DashScope for backward compatibility
        try:
            provider = create_tts_provider("dashscope")
        except ValueError as e:
            logger.error(f"Failed to create default provider: {e}")
            return False

    return provider.generate_audio(text, voice, output_path)


def process_podcast_episode(
    podcast_path: str,
    output_dir: str,
    tts_provider: TTSProvider
) -> bool:
    """
    Process a single podcast episode JSON and generate all audio segments.

    Args:
        podcast_path: Path to podcast JSON file
        output_dir: Directory to save audio segments
        tts_provider: TTSProvider instance to use for audio generation

    Returns:
        bool: True if all segments generated successfully, False otherwise

    Processing Steps:
        1. Load podcast JSON
        2. Create episode-specific output directory
        3. Check if provider supports multi-speaker batch generation
        4a. If yes: Generate full episode audio in one call
        4b. If no: Generate audio for each dialogue turn separately
        5. Save metadata JSON with segment info
    """
    voice_profiles = tts_provider.get_voice_profiles()
    audio_format = tts_provider.get_audio_format()
    try:
        logger.info(f"開始處理播客: {podcast_path}")

        # Load podcast JSON
        with open(podcast_path, 'r', encoding='utf-8') as f:
            podcast_data = json.load(f)

        episode_title = podcast_data.get('episode_title', 'Unknown Episode')
        logger.info(f"   集標題: {episode_title}")

        # Create episode-specific output directory
        episode_id = Path(podcast_path).stem  # e.g., "05.03.pdf.podcast"
        episode_output_dir = os.path.join(output_dir, episode_id)
        os.makedirs(episode_output_dir, exist_ok=True)

        # Check if provider supports multi-speaker batch generation
        if tts_provider.supports_multi_speaker():
            logger.info(f"   ✨ 使用多人對話批量生成模式")
            return _process_episode_batch(podcast_data, episode_id, episode_output_dir, tts_provider, audio_format)
        else:
            logger.info(f"   📝 使用逐段生成模式")
            return _process_episode_segments(podcast_data, episode_id, episode_output_dir, tts_provider, voice_profiles, audio_format)

    except Exception as e:
        logger.error(f"❌ 處理播客時發生錯誤 {podcast_path}: {e}")
        return False


def _process_episode_batch(
    podcast_data: Dict[str, Any],
    episode_id: str,
    episode_output_dir: str,
    tts_provider: TTSProvider,
    audio_format: str
) -> bool:
    """Process episode using multi-speaker batch generation."""
    try:
        # Generate full episode audio in one call
        full_audio_path = os.path.join(episode_output_dir, f"{episode_id}_full_episode.{audio_format}")

        success = tts_provider.generate_episode_audio(podcast_data, full_audio_path)

        if success:
            # Save metadata
            metadata = {
                "episode_id": episode_id,
                "episode_title": podcast_data.get('episode_title', ''),
                "episode_summary": podcast_data.get('episode_summary', ''),
                "speakers": podcast_data.get('speakers', {}),
                "generation_mode": "multi_speaker_batch",
                "full_audio_file": f"{episode_id}_full_episode.{audio_format}"
            }

            metadata_path = os.path.join(episode_output_dir, f"{episode_id}_metadata.json")
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)

            logger.info(f"✅ 播客處理完成: {episode_id}")
            logger.info(f"   完整音頻: {full_audio_path}")
            return True
        else:
            logger.error(f"❌ 批量生成失敗")
            return False

    except Exception as e:
        logger.error(f"❌ 批量處理時發生錯誤: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def _process_episode_segments(
    podcast_data: Dict[str, Any],
    episode_id: str,
    episode_output_dir: str,
    tts_provider: TTSProvider,
    voice_profiles: Dict[str, str],
    audio_format: str
) -> bool:
    """Process episode by generating audio for each segment separately."""
    try:
        # Track all generated segments
        all_segments_metadata = []
        segment_counter = 0

        # Process opening dialogue
        logger.info(f"   處理開場白 ({len(podcast_data.get('opening', []))} 輪對話)")
        for turn in podcast_data.get('opening', []):
            segment_counter += 1
            speaker_role = turn.get('speaker', 'anchor')
            speaker_name = turn.get('speaker_name', '')
            content = turn.get('content', '')

            # Map speaker role to voice
            voice = voice_profiles.get(speaker_role, voice_profiles['anchor'])

            # Generate output filename
            output_filename = SEGMENT_FILENAME_TEMPLATE.format(
                episode_id=episode_id,
                segment_num=segment_counter,
                speaker=speaker_role,
                format=audio_format
            )
            output_path = os.path.join(episode_output_dir, output_filename)

            # Generate audio segment
            success = tts_provider.generate_audio(
                text=content,
                voice=voice,
                output_path=output_path
            )

            if success:
                all_segments_metadata.append({
                    "segment_num": segment_counter,
                    "section": "opening",
                    "speaker_role": speaker_role,
                    "speaker_name": speaker_name,
                    "voice": voice,
                    "content": content,
                    "audio_file": output_filename
                })
            else:
                logger.warning(f"   ⚠️  片段 {segment_counter} 生成失敗，跳過")

            # Rate limiting: pause between requests
            time.sleep(0.5)

        # Process main segments
        logger.info(f"   處理主要段落 ({len(podcast_data.get('segments', []))} 個段落)")
        for seg_idx, segment in enumerate(podcast_data.get('segments', []), 1):
            segment_title = segment.get('segment_title', f'Segment {seg_idx}')
            logger.info(f"      段落 {seg_idx}: {segment_title}")

            for turn in segment.get('dialogue', []):
                segment_counter += 1
                speaker_role = turn.get('speaker', 'anchor')
                speaker_name = turn.get('speaker_name', '')
                content = turn.get('content', '')

                # Map speaker role to voice
                voice = voice_profiles.get(speaker_role, voice_profiles['anchor'])

                # Generate output filename
                output_filename = SEGMENT_FILENAME_TEMPLATE.format(
                    episode_id=episode_id,
                    segment_num=segment_counter,
                    speaker=speaker_role,
                    format=audio_format
                )
                output_path = os.path.join(episode_output_dir, output_filename)

                # Generate audio segment
                success = tts_provider.generate_audio(
                    text=content,
                    voice=voice,
                    output_path=output_path
                )

                if success:
                    all_segments_metadata.append({
                        "segment_num": segment_counter,
                        "section": f"segment_{seg_idx}",
                        "segment_title": segment_title,
                        "speaker_role": speaker_role,
                        "speaker_name": speaker_name,
                        "voice": voice,
                        "content": content,
                        "audio_file": output_filename
                    })
                else:
                    logger.warning(f"   ⚠️  片段 {segment_counter} 生成失敗，跳過")

                # Rate limiting: pause between requests
                time.sleep(0.5)

        # Process closing dialogue
        logger.info(f"   處理結尾 ({len(podcast_data.get('closing', []))} 輪對話)")
        for turn in podcast_data.get('closing', []):
            segment_counter += 1
            speaker_role = turn.get('speaker', 'anchor')
            speaker_name = turn.get('speaker_name', '')
            content = turn.get('content', '')

            # Map speaker role to voice
            voice = voice_profiles.get(speaker_role, voice_profiles['anchor'])

            # Generate output filename
            output_filename = SEGMENT_FILENAME_TEMPLATE.format(
                episode_id=episode_id,
                segment_num=segment_counter,
                speaker=speaker_role,
                format=audio_format
            )
            output_path = os.path.join(episode_output_dir, output_filename)

            # Generate audio segment
            success = tts_provider.generate_audio(
                text=content,
                voice=voice,
                output_path=output_path
            )

            if success:
                all_segments_metadata.append({
                    "segment_num": segment_counter,
                    "section": "closing",
                    "speaker_role": speaker_role,
                    "speaker_name": speaker_name,
                    "voice": voice,
                    "content": content,
                    "audio_file": output_filename
                })
            else:
                logger.warning(f"   ⚠️  片段 {segment_counter} 生成失敗，跳過")

            # Rate limiting: pause between requests
            time.sleep(0.5)

        # Save metadata JSON
        metadata = {
            "episode_id": episode_id,
            "episode_title": episode_title,
            "episode_summary": podcast_data.get('episode_summary', ''),
            "speakers": podcast_data.get('speakers', {}),
            "total_segments": segment_counter,
            "successful_segments": len(all_segments_metadata),
            "segments": all_segments_metadata
        }

        metadata_path = os.path.join(episode_output_dir, f"{episode_id}_metadata.json")
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ 播客處理完成: {episode_id}")
        logger.info(f"   總片段數: {segment_counter}")
        logger.info(f"   成功生成: {len(all_segments_metadata)}")
        logger.info(f"   音頻目錄: {episode_output_dir}")

        return len(all_segments_metadata) > 0

    except Exception as e:
        logger.error(f"❌ 處理播客時發生錯誤 {podcast_path}: {e}")
        return False


# ================================
# Main Entry Point
# ================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="播客音頻生成工具（多供應商 TTS）")
    parser.add_argument("--podcast", type=str, required=True,
                       help="播客 JSON 檔案路徑或通配符模式（例如 podcasts/*.podcast.json）")
    parser.add_argument("--out_dir", type=str, default="podcast_audio",
                       help="輸出目錄 (預設：podcast_audio)")
    parser.add_argument("--provider", type=str, default="dashscope",
                       choices=["dashscope", "gemini", "elevenlabs"],
                       help="TTS 供應商選擇 (預設：dashscope)")
    parser.add_argument("--log_level", type=str, default="INFO",
                       choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                       help="日誌級別")

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create output directory
    os.makedirs(args.out_dir, exist_ok=True)
    logger.info(f"輸出目錄: {args.out_dir}")
    logger.info(f"TTS 供應商: {args.provider}")

    # Create TTS provider
    try:
        tts_provider = create_tts_provider(args.provider)
        logger.info(f"✅ 成功初始化 {args.provider.upper()} TTS 供應商")
        logger.info(f"   音頻格式: {tts_provider.get_audio_format()}")
        logger.info(f"   可用聲音: {list(tts_provider.get_voice_profiles().values())}")
    except ValueError as e:
        logger.error(f"❌ {e}")
        return
    except Exception as e:
        logger.error(f"❌ 初始化 TTS 供應商失敗: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return

    # Find all podcast files
    podcast_files = glob.glob(args.podcast)
    if not podcast_files:
        logger.error(f"❌ 未找到匹配的播客文件: {args.podcast}")
        return

    logger.info(f"找到 {len(podcast_files)} 個播客文件")

    # Process each podcast
    successful_count = 0
    for podcast_file in podcast_files:
        success = process_podcast_episode(
            podcast_path=podcast_file,
            output_dir=args.out_dir,
            tts_provider=tts_provider
        )

        if success:
            successful_count += 1

    logger.info(f"處理完成！成功: {successful_count}/{len(podcast_files)} 個播客")


if __name__ == "__main__":
    main()

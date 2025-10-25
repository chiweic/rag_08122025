"""
Audio Ingestion Script for Processing Audio Transcripts into Vector Store
Processes audio transcripts from processed_audios.json and creates searchable chunks
"""

import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioIngester:
    """Process audio transcripts and prepare them for vector storage."""
    
    def __init__(
        self,
        audio_file: str = "processed_audios.json",
        output_file: str = "chunks/audio_chunks.jsonl",
        chunk_size: int = 500,
        chunk_overlap: int = 100
    ):
        self.audio_file = Path(audio_file)
        self.output_file = Path(output_file)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.audio_data = []
        
    def load_audio_data(self) -> None:
        """Load audio data from JSON file."""
        try:
            with open(self.audio_file, 'r', encoding='utf-8') as f:
                self.audio_data = json.load(f)
            logger.info(f"Loaded {len(self.audio_data)} audio files")
        except Exception as e:
            logger.error(f"Error loading audio data: {e}")
            raise
    
    def clean_transcript(self, text: str) -> str:
        """Clean and normalize transcript text."""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep Chinese punctuation
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        return text.strip()
    
    def split_into_chunks(self, text: str, audio_id: str) -> List[Dict[str, Any]]:
        """Split transcript into smaller chunks with overlap."""
        chunks = []
        
        if not text:
            return chunks
        
        # Split by sentences (Chinese period, exclamation, question mark)
        sentences = re.split(r'[。！？\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            return chunks
        
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence exceeds chunk size, save current chunk
            if current_length + sentence_length > self.chunk_size and current_chunk:
                chunk_text = '。'.join(current_chunk) + '。'
                chunks.append(chunk_text)
                
                # Keep overlap for context
                if self.chunk_overlap > 0:
                    overlap_sentences = []
                    overlap_length = 0
                    for s in reversed(current_chunk):
                        if overlap_length + len(s) <= self.chunk_overlap:
                            overlap_sentences.insert(0, s)
                            overlap_length += len(s)
                        else:
                            break
                    current_chunk = overlap_sentences
                    current_length = overlap_length
                else:
                    current_chunk = []
                    current_length = 0
            
            current_chunk.append(sentence)
            current_length += sentence_length
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = '。'.join(current_chunk) + '。'
            chunks.append(chunk_text)
        
        return chunks
    
    def estimate_timestamp(self, chunk_index: int, total_chunks: int, 
                          estimated_duration: int = 1800) -> tuple:
        """Estimate timestamp range for a chunk (in seconds)."""
        if total_chunks == 0:
            return "00:00", "00:00"
        
        chunk_duration = estimated_duration / total_chunks
        start_seconds = int(chunk_index * chunk_duration)
        end_seconds = int((chunk_index + 1) * chunk_duration)
        
        # Convert to MM:SS format
        start_time = f"{start_seconds // 60:02d}:{start_seconds % 60:02d}"
        end_time = f"{end_seconds // 60:02d}:{end_seconds % 60:02d}"
        
        return start_time, end_time
    
    def create_chunk_document(
        self, 
        chunk_text: str, 
        audio_data: Dict[str, Any],
        chunk_index: int,
        total_chunks: int
    ) -> Dict[str, Any]:
        """Create a document for a single audio chunk."""
        # Generate unique ID for this chunk
        chunk_id = hashlib.md5(
            f"{audio_data['id']}_{chunk_index}_{chunk_text[:50]}".encode()
        ).hexdigest()
        
        # Estimate timestamps
        start_time, end_time = self.estimate_timestamp(chunk_index, total_chunks)
        
        # Extract header from chunk (first 50 chars or first sentence)
        header_match = re.match(r'^([^。！？]+)[。！？]', chunk_text)
        header = header_match.group(1) if header_match else chunk_text[:50]
        
        return {
            "id": f"audio_chunk_{chunk_id}",
            "header": header,
            "content": chunk_text,
            "metadata": {
                "source_type": "audio",
                "audio_id": audio_data['id'],
                "audio_url": audio_data['url'],
                "audio_title": audio_data['title'],
                "section": audio_data.get('section', ''),
                "speaker": audio_data.get('metadata', {}).get('speaker', '聖嚴法師'),
                "chunk_index": chunk_index,
                "total_chunks": total_chunks,
                "timestamp_start": start_time,
                "timestamp_end": end_time,
                "source": audio_data['url'],
                "created_at": datetime.now().isoformat(),
                "category": "audio",
                "keyphrases": self.extract_keyphrases(chunk_text)
            }
        }
    
    def extract_keyphrases(self, text: str, max_phrases: int = 5) -> List[str]:
        """Extract key phrases from text."""
        # Simple keyword extraction based on common Buddhist terms
        keywords = []
        
        # Common Buddhist terms to look for
        buddhist_terms = [
            '念佛', '淨土', '禪修', '菩薩', '佛法', '修行', '智慧', '慈悲',
            '解脫', '覺悟', '三寶', '因果', '業力', '輪迴', '涅槃', '般若',
            '空性', '中道', '八正道', '四聖諦', '十二因緣', '六度', '布施',
            '持戒', '忍辱', '精進', '禪定', '般若', '迴向', '發願', '懺悔'
        ]
        
        for term in buddhist_terms:
            if term in text:
                keywords.append(term)
                if len(keywords) >= max_phrases:
                    break
        
        return keywords
    
    def process_audio_files(self) -> List[Dict[str, Any]]:
        """Process all audio files and create chunks."""
        all_chunks = []
        
        for audio in self.audio_data:
            if not audio.get('transcript'):
                logger.warning(f"No transcript for audio: {audio.get('title', 'Unknown')}")
                continue
            
            # Clean transcript
            clean_text = self.clean_transcript(audio['transcript'])
            
            # Split into chunks
            chunks = self.split_into_chunks(clean_text, audio['id'])
            
            # Create documents for each chunk
            for i, chunk_text in enumerate(chunks):
                chunk_doc = self.create_chunk_document(
                    chunk_text, 
                    audio, 
                    i, 
                    len(chunks)
                )
                all_chunks.append(chunk_doc)
            
            logger.info(f"Processed {audio['title']}: {len(chunks)} chunks")
        
        return all_chunks
    
    def save_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """Save chunks to JSONL file."""
        self.output_file.parent.mkdir(exist_ok=True)
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
        
        logger.info(f"Saved {len(chunks)} chunks to {self.output_file}")
    
    def run(self) -> None:
        """Run the complete ingestion process."""
        logger.info("Starting audio ingestion process...")
        
        # Load audio data
        self.load_audio_data()
        
        # Process audio files
        chunks = self.process_audio_files()
        
        # Save chunks
        self.save_chunks(chunks)
        
        logger.info(f"Audio ingestion complete! Created {len(chunks)} searchable chunks")
        
        # Print statistics
        sections = {}
        for chunk in chunks:
            section = chunk['metadata'].get('section', 'Unknown')
            sections[section] = sections.get(section, 0) + 1
        
        logger.info("Chunks by section:")
        for section, count in sections.items():
            logger.info(f"  {section}: {count} chunks")


if __name__ == "__main__":
    ingester = AudioIngester()
    ingester.run()
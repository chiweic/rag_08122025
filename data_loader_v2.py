"""
Enhanced Data Loader for Multi-Collection RAG System
Handles text, audio, and event chunks separately
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ChunkTypes:
    """Define the types of chunks we support"""
    TEXT = "text"
    AUDIO = "audio"
    EVENT = "event"
    
    @classmethod
    def all_types(cls) -> List[str]:
        return [cls.TEXT, cls.AUDIO, cls.EVENT]


@dataclass
class LoadedData:
    """Container for loaded chunks by type"""
    text_chunks: List[Dict[str, Any]]
    audio_chunks: List[Dict[str, Any]]
    event_chunks: List[Dict[str, Any]]
    
    def get_by_type(self, chunk_type: str) -> List[Dict[str, Any]]:
        """Get chunks by type"""
        if chunk_type == ChunkTypes.TEXT:
            return self.text_chunks
        elif chunk_type == ChunkTypes.AUDIO:
            return self.audio_chunks
        elif chunk_type == ChunkTypes.EVENT:
            return self.event_chunks
        else:
            raise ValueError(f"Unknown chunk type: {chunk_type}")
    
    def total_chunks(self) -> int:
        """Get total number of chunks across all types"""
        return len(self.text_chunks) + len(self.audio_chunks) + len(self.event_chunks)


class MultiTypeDataLoader:
    """Load and manage chunks of different types"""
    
    def __init__(self, chunks_dir: str = "chunks", audio_limit: int = None):
        self.chunks_dir = Path(chunks_dir)
        if not self.chunks_dir.exists():
            raise ValueError(f"Chunks directory {chunks_dir} does not exist")
        
        # Configuration for limiting chunks (useful for testing with large datasets)
        self.audio_limit = audio_limit  # Limit number of audio chunks to load
        
        # Define expected file names for each type
        self.chunk_files = {
            ChunkTypes.TEXT: "text_chunks.jsonl",
            ChunkTypes.AUDIO: "audio_chunks.jsonl",
            ChunkTypes.EVENT: "event_chunks.jsonl"
        }
    
    def load_jsonl_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load chunks from a single JSONL file."""
        chunks = []
        if not file_path.exists():
            logger.warning(f"File not found: {file_path}")
            return chunks
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    if line.strip():
                        try:
                            chunk = json.loads(line)
                            chunks.append(chunk)
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing line {line_num} in {file_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
        
        return chunks
    
    def load_all_chunks(self) -> LoadedData:
        """Load all chunks organized by type"""
        loaded_data = LoadedData(
            text_chunks=[],
            audio_chunks=[],
            event_chunks=[]
        )
        
        # Load text chunks (could be multiple files for backward compatibility)
        text_file = self.chunks_dir / self.chunk_files[ChunkTypes.TEXT]
        if text_file.exists():
            logger.info(f"Loading text chunks from {text_file}")
            loaded_data.text_chunks = self.load_jsonl_file(text_file)
        else:
            # Fallback: Load all non-audio/event JSONL files as text chunks
            logger.info("text_chunks.jsonl not found, loading legacy text files")
            for file_path in self.chunks_dir.glob("*.jsonl"):
                if file_path.name not in [self.chunk_files[ChunkTypes.AUDIO], 
                                         self.chunk_files[ChunkTypes.EVENT]]:
                    chunks = self.load_jsonl_file(file_path)
                    loaded_data.text_chunks.extend(chunks)
                    logger.info(f"Loaded {len(chunks)} text chunks from {file_path.name}")
        
        # Load audio chunks (with optional limit)
        audio_file = self.chunks_dir / self.chunk_files[ChunkTypes.AUDIO]
        if audio_file.exists():
            logger.info(f"Loading audio chunks from {audio_file}")
            all_audio_chunks = self.load_jsonl_file(audio_file)
            
            # Apply audio limit if configured
            if self.audio_limit and self.audio_limit > 0:
                loaded_data.audio_chunks = all_audio_chunks[:self.audio_limit]
                logger.info(f"Limited audio chunks to first {self.audio_limit} out of {len(all_audio_chunks)}")
            else:
                loaded_data.audio_chunks = all_audio_chunks
        
        # Load event chunks
        event_file = self.chunks_dir / self.chunk_files[ChunkTypes.EVENT]
        if event_file.exists():
            logger.info(f"Loading event chunks from {event_file}")
            loaded_data.event_chunks = self.load_jsonl_file(event_file)
        
        # Log statistics
        logger.info(f"Loaded chunks - Text: {len(loaded_data.text_chunks)}, "
                   f"Audio: {len(loaded_data.audio_chunks)}, "
                   f"Event: {len(loaded_data.event_chunks)}")
        
        return loaded_data
    
    def prepare_documents_for_vectordb(
        self, 
        chunks: List[Dict[str, Any]], 
        chunk_type: str
    ) -> List[Dict[str, Any]]:
        """Prepare chunks of a specific type for vector database insertion."""
        documents = []
        
        for chunk in chunks:
            # Combine header and content for embedding
            text_content = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
            
            # Ensure metadata includes the chunk type
            metadata = chunk.get('metadata', {})
            metadata['chunk_type'] = chunk_type
            
            # Add source_type if not already present
            if 'source_type' not in metadata:
                metadata['source_type'] = chunk_type
            
            document = {
                'id': chunk.get('id', ''),
                'text': text_content,
                'metadata': metadata
            }
            
            documents.append(document)
        
        return documents
    
    def get_chunk_statistics(self, loaded_data: LoadedData) -> Dict[str, Any]:
        """Get statistics about loaded chunks"""
        stats = {
            'total_chunks': loaded_data.total_chunks(),
            'by_type': {
                ChunkTypes.TEXT: len(loaded_data.text_chunks),
                ChunkTypes.AUDIO: len(loaded_data.audio_chunks),
                ChunkTypes.EVENT: len(loaded_data.event_chunks)
            },
            'categories': {}
        }
        
        # Analyze categories within each type
        for chunk_type in ChunkTypes.all_types():
            chunks = loaded_data.get_by_type(chunk_type)
            categories = {}
            for chunk in chunks:
                category = chunk.get('metadata', {}).get('category', 'unknown')
                categories[category] = categories.get(category, 0) + 1
            stats['categories'][chunk_type] = categories
        
        return stats


class ChunkOrganizer:
    """Utility to reorganize existing chunks into type-specific files"""
    
    @staticmethod
    def reorganize_chunks(chunks_dir: str = "chunks"):
        """Reorganize existing chunks into type-specific files"""
        chunks_path = Path(chunks_dir)
        
        text_chunks = []
        audio_chunks = []
        event_chunks = []
        
        # Process all existing JSONL files
        for file_path in chunks_path.glob("*.jsonl"):
            # Skip if already organized
            if file_path.name in ["text_chunks.jsonl", "audio_chunks.jsonl", "event_chunks.jsonl"]:
                continue
                
            chunks = []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        chunks.append(json.loads(line))
            
            # Categorize chunks
            for chunk in chunks:
                source_type = chunk.get('metadata', {}).get('source_type', '')
                chunk_id = chunk.get('id', '')
                
                if source_type == 'audio' or 'audio_chunk' in chunk_id:
                    audio_chunks.append(chunk)
                elif source_type == 'event' or 'event' in chunk_id.lower():
                    event_chunks.append(chunk)
                else:
                    text_chunks.append(chunk)
        
        # Write organized chunks
        def write_chunks(chunks, filename):
            if chunks:
                output_path = chunks_path / filename
                with open(output_path, 'w', encoding='utf-8') as f:
                    for chunk in chunks:
                        f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
                logger.info(f"Wrote {len(chunks)} chunks to {filename}")
        
        write_chunks(text_chunks, "text_chunks.jsonl")
        write_chunks(audio_chunks, "audio_chunks.jsonl")
        write_chunks(event_chunks, "event_chunks.jsonl")
        
        return {
            'text': len(text_chunks),
            'audio': len(audio_chunks),
            'event': len(event_chunks)
        }


if __name__ == "__main__":
    # Test the loader
    loader = MultiTypeDataLoader()
    data = loader.load_all_chunks()
    stats = loader.get_chunk_statistics(data)
    
    print("\nChunk Statistics:")
    print(f"Total chunks: {stats['total_chunks']}")
    print("\nBy type:")
    for chunk_type, count in stats['by_type'].items():
        print(f"  {chunk_type}: {count}")
    
    print("\nCategories by type:")
    for chunk_type, categories in stats['categories'].items():
        if categories:
            print(f"\n  {chunk_type}:")
            for category, count in categories.items():
                print(f"    {category}: {count}")
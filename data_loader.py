import json
import os
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# class
class ChunkDataLoader:
    def __init__(self, chunks_dir: str = "chunks"):
        self.chunks_dir = Path(chunks_dir)
        if not self.chunks_dir.exists():
            raise ValueError(f"Chunks directory {chunks_dir} does not exist")
    
    def load_all_chunks(self) -> List[Dict[str, Any]]:
        """Load all chunks from all .jsonl files (text, audio, event) in the chunks directory."""
        all_chunks = []

        # Load all three chunk types
        chunk_files = [
            "text_chunks.jsonl",
            "audio_chunks.jsonl",
            "event_chunks.jsonl"
        ]

        for filename in chunk_files:
            file_path = self.chunks_dir / filename

            if not file_path.exists():
                logger.warning(f"{filename} not found in {self.chunks_dir}")
                continue

            logger.info(f"Loading chunks from {filename}")

            chunks = self.load_jsonl_file(file_path)
            all_chunks.extend(chunks)
            logger.info(f"Loaded {len(chunks)} chunks from {filename}")

        logger.info(f"Total chunks loaded: {len(all_chunks)}")
        return all_chunks
    
    def load_jsonl_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load chunks from a single JSONL file."""
        chunks = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        chunk = json.loads(line)
                        chunks.append(chunk)
        except Exception as e:
            logger.error(f"Error loading {file_path}: {e}")
        
        return chunks
    
    def prepare_documents_for_vectordb(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare chunks for vector database insertion."""
        documents = []
        
        for chunk in chunks:
            # Combine header and content for embedding
            text_content = f"{chunk.get('header', '')}\n{chunk.get('content', '')}".strip()
            
            # Prepare metadata
            metadata = chunk.get('metadata', {})
            metadata['chunk_id'] = chunk.get('id', '')
            metadata['header'] = chunk.get('header', '')
            
            documents.append({
                'id': chunk.get('id', ''),
                'text': text_content,
                'metadata': metadata
            })
        
        return documents
    
    def get_chunk_statistics(self) -> Dict[str, Any]:
        """Get statistics about the loaded chunks."""
        chunks = self.load_all_chunks()
        
        if not chunks:
            return {"total_chunks": 0, "files": 0}
        
        # Collect statistics
        titles = set()
        categories = set()
        total_chars = 0
        
        for chunk in chunks:
            metadata = chunk.get('metadata', {})
            if 'title' in metadata:
                titles.add(metadata['title'])
            if 'category' in metadata:
                categories.add(metadata['category'])
            total_chars += len(chunk.get('content', ''))
        
        return {
            "total_chunks": len(chunks),
            "unique_documents": len(titles),
            "unique_categories": len(categories),
            "average_chunk_size": total_chars // len(chunks) if chunks else 0,
            "documents": list(titles),
            "categories": list(categories)
        }
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AudioRecommender:
    def __init__(self, 
                 vector_store=None, 
                 embeddings=None,
                 audio_file: str = "chunks/audio_chunks.jsonl"):
        """
        Initialize the audio recommender system.
        
        Args:
            vector_store: Vector store for semantic search (optional)
            embeddings: Embedding model (optional)
            audio_file: Path to the audio JSONL file
        """
        self.vector_store = vector_store
        self.embeddings = embeddings
        self.audio_file = Path(audio_file)
        self.audio_chunks = []
        self.audio_chunks_by_id = {}
        
        # Load audio chunks from file
        self.load_audio_chunks()
        
        # Initialize semantic search if embeddings provided
        if self.embeddings:
            self.build_search_index()
        
        logger.info(f"Audio recommender initialized with {len(self.audio_chunks)} audio chunks")
    
    def load_audio_chunks(self):
        """Load audio chunks from JSONL file."""
        if not self.audio_file.exists():
            logger.warning(f"Audio file {self.audio_file} not found")
            return
        
        with open(self.audio_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        audio_chunk = json.loads(line)
                        # Extract audio information from the chunk
                        metadata = audio_chunk.get('metadata', {})
                        audio = {
                            'id': audio_chunk.get('id', ''),
                            'header': audio_chunk.get('header', ''),
                            'content': audio_chunk.get('content', ''),
                            'audio_title': metadata.get('audio_title', ''),
                            'audio_url': metadata.get('audio_url', ''),
                            'speaker': metadata.get('speaker', ''),
                            'section': metadata.get('section', ''),
                            'timestamp_start': metadata.get('timestamp_start', ''),
                            'timestamp_end': metadata.get('timestamp_end', ''),
                            'chunk_index': metadata.get('chunk_index', 0),
                            'total_chunks': metadata.get('total_chunks', 1),
                            'keyphrases': metadata.get('keyphrases', []),
                            'category': metadata.get('category', 'audio'),
                            'source': metadata.get('source', ''),
                            'created_at': metadata.get('created_at', ''),
                            'chunk_id': audio_chunk.get('id', '')
                        }
                        
                        self.audio_chunks.append(audio)
                        self.audio_chunks_by_id[audio['id']] = audio

                        # Also index by audio_id + chunk_index for Qdrant matching
                        audio_id = metadata.get('audio_id', '')
                        chunk_index = metadata.get('chunk_index', 0)
                        if audio_id:
                            composite_key = f"{audio_id}_{chunk_index}"
                            self.audio_chunks_by_id[composite_key] = audio
                    except Exception as e:
                        logger.error(f"Error parsing audio chunk: {e}")
    
    def build_search_index(self):
        """Build semantic search index for audio chunks using Qdrant."""
        if not self.audio_chunks:
            logger.warning("No audio chunks to index")
            return

        # Skip embedding generation - we'll use vector_store.search() directly
        # Audio chunks are already in Qdrant with embeddings
        logger.info(f"Audio recommender will use Qdrant vector store for {len(self.audio_chunks)} audio chunks")
        self.audio_embeddings = None
    
    def get_audio_recommendations(self,
                                 query_and_answer: str,
                                 top_k: int = 3,
                                 min_similarity: float = 0.1) -> List[Dict[str, Any]]:
        """
        Get audio recommendations based on query and answer similarity.
        
        Args:
            query_and_answer: Combined query and answer text for similarity matching
            top_k: Number of recommendations to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of recommended audio chunks with similarity scores
        """
        if not self.audio_chunks:
            return []
        
        # Use Qdrant vector store for semantic search
        if self.vector_store and self.embeddings:
            try:
                # First embed the query
                query_embedding = self.embeddings.embed_query(query_and_answer)

                # Search Qdrant for audio chunks (filter by source_type=audio)
                search_results = self.vector_store.search(
                    query_embedding=query_embedding,
                    top_k=top_k,
                    filter_dict={"source_type": "audio"}
                )

                # Convert to audio objects
                recommendations = []
                for result in search_results:
                    # Find the audio chunk by audio_id + chunk_index
                    metadata = result.get('metadata', {})
                    audio_id = metadata.get('audio_id', '')
                    chunk_index = metadata.get('chunk_index', 0)
                    composite_key = f"{audio_id}_{chunk_index}"

                    if composite_key in self.audio_chunks_by_id:
                        audio = self.audio_chunks_by_id[composite_key].copy()

                        # Add similarity score
                        score = result.get('score', 0)
                        if score >= min_similarity:
                            audio['similarity_score'] = float(score)
                            audio['relevance'] = 'high' if score > 0.7 else 'medium' if score > 0.5 else 'low'
                            recommendations.append(audio)

                return recommendations

            except Exception as e:
                logger.error(f"Error in Qdrant search: {e}")
                # Fall back to keyword search
        
        # Fallback: keyword-based search
        return self.keyword_search(query_and_answer, self.audio_chunks, top_k)
    
    def keyword_search(self, query: str, audio_chunks: List[Dict], top_k: int) -> List[Dict[str, Any]]:
        """Simple keyword-based audio search."""
        query_lower = query.lower()
        query_terms = set(query_lower.split())
        
        scored_audios = []
        for audio in audio_chunks:
            score = 0
            search_text = f"{audio['audio_title']} {audio['speaker']} {audio['section']} {audio['header']} {audio['content']}".lower()
            
            # Count matching terms
            for term in query_terms:
                if term in search_text:
                    score += search_text.count(term)
            
            if score > 0:
                audio_copy = audio.copy()
                audio_copy['similarity_score'] = score / len(query_terms)  # Normalize
                audio_copy['relevance'] = 'medium'
                scored_audios.append(audio_copy)
        
        # Sort by score and return top k
        scored_audios.sort(key=lambda x: x['similarity_score'], reverse=True)
        return scored_audios[:top_k]
    
    def get_audio_by_id(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific audio chunk by ID."""
        audio = self.audio_chunks_by_id.get(audio_id)
        if audio:
            return audio.copy()
        return None
    
    def get_audios_by_title(self, title: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get audio chunks filtered by title."""
        matching_audios = [
            a for a in self.audio_chunks 
            if title.lower() in a.get('audio_title', '').lower()
        ]
        
        # Sort by chunk_index to maintain order
        matching_audios.sort(key=lambda x: x.get('chunk_index', 0))
        
        return matching_audios[:limit]
    
    def get_audios_by_speaker(self, speaker: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get audio chunks filtered by speaker."""
        matching_audios = [
            a for a in self.audio_chunks 
            if speaker.lower() in a.get('speaker', '').lower()
        ]
        
        # Sort by audio title and chunk index
        matching_audios.sort(key=lambda x: (x.get('audio_title', ''), x.get('chunk_index', 0)))
        
        return matching_audios[:limit]
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
                    except Exception as e:
                        logger.error(f"Error parsing audio chunk: {e}")
    
    def build_search_index(self):
        """Build semantic search index for audio chunks."""
        if not self.audio_chunks:
            logger.warning("No audio chunks to index")
            return
        
        # Create searchable text for each audio chunk
        self.audio_texts = []
        for audio in self.audio_chunks:
            search_text = f"{audio['audio_title']} {audio['speaker']} {audio['section']} {audio['header']} {audio['content']}"
            self.audio_texts.append(search_text)
        
        # Generate embeddings for all audio chunks
        try:
            logger.info(f"Generating embeddings for {len(self.audio_texts)} audio chunks...")
            self.audio_embeddings = self.embeddings.embed_documents(self.audio_texts)
            self.audio_embeddings = np.array(self.audio_embeddings)
            logger.info(f"Generated embeddings with shape {self.audio_embeddings.shape}")
        except Exception as e:
            logger.error(f"Error generating audio embeddings: {e}")
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
        
        # If we have embeddings, use semantic search
        if self.embeddings and self.audio_embeddings is not None:
            try:
                # Generate query embedding
                query_embedding = self.embeddings.embed_query(query_and_answer)
                query_embedding = np.array(query_embedding)
                
                # Calculate similarities
                similarities = np.dot(self.audio_embeddings, query_embedding)
                
                # Get top k recommendations
                top_indices = np.argsort(similarities)[::-1][:top_k]
                
                recommendations = []
                for idx in top_indices:
                    score = similarities[idx]
                    if score >= min_similarity:
                        audio = self.audio_chunks[idx].copy()
                        audio['similarity_score'] = float(score)
                        audio['relevance'] = 'high' if score > 0.4 else 'medium' if score > 0.2 else 'low'
                        recommendations.append(audio)
                
                return recommendations
                
            except Exception as e:
                logger.error(f"Error in audio semantic search: {e}")
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
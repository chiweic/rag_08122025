"""
Enhanced Vector Store with Multi-Collection Support
Manages separate collections for text, audio, and event chunks
"""

import uuid
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue
)
import numpy as np
from tqdm import tqdm

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """Configuration for multi-collection search"""
    text_limit: int = 3
    audio_limit: int = 1
    event_limit: int = 1
    similarity_threshold: float = 0.0
    
    def total_limit(self) -> int:
        return self.text_limit + self.audio_limit + self.event_limit


class MultiCollectionVectorStore:
    """Vector store managing multiple collections by type"""
    
    def __init__(
        self,
        url: str = "http://localhost:6333",
        api_key: Optional[str] = None,
        embedding_dim: int = None,  # Auto-detect if not specified
        collection_prefix: str = "ddm_rag"
    ):
        self.client = QdrantClient(url=url, api_key=api_key)
        
        # Auto-detect embedding dimension if not provided
        if embedding_dim is None:
            from llm_factory import EmbeddingFactory
            self.embedding_dim = EmbeddingFactory.get_embedding_dimension()
        else:
            self.embedding_dim = embedding_dim
            
        self.collection_prefix = collection_prefix
        
        # Define collection names
        self.collections = {
            'text': f"{collection_prefix}_text",
            'audio': f"{collection_prefix}_audio",
            'event': f"{collection_prefix}_event"
        }
        
        logger.info(f"Connected to Qdrant at {url}")
    
    def create_collection(self, collection_type: str, recreate: bool = False) -> None:
        """Create a collection for a specific type"""
        if collection_type not in self.collections:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        collection_name = self.collections[collection_type]
        
        # Check if collection exists
        collections = self.client.get_collections().collections
        exists = any(c.name == collection_name for c in collections)
        
        if exists:
            if recreate:
                logger.info(f"Deleting existing collection: {collection_name}")
                self.client.delete_collection(collection_name)
            else:
                logger.info(f"Collection {collection_name} already exists")
                return
        
        # Create new collection
        logger.info(f"Creating collection: {collection_name}")
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=self.embedding_dim,
                distance=Distance.COSINE
            )
        )
    
    def create_all_collections(self, recreate: bool = False) -> None:
        """Create all collections"""
        for collection_type in self.collections.keys():
            self.create_collection(collection_type, recreate)
    
    def add_documents(
        self,
        collection_type: str,
        documents: List[Dict[str, Any]],
        embeddings: List[List[float]],
        batch_size: int = 100
    ) -> None:
        """Add documents to a specific collection"""
        if collection_type not in self.collections:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        collection_name = self.collections[collection_type]
        
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings")
        
        points = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            # Generate unique point ID
            point_id = str(uuid.uuid4())
            
            # Prepare payload
            payload = {
                "id": doc.get('id', ''),
                "text": doc.get('text', ''),
                "metadata": doc.get('metadata', {})
            }
            
            # Ensure metadata is properly structured
            if 'metadata' in payload:
                # Flatten nested metadata for better searchability
                metadata = payload['metadata']
                if isinstance(metadata, dict):
                    # Add collection type to metadata
                    metadata['collection_type'] = collection_type
                    payload.update(metadata)
            
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload=payload
            )
            points.append(point)
        
        # Upload in batches
        total_batches = (len(points) + batch_size - 1) // batch_size
        
        with tqdm(total=total_batches, desc=f"Uploading to {collection_name}") as pbar:
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=collection_name,
                    points=batch,
                    wait=True
                )
                pbar.update(1)
        
        logger.info(f"Successfully added {len(documents)} documents to {collection_name}")
    
    def search_collection(
        self,
        collection_type: str,
        query_vector: List[float],
        limit: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search in a specific collection"""
        if collection_type not in self.collections:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        collection_name = self.collections[collection_type]
        
        # Build filter if provided
        search_filter = None
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            if conditions:
                search_filter = Filter(must=conditions)
        
        # Perform search
        results = self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            query_filter=search_filter,
            with_payload=True,
            with_vectors=False
        )
        
        # Format results
        formatted_results = []
        for hit in results:
            result = {
                'id': hit.id,
                'score': hit.score,
                'collection_type': collection_type,
                **hit.payload
            }
            formatted_results.append(result)
        
        return formatted_results
    
    def multi_collection_search(
        self,
        query_vector: List[float],
        search_config: SearchConfig,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across multiple collections with configurable limits"""
        results = {}
        
        # Search text collection
        if search_config.text_limit > 0:
            text_results = self.search_collection(
                'text',
                query_vector,
                search_config.text_limit,
                filter_dict
            )
            results['text'] = text_results
        
        # Search audio collection
        if search_config.audio_limit > 0:
            audio_results = self.search_collection(
                'audio',
                query_vector,
                search_config.audio_limit,
                filter_dict
            )
            results['audio'] = audio_results
        
        # Search event collection
        if search_config.event_limit > 0:
            event_results = self.search_collection(
                'event',
                query_vector,
                search_config.event_limit,
                filter_dict
            )
            results['event'] = event_results
        
        return results
    
    def combined_search(
        self,
        query_vector: List[float],
        search_config: SearchConfig,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search across collections and return combined sorted results"""
        multi_results = self.multi_collection_search(
            query_vector,
            search_config,
            filter_dict
        )
        
        # Combine all results
        all_results = []
        for collection_type, results in multi_results.items():
            all_results.extend(results)
        
        # Sort by score (descending)
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Apply similarity threshold if specified
        if search_config.similarity_threshold > 0:
            all_results = [
                r for r in all_results 
                if r.get('score', 0) >= search_config.similarity_threshold
            ]
        
        return all_results
    
    def get_collection_info(self, collection_type: str) -> Dict[str, Any]:
        """Get information about a specific collection"""
        if collection_type not in self.collections:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        collection_name = self.collections[collection_type]
        
        try:
            info = self.client.get_collection(collection_name)
            return {
                'name': collection_name,
                'vectors_count': info.vectors_count,
                'points_count': info.points_count,
                'indexed_vectors_count': info.indexed_vectors_count,
                'status': info.status
            }
        except Exception as e:
            logger.error(f"Error getting collection info for {collection_name}: {e}")
            return {'name': collection_name, 'error': str(e)}
    
    def get_all_collections_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all collections"""
        info = {}
        for collection_type in self.collections.keys():
            info[collection_type] = self.get_collection_info(collection_type)
        return info
    
    def delete_collection(self, collection_type: str) -> None:
        """Delete a specific collection"""
        if collection_type not in self.collections:
            raise ValueError(f"Unknown collection type: {collection_type}")
        
        collection_name = self.collections[collection_type]
        self.client.delete_collection(collection_name)
        logger.info(f"Deleted collection: {collection_name}")
    
    def delete_all_collections(self) -> None:
        """Delete all collections"""
        for collection_type in self.collections.keys():
            try:
                self.delete_collection(collection_type)
            except Exception as e:
                logger.warning(f"Could not delete collection {collection_type}: {e}")
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, 
    Distance, 
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue
)
import uuid
from tqdm import tqdm

logger = logging.getLogger(__name__)


class QdrantVectorStore:
    def __init__(self, url: str, api_key: Optional[str] = None, collection_name: str = "ddm_rag"):
        self.client = QdrantClient(url=url, api_key=api_key)
        self.collection_name = collection_name
        logger.info(f"Connected to Qdrant at {url}")
    
    def create_collection(self, vector_size: int = 1024, recreate: bool = False):
        """Create or recreate a collection in Qdrant."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            
            if exists:
                if recreate:
                    logger.info(f"Deleting existing collection: {self.collection_name}")
                    self.client.delete_collection(self.collection_name)
                else:
                    logger.info(f"Collection {self.collection_name} already exists")
                    return
            
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created collection: {self.collection_name} with vector size {vector_size}")
            
        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise
    
    def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]], batch_size: int = 100):
        """Add documents with embeddings to the vector store."""
        if len(documents) != len(embeddings):
            raise ValueError("Number of documents must match number of embeddings")
        
        points = []
        for i, (doc, embedding) in enumerate(zip(documents, embeddings)):
            # Use integer ID for Qdrant compatibility
            point_id = i if 'id' not in doc else str(uuid.uuid4())
            
            # Ensure metadata is JSON serializable
            metadata = doc.get('metadata', {})
            metadata['text'] = doc.get('text', '')
            
            points.append(
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload=metadata
                )
            )
        
        # Upload in batches
        total_batches = (len(points) + batch_size - 1) // batch_size
        for i in tqdm(range(0, len(points), batch_size), desc="Uploading to Qdrant", total=total_batches):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.collection_name,
                points=batch
            )
        
        logger.info(f"Successfully added {len(points)} documents to {self.collection_name}")
    
    def search(
        self, 
        query_embedding: List[float], 
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar documents in the vector store."""
        search_params = {
            "collection_name": self.collection_name,
            "query_vector": query_embedding,
            "limit": top_k,
            "with_payload": True,
            "with_vectors": False
        }
        
        # Add filter if provided
        if filter_dict:
            conditions = []
            for key, value in filter_dict.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            search_params["query_filter"] = Filter(must=conditions)
        
        results = self.client.search(**search_params)
        
        # Format results
        formatted_results = []
        for result in results:
            formatted_results.append({
                "id": result.id,
                "score": result.score,
                "text": result.payload.get("text", ""),
                "metadata": {k: v for k, v in result.payload.items() if k != "text"}
            })
        
        return formatted_results
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        try:
            info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "indexed_vectors_count": info.indexed_vectors_count,
                "status": info.status
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            return {"error": str(e)}
    
    def delete_collection(self):
        """Delete the collection."""
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            raise
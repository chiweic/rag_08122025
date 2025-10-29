"""
Enhanced API with Multi-Collection RAG Support
Handles text, audio, and event collections separately
"""

import time
import asyncio
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import json

from config import settings
from data_loader_v2 import MultiTypeDataLoader, LoadedData, ChunkTypes
from vector_store_v2 import MultiCollectionVectorStore, SearchConfig
from rag_pipeline_v2 import MultiCollectionRAGPipeline, RAGConfig
from llm_factory import EmbeddingFactory, LLMFactory
from book_recommender import BookRecommender
from query_recommender import QueryRecommender
from embedding_config import EmbeddingConfigManager
# from event_recommender import EventRecommender  # TODO: Create this module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="Multi-Collection RAG API",
    description="Buddhist Teaching RAG System with Multiple Collections",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Global variables
rag_pipeline: Optional[MultiCollectionRAGPipeline] = None
vector_store: Optional[MultiCollectionVectorStore] = None
is_initialized = False
book_recommender: Optional[BookRecommender] = None
query_recommender: Optional[QueryRecommender] = None
event_recommender = None  # Optional[EventRecommender] - TODO: Implement EventRecommender


# Request models
class InitializeRequest(BaseModel):
    recreate_collections: bool = Field(False, description="Recreate all vector collections")
    batch_size: int = Field(100, description="Batch size for vector upload")
    text_limit: int = Field(3, description="Default text results limit")
    audio_limit: int = Field(1, description="Default audio results limit")
    event_limit: int = Field(1, description="Default event results limit")


class QueryRequest(BaseModel):
    question: str = Field(..., description="User question")
    text_limit: int = Field(3, description="Number of text results")
    audio_limit: int = Field(1, description="Number of audio results")
    event_limit: int = Field(1, description="Number of event results")
    similarity_threshold: float = Field(0.3, description="Minimum similarity threshold")
    include_sources: bool = Field(True, description="Include source references")
    temperature: float = Field(0.7, description="LLM temperature")
    max_tokens: int = Field(1000, description="Maximum response tokens")


class CollectionStatsRequest(BaseModel):
    collection_type: Optional[str] = Field(None, description="Specific collection type")


class ConfigUpdateRequest(BaseModel):
    # Embedding configuration
    embedding_model: Optional[str] = Field(None, description="New embedding model name")
    embedding_provider: Optional[str] = Field(None, description="Embedding provider")
    
    # LLM configuration
    llm_model: Optional[str] = Field(None, description="New LLM model name")
    llm_provider: Optional[str] = Field(None, description="LLM provider")
    llm_temperature: Optional[float] = Field(None, description="LLM temperature", ge=0.0, le=2.0)
    llm_max_tokens: Optional[int] = Field(None, description="Maximum tokens for LLM response", ge=1)
    
    # Auto-reinitialize flag (only needed if embedding changes)
    auto_reinitialize: bool = Field(True, description="Automatically reinitialize after embedding config change")


class RetrievalRequest(BaseModel):
    question: str = Field(..., description="User question")
    text_limit: int = Field(3, description="Number of text results")
    audio_limit: int = Field(1, description="Number of audio results")
    event_limit: int = Field(1, description="Number of event results")
    similarity_threshold: float = Field(0.3, description="Minimum similarity threshold")
    include_metadata: bool = Field(True, description="Include detailed metadata")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    global is_initialized, vector_store
    
    collections_status = {}
    if vector_store:
        try:
            collections_info = vector_store.get_all_collections_info()
            for collection_type, info in collections_info.items():
                collections_status[collection_type] = {
                    'healthy': 'error' not in info,
                    'points': info.get('points_count', 0)
                }
        except Exception as e:
            logger.error(f"Error checking collections: {e}")
    
    return {
        "status": "healthy" if is_initialized else "initializing",
        "initialized": is_initialized,
        "collections": collections_status,
        "timestamp": time.time()
    }


# Initialize system
@app.post("/initialize")
async def initialize_system(request: InitializeRequest = InitializeRequest()):
    """Initialize the multi-collection RAG system"""
    global rag_pipeline, vector_store, is_initialized
    global book_recommender, query_recommender, event_recommender
    
    start_time = time.time()
    
    try:
        logger.info("Starting multi-collection RAG system initialization...")
        
        # Check embedding configuration and auto-detect changes
        config_manager = EmbeddingConfigManager()
        
        # Auto-detect embedding dimension
        embedding_dim = EmbeddingFactory.get_embedding_dimension()
        logger.info(f"Using embedding model: {settings.embedding_model} with {embedding_dim} dimensions")
        
        # Determine if collections should be recreated
        should_recreate = request.recreate_collections or config_manager.should_recreate_collections()
        
        if should_recreate and not request.recreate_collections:
            logger.info("Embedding model changed - automatically recreating collections")
        
        # Initialize vector store with auto-detected dimension
        vector_store = MultiCollectionVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            embedding_dim=embedding_dim
        )
        
        # Create collections
        vector_store.create_all_collections(recreate=should_recreate)
        
        # Load data (limit audio chunks to 100 for faster initialization)
        loader = MultiTypeDataLoader(audio_limit=100)
        loaded_data = loader.load_all_chunks()
        
        if loaded_data.total_chunks() == 0:
            raise ValueError("No chunks found in any category")
        
        # Initialize embedding factory
        embedding_factory = EmbeddingFactory()
        embeddings_model = embedding_factory.create_embeddings()
        
        # Process each collection type
        for chunk_type in ChunkTypes.all_types():
            chunks = loaded_data.get_by_type(chunk_type)
            
            if not chunks:
                logger.info(f"No {chunk_type} chunks found, skipping")
                continue
            
            logger.info(f"Processing {len(chunks)} {chunk_type} chunks...")
            
            # Prepare documents
            documents = loader.prepare_documents_for_vectordb(chunks, chunk_type)
            
            # Generate embeddings
            texts = [doc['text'] for doc in documents]
            embeddings_list = embeddings_model.embed_documents(texts)
            
            # Add to vector store
            vector_store.add_documents(
                collection_type=chunk_type,
                documents=documents,
                embeddings=embeddings_list,
                batch_size=request.batch_size
            )
        
        # Initialize RAG pipeline
        llm_factory = LLMFactory()
        rag_pipeline = MultiCollectionRAGPipeline(
            vector_store=vector_store,
            llm_factory=llm_factory,
            embedding_factory=embedding_factory
        )
        
        # Initialize recommenders
        try:
            book_recommender = BookRecommender()
            logger.info("Book recommender initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize book recommender: {e}")
            book_recommender = None
        
        try:
            query_recommender = QueryRecommender(vector_store=vector_store)
            logger.info("Query recommender initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize query recommender: {e}")
            query_recommender = None
        
        # TODO: Initialize event recommender when module is implemented
        # try:
        #     event_recommender = EventRecommender(vector_store=vector_store)
        #     logger.info("Event recommender initialized successfully")
        # except Exception as e:
        #     logger.warning(f"Failed to initialize event recommender: {e}")
        event_recommender = None
        
        # Get final collection info
        collections_info = vector_store.get_all_collections_info()
        
        # Save embedding configuration after successful initialization
        config_manager.save_config(embedding_dim)
        
        is_initialized = True
        computation_time = time.time() - start_time
        
        logger.info(f"Multi-collection RAG system initialized in {computation_time:.2f}s")
        
        return {
            "status": "success",
            "message": "Multi-collection RAG system initialized successfully",
            "collections_info": collections_info,
            "chunks_loaded": {
                "text": len(loaded_data.text_chunks),
                "audio": len(loaded_data.audio_chunks),
                "event": len(loaded_data.event_chunks),
                "total": loaded_data.total_chunks()
            },
            "computation_time": computation_time
        }
        
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        is_initialized = False
        raise HTTPException(status_code=500, detail=f"Initialization failed: {str(e)}")


# Query endpoints
@app.post("/query")
async def query_rag(request: QueryRequest):
    """Query the multi-collection RAG system"""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        config = RAGConfig(
            text_limit=request.text_limit,
            audio_limit=request.audio_limit,
            event_limit=request.event_limit,
            similarity_threshold=request.similarity_threshold,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            include_sources=request.include_sources,
            stream=False
        )
        
        result = rag_pipeline.query(request.question, config)
        return result
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def query_rag_stream(request: QueryRequest):
    """Streaming query for the multi-collection RAG system"""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    async def generate_stream():
        try:
            config = RAGConfig(
                text_limit=request.text_limit,
                audio_limit=request.audio_limit,
                event_limit=request.event_limit,
                similarity_threshold=request.similarity_threshold,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                include_sources=request.include_sources,
                stream=True
            )
            
            async for chunk in rag_pipeline.query_stream(request.question, config):
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.post("/retrieve")
async def retrieve_chunks(request: RetrievalRequest):
    """Retrieve relevant chunks without generating an answer"""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        start_time = time.time()
        
        # Use the existing RAG pipeline's retrieve method to get results
        config = RAGConfig(
            text_limit=request.text_limit,
            audio_limit=request.audio_limit,
            event_limit=request.event_limit,
            similarity_threshold=request.similarity_threshold
        )
        
        # Use the pipeline's retrieve method which already handles embeddings properly
        results, retrieval_time = rag_pipeline.retrieve(request.question, config)
        
        # Format results using the pipeline's format_sources method
        formatted_sources = rag_pipeline.format_sources(results)
        
        # Reorganize sources into our expected format
        formatted_results = []
        chunks_retrieved = {"text": 0, "audio": 0, "event": 0}
        
        for source in formatted_sources:
            collection_type = source.get("type", "text")
            chunks_retrieved[collection_type] = chunks_retrieved.get(collection_type, 0) + 1
            
            chunk_data = {
                "type": collection_type,
                "content": source.get("text", ""),
                "score": source.get("score", 0.0)
            }
            
            if request.include_metadata:
                chunk_data["metadata"] = source.get("metadata", {})
            else:
                # Include minimal metadata
                metadata = source.get("metadata", {})
                chunk_data["metadata"] = {
                    "title": metadata.get("title", ""),
                    "source": metadata.get("source", ""),
                    "category": metadata.get("category", "")
                }
            
            formatted_results.append(chunk_data)
        
        return {
            "query": request.question,
            "chunks_retrieved": chunks_retrieved,
            "total_chunks": len(formatted_results),
            "retrieval_time": retrieval_time,
            "results": formatted_results,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logger.error(f"Retrieval error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Collection management
@app.get("/collections/info")
async def get_collections_info():
    """Get information about all collections"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
    try:
        info = vector_store.get_all_collections_info()
        return {
            "collections": info,
            "total_collections": len(info),
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting collections info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/collections/{collection_type}/stats")
async def get_collection_stats(collection_type: str):
    """Get statistics for a specific collection"""
    if not vector_store:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    
    if collection_type not in ChunkTypes.all_types():
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid collection type. Must be one of: {ChunkTypes.all_types()}"
        )
    
    try:
        info = vector_store.get_collection_info(collection_type)
        return {
            "collection_type": collection_type,
            "info": info,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Error getting collection stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Configuration management
@app.get("/config")
async def get_current_config():
    """Get current system configuration"""
    return {
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimension": EmbeddingFactory.get_embedding_dimension() if is_initialized else None
        },
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "max_tokens": settings.llm_max_tokens,
            "temperature": settings.llm_temperature
        },
        "vector_store": {
            "url": settings.qdrant_url,
            "collections": vector_store.get_all_collections_info() if vector_store else None
        },
        "system": {
            "initialized": is_initialized,
            "timestamp": time.time()
        }
    }


@app.post("/config")
async def update_config(request: ConfigUpdateRequest):
    """Update system configuration at runtime (embedding and/or LLM)"""
    global rag_pipeline, vector_store, is_initialized
    
    try:
        changes_made = {}
        old_config = {}
        needs_reinit = False
        
        # Handle embedding configuration changes
        if request.embedding_model or request.embedding_provider:
            old_config["embedding"] = {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model
            }
            
            # Validate the new embedding model first
            test_provider = request.embedding_provider or settings.embedding_provider
            test_model = request.embedding_model or settings.embedding_model
            test_factory = EmbeddingFactory()
            
            # Test if the model can be loaded
            logger.info(f"Testing new embedding model: {test_provider}/{test_model}")
            test_embeddings = test_factory.create_embeddings(test_provider, test_model)
            test_dimension = len(test_embeddings.embed_query("test"))
            
            # Update settings
            if request.embedding_model:
                settings.embedding_model = request.embedding_model
            if request.embedding_provider:
                settings.embedding_provider = request.embedding_provider
            
            changes_made["embedding"] = {
                "provider": settings.embedding_provider,
                "model": settings.embedding_model,
                "dimension": test_dimension
            }
            needs_reinit = True
            logger.info(f"Updated embedding config: {old_config['embedding']} → {changes_made['embedding']}")
        
        # Handle LLM configuration changes
        if any([request.llm_model, request.llm_provider, request.llm_temperature is not None, request.llm_max_tokens]):
            old_config["llm"] = {
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "temperature": settings.llm_temperature,
                "max_tokens": settings.llm_max_tokens
            }
            
            # Validate LLM model if changed
            if request.llm_model or request.llm_provider:
                test_llm_provider = request.llm_provider or settings.llm_provider
                test_llm_model = request.llm_model or settings.llm_model
                test_llm_factory = LLMFactory()
                
                # Test if the model can be loaded
                logger.info(f"Testing new LLM model: {test_llm_provider}/{test_llm_model}")
                test_llm = test_llm_factory.create_llm(test_llm_provider, test_llm_model)
            
            # Update LLM settings
            if request.llm_model:
                settings.llm_model = request.llm_model
            if request.llm_provider:
                settings.llm_provider = request.llm_provider
            if request.llm_temperature is not None:
                settings.llm_temperature = request.llm_temperature
            if request.llm_max_tokens:
                settings.llm_max_tokens = request.llm_max_tokens
            
            changes_made["llm"] = {
                "provider": settings.llm_provider,
                "model": settings.llm_model,
                "temperature": settings.llm_temperature,
                "max_tokens": settings.llm_max_tokens
            }
            
            # Update the RAG pipeline's LLM if initialized
            if is_initialized and rag_pipeline:
                rag_pipeline.llm_factory = LLMFactory()
                rag_pipeline.llm = rag_pipeline.llm_factory.create_llm()
                logger.info("Updated RAG pipeline with new LLM configuration")
        
        if not changes_made:
            return {
                "status": "no_changes",
                "message": "No configuration changes requested"
            }
        
        config_response = {
            "status": "success",
            "message": "Configuration updated successfully",
            "old_config": old_config,
            "new_config": changes_made,
            "needs_reinitialization": needs_reinit
        }
        
        # Automatically reinitialize if requested and needed
        if needs_reinit and request.auto_reinitialize:
            logger.info("Auto-reinitializing system due to embedding model change...")
            init_request = InitializeRequest(recreate_collections=True)
            init_result = await initialize_system(init_request)
            config_response["initialization"] = init_result
        
        return config_response
        
    except Exception as e:
        # Rollback settings on error
        if "old_config" in locals():
            if "embedding" in old_config:
                settings.embedding_model = old_config["embedding"]["model"]
                settings.embedding_provider = old_config["embedding"]["provider"]
            if "llm" in old_config:
                settings.llm_model = old_config["llm"]["model"]
                settings.llm_provider = old_config["llm"]["provider"]
                settings.llm_temperature = old_config["llm"]["temperature"]
                settings.llm_max_tokens = old_config["llm"]["max_tokens"]
        
        logger.error(f"Failed to update config: {e}")
        raise HTTPException(status_code=500, detail=f"Configuration update failed: {str(e)}")


# Legacy endpoints (for compatibility)
@app.post("/books/recommend")
async def recommend_books(request: Dict[str, Any]):
    """Book recommendations (legacy compatibility)"""
    if not book_recommender:
        raise HTTPException(status_code=503, detail="Book recommender not available")
    
    try:
        recommendations = book_recommender.get_recommendations(
            query=request.get("query", ""),
            top_k=request.get("top_k", 5),
            min_similarity=request.get("min_similarity", 0.05)
        )
        return {"books": recommendations}
    except Exception as e:
        logger.error(f"Book recommendation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend
@app.get("/")
async def serve_frontend():
    """Serve the frontend index.html"""
    return FileResponse("frontend/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
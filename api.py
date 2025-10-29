from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union
import logging
import time
import uuid
from datetime import datetime
import random
from contextlib import asynccontextmanager

from config import settings
from data_loader import ChunkDataLoader
from vector_store import QdrantVectorStore
from rag_pipeline import RAGPipeline
from llm_factory import EmbeddingFactory
from book_recommender import BookRecommender
from query_recommender import QueryRecommender
from event_recommender import EventRecommender
from audio_recommender import AudioRecommender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for pipeline
rag_pipeline = None
vector_store = None
is_initialized = False
book_recommender = None
query_recommender = None
event_recommender = None
audio_recommender = None

# Cache for query history (stores last N queries)
from collections import deque
query_history_cache = deque(maxlen=50)  # Keep last 50 queries
last_query_cache = None  # Quick access to most recent query


# Request/Response models
class QueryRequest(BaseModel):
    question: str = Field(..., description="The question to ask")
    top_k: Optional[int] = Field(default=5, description="Number of documents to retrieve")
    filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters")
    include_sources: Optional[bool] = Field(default=True, description="Include source documents")


class RetrievalRequest(BaseModel):
    query: str = Field(..., description="The search query")
    top_k: Optional[int] = Field(default=5, description="Number of documents to retrieve")
    filter: Optional[Dict[str, Any]] = Field(default=None, description="Metadata filters")


class SynthesisRequest(BaseModel):
    question: str = Field(..., description="The question to answer")
    contexts: List[Dict[str, Any]] = Field(..., description="Context documents")
    prompt_type: Optional[Literal["qa", "summary"]] = Field(default="qa", description="Type of synthesis")


class ConfigUpdateRequest(BaseModel):
    llm_provider: Optional[Literal["openai", "deepseek", "google", "dashscope", "custom"]] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = Field(None, ge=0, le=2)
    embedding_provider: Optional[Literal["openai", "huggingface", "local"]] = None
    embedding_model: Optional[str] = None


class InitializeRequest(BaseModel):
    recreate_collection: Optional[bool] = Field(default=False, description="Recreate vector collection")
    batch_size: Optional[int] = Field(default=100, description="Batch size for uploading")


class BookRecommendationRequest(BaseModel):
    query: str = Field(..., description="Query for book recommendations")
    top_k: Optional[int] = Field(default=5, description="Number of books to recommend")
    min_similarity: Optional[float] = Field(default=0.1, description="Minimum similarity threshold")


class RelatedQueriesRequest(BaseModel):
    query: str = Field(..., description="User query to find related questions for")
    top_k: Optional[int] = Field(default=3, description="Number of related queries to return")
    min_similarity: Optional[float] = Field(default=0.1, description="Minimum similarity threshold")
    category: Optional[str] = Field(default=None, description="Filter by category")


class EventRecommendationRequest(BaseModel):
    query: str = Field(..., description="Query for event recommendations")
    top_k: Optional[int] = Field(default=6, description="Number of events to recommend")
    min_similarity: Optional[float] = Field(default=0.1, description="Minimum similarity threshold")
    upcoming_only: Optional[bool] = Field(default=True, description="Filter for upcoming events only")


class AudioRecommendationRequest(BaseModel):
    query_and_answer: str = Field(..., description="Combined query and answer for audio recommendations")
    top_k: Optional[int] = Field(default=3, description="Number of audio chunks to recommend")
    min_similarity: Optional[float] = Field(default=0.1, description="Minimum similarity threshold")


class TranslationRequest(BaseModel):
    text: str = Field(..., description="Text to translate")
    target_language: Optional[str] = Field(default="english", description="Target language")


class SummarizationRequest(BaseModel):
    text: str = Field(..., description="Text to summarize")
    max_length: Optional[int] = Field(default=200, description="Maximum length of summary")


# OpenAI v1 Compatible Models
class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"] = Field(..., description="Message role")
    content: str = Field(..., description="Message content")


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="rag-model", description="Model name (ignored, uses configured model)")
    messages: List[ChatMessage] = Field(..., description="Chat messages")
    temperature: Optional[float] = Field(default=None, description="Temperature for generation")
    max_tokens: Optional[int] = Field(default=None, description="Maximum tokens")
    top_p: Optional[float] = Field(default=1.0, description="Top-p sampling")
    n: Optional[int] = Field(default=1, description="Number of completions")
    stream: Optional[bool] = Field(default=False, description="Stream response (not supported)")
    top_k: Optional[int] = Field(default=5, description="Number of documents to retrieve for RAG")
    include_sources: Optional[bool] = Field(default=False, description="Include source documents in response")


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: Literal["stop", "length", "content_filter"]


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"]
    created: int
    model: str
    choices: List[ChatCompletionChoice]
    usage: ChatCompletionUsage
    system_fingerprint: Optional[str] = None
    # Extended fields for RAG
    sources: Optional[List[Dict[str, Any]]] = None
    computation_time: Optional[Dict[str, float]] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global rag_pipeline, vector_store, is_initialized, book_recommender, query_recommender, event_recommender, audio_recommender

    logger.info("Starting up RAG API...")
    logger.info("Connecting to Qdrant and initializing components...")

    try:
        # Initialize vector store (connects to existing Qdrant collection)
        vector_store = QdrantVectorStore(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key,
            collection_name=settings.qdrant_collection
        )
        logger.info(f"Connected to Qdrant at {settings.qdrant_url}")

        # Initialize RAG pipeline
        rag_pipeline = RAGPipeline(vector_store=vector_store)
        logger.info("RAG pipeline initialized")

        # Initialize book recommender
        try:
            book_recommender = BookRecommender()
            logger.info("Book recommender initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize book recommender: {e}")
            book_recommender = None

        # Initialize query recommender
        try:
            query_recommender = QueryRecommender(
                vector_store=vector_store,
                embeddings=EmbeddingFactory.create_embeddings()
            )
            logger.info("Query recommender initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize query recommender: {e}")
            query_recommender = None

        # Initialize event recommender
        try:
            event_recommender = EventRecommender(
                vector_store=vector_store,
                embeddings=EmbeddingFactory.create_embeddings()
            )
            logger.info("Event recommender initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize event recommender: {e}")
            event_recommender = None

        # Initialize audio recommender
        try:
            audio_recommender = AudioRecommender(
                vector_store=vector_store,
                embeddings=EmbeddingFactory.create_embeddings()
            )
            logger.info("Audio recommender initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize audio recommender: {e}")
            audio_recommender = None

        is_initialized = True
        logger.info("✅ Server startup complete - ready to serve requests")

    except Exception as e:
        logger.error(f"❌ Failed to initialize server: {e}")
        logger.error("Please ensure Qdrant is running and the collection exists.")
        logger.error("Run 'python dashscope_init.py' to initialize the vector database.")
        is_initialized = False

    yield

    # Shutdown
    logger.info("Shutting down RAG API...")


# Create FastAPI app
app = FastAPI(
    title="DDM RAG System API",
    description="API for Buddhist text retrieval and question answering",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for frontend
import os
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def root():
    """Redirect to frontend."""
    if os.path.exists("frontend/index.html"):
        return FileResponse("frontend/index.html")
    return {"message": "DDM RAG System API", "docs": "/docs"}


@app.get("/app.js")
async def serve_js():
    """Serve the main JavaScript file."""
    if os.path.exists("frontend/app.js"):
        return FileResponse("frontend/app.js", media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JavaScript file not found")


@app.get("/v1/models")
async def list_models():
    """OpenAI v1 compatible models endpoint."""
    return {
        "object": "list",
        "data": [
            {
                "id": "rag-model",
                "object": "model",
                "created": int(datetime.now().timestamp()),
                "owned_by": "rag-system",
                "permission": [],
                "root": "rag-model",
                "parent": None
            }
        ]
    }


@app.get("/health")
async def health_check():
    """Health check endpoint with Qdrant collection info."""
    health_info = {
        "status": "healthy",
        "initialized": is_initialized,
        "vector_store_connected": vector_store is not None,
        "pipeline_ready": rag_pipeline is not None,
        "qdrant_collection": None
    }

    # Get Qdrant collection info if connected
    if vector_store:
        try:
            collection_info = vector_store.get_collection_info()
            health_info["qdrant_collection"] = {
                "name": collection_info.get("name"),
                "points_count": collection_info.get("points_count"),
                "status": collection_info.get("status")
            }
        except Exception as e:
            logger.warning(f"Failed to get Qdrant collection info: {e}")
            health_info["qdrant_collection"] = {"error": str(e)}

    return health_info


@app.post("/query")
async def query_rag(request: QueryRequest):
    """Main RAG endpoint for question answering."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        result = rag_pipeline.query(
            question=request.question,
            top_k=request.top_k,
            filter_dict=request.filter,
            include_sources=request.include_sources
        )
        
        # Cache the query result
        global last_query_cache, query_history_cache
        cache_entry = {
            "query": request.question,
            "answer": result.get("answer"),
            "sources": result.get("sources", []),
            "timestamp": datetime.now().isoformat(),
            "computation_time": result.get("computation_time")
        }
        last_query_cache = cache_entry
        query_history_cache.append(cache_entry)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrieve")
async def retrieve_documents(request: RetrievalRequest):
    """Retrieve relevant documents without synthesis."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        documents, retrieval_time = rag_pipeline.retrieve(
            query=request.query,
            top_k=request.top_k,
            filter_dict=request.filter
        )
        
        return {
            "documents": documents,
            "count": len(documents),
            "computation_time": retrieval_time
        }
        
    except Exception as e:
        logger.error(f"Error retrieving documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/synthesize")
async def synthesize_answer(request: SynthesisRequest):
    """Synthesize an answer from provided contexts."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        answer, synthesis_time = rag_pipeline.synthesize(
            question=request.question,
            contexts=request.contexts,
            prompt_type=request.prompt_type
        )
        
        return {
            "answer": answer,
            "computation_time": synthesis_time
        }
        
    except Exception as e:
        logger.error(f"Error synthesizing answer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """OpenAI v1 compatible chat completions endpoint with RAG."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        # Extract the user's question from messages
        user_message = None
        system_message = None
        
        for msg in request.messages:
            if msg.role == "user":
                user_message = msg.content
            elif msg.role == "system":
                system_message = msg.content
        
        if not user_message:
            raise HTTPException(
                status_code=400,
                detail="No user message found in the request"
            )
        
        # Combine system message with user message if present
        question = user_message
        if system_message:
            question = f"{system_message}\n\n{question}"
        
        # Temperature parameter is ignored to avoid compatibility issues
        
        # Perform RAG query
        result = rag_pipeline.query(
            question=question,
            top_k=request.top_k,
            include_sources=request.include_sources
        )
        
        # Estimate token counts (rough approximation)
        prompt_tokens = len(question.split()) * 2  # Rough estimate
        completion_tokens = len(result["answer"].split()) * 2  # Rough estimate
        total_tokens = prompt_tokens + completion_tokens
        
        # Create OpenAI v1 compatible response
        response = ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            object="chat.completion",
            created=int(datetime.now().timestamp()),
            model=request.model or "rag-model",
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=ChatMessage(
                        role="assistant",
                        content=result["answer"]
                    ),
                    finish_reason="stop"
                )
            ],
            usage=ChatCompletionUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            ),
            system_fingerprint=f"rag-{settings.llm_provider}-{settings.embedding_model.split('/')[-1][:8]}"
        )
        
        # Add RAG-specific fields if requested
        if request.include_sources:
            response.sources = result.get("sources", [])
        response.computation_time = result.get("computation_time")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing chat completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/stream")
async def stream_rag(request: QueryRequest):
    """Streaming RAG endpoint for real-time question answering."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        async def generate_stream():
            # Variables to collect streaming data for cache
            collected_answer = []
            collected_sources = []
            computation_time = {}
            
            yield "data: {\"type\": \"start\"}\n\n"
            
            async for chunk in rag_pipeline.stream_query(
                question=request.question,
                top_k=request.top_k,
                filter_dict=request.filter,
                include_sources=request.include_sources
            ):
                yield chunk
                
                # Parse chunk to collect data for cache
                if "data: " in chunk:
                    try:
                        import json
                        data = json.loads(chunk.replace("data: ", "").strip())
                        if data.get("type") == "answer":
                            collected_answer.append(data.get("content", ""))
                        elif data.get("type") == "sources":
                            collected_sources = data.get("sources", [])
                        elif data.get("type") == "done":
                            computation_time = {
                                "synthesis_time": data.get("synthesis_time"),
                                "total_time": data.get("total_time")
                            }
                    except:
                        pass
                
            yield "data: [DONE]\n\n"
            
            # Cache the complete result after streaming
            global last_query_cache, query_history_cache
            cache_entry = {
                "query": request.question,
                "answer": "".join(collected_answer),
                "sources": collected_sources,
                "timestamp": datetime.now().isoformat(),
                "computation_time": computation_time
            }
            last_query_cache = cache_entry
            query_history_cache.append(cache_entry)
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                "Access-Control-Allow-Headers": "*",
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing streaming query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update_config")
async def update_configuration(request: ConfigUpdateRequest):
    """Update LLM or embedding configuration."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        rag_pipeline.update_configuration(
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
            embedding_provider=request.embedding_provider,
            embedding_model=request.embedding_model
        )
        
        return {
            "status": "success",
            "message": "Configuration updated successfully",
            "current_config": {
                "llm_provider": request.llm_provider or settings.llm_provider,
                "llm_model": request.llm_model or settings.llm_model,
                "embedding_provider": request.embedding_provider or settings.embedding_provider,
                "embedding_model": request.embedding_model or settings.embedding_model
            }
        }
        
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/statistics")
async def get_statistics():
    """Get statistics about the loaded data and vector store."""
    try:
        stats = {"initialized": is_initialized}
        
        if vector_store:
            stats["vector_store"] = vector_store.get_collection_info()
        
        # Get chunk statistics
        loader = ChunkDataLoader()
        stats["data"] = loader.get_chunk_statistics()
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chunk/{chunk_id}")
async def get_chunk_content(chunk_id: str):
    """Get individual chunk content by ID."""
    try:
        # Load chunk data
        loader = ChunkDataLoader()
        chunks = loader.load_all_chunks()
        
        # Find the specific chunk
        chunk = None
        for c in chunks:
            if c.get('id') == chunk_id:
                chunk = c
                break
        
        if not chunk:
            raise HTTPException(status_code=404, detail=f"Chunk {chunk_id} not found")
        
        metadata = chunk.get('metadata', {})
        
        return {
            "chunk_id": chunk_id,
            "content": chunk.get('content', ''),
            "header": chunk.get('header', ''),
            "metadata": {
                "title": metadata.get('title', ''),
                "pages": f"{metadata.get('start_page', '')}-{metadata.get('end_page', '')}" if metadata.get('start_page') else '',
                "category": metadata.get('category', ''),
                "source": metadata.get('source', ''),
                "keyphrases": metadata.get('keyphrases', [])
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching chunk content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/books/recommend")
async def recommend_books(request: BookRecommendationRequest):
    """Get book recommendations based on query."""
    if not book_recommender:
        raise HTTPException(
            status_code=503,
            detail="Book recommender not available. Please check if ddm_books.json exists."
        )
    
    try:
        recommendations = book_recommender.get_recommendations(
            query=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )
        
        return {
            "query": request.query,
            "recommendations": recommendations,
            "count": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error getting book recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/queries/related")
async def get_related_queries(request: RelatedQueriesRequest):
    """Get related queries based on semantic similarity to user query."""
    if not query_recommender:
        raise HTTPException(
            status_code=503,
            detail="Query recommender not available."
        )
    
    try:
        related_queries = query_recommender.get_related_queries(
            user_query=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )
        
        return {
            "user_query": request.query,
            "related_queries": related_queries,
            "count": len(related_queries)
        }
        
    except Exception as e:
        logger.error(f"Error getting related queries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/queries/popular")
async def get_popular_queries(limit: int = 10):
    """Get most popular queries."""
    if not query_recommender:
        raise HTTPException(
            status_code=503,
            detail="Query recommender not available."
        )
    
    try:
        popular_queries = query_recommender.get_popular_queries(limit=limit)
        return {
            "popular_queries": popular_queries,
            "count": len(popular_queries)
        }
        
    except Exception as e:
        logger.error(f"Error getting popular queries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/books/{isbn}")
async def get_book_by_isbn(isbn: str):
    """Get book details by ISBN."""
    if not book_recommender:
        raise HTTPException(
            status_code=503,
            detail="Book recommender not available."
        )
    
    try:
        book = book_recommender.get_book_by_isbn(isbn)
        if not book:
            raise HTTPException(status_code=404, detail=f"Book with ISBN {isbn} not found")
        
        return book
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting book by ISBN: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/books/random/{count}")
async def get_random_books(count: int = 5):
    """Get random book recommendations."""
    if not book_recommender:
        raise HTTPException(
            status_code=503,
            detail="Book recommender not available."
        )
    
    try:
        if count > 20:
            count = 20  # Limit to prevent abuse
        
        books = book_recommender.get_random_recommendations(count)
        return {
            "books": books,
            "count": len(books)
        }
        
    except Exception as e:
        logger.error(f"Error getting random books: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/config")
async def get_current_config():
    """Get current configuration."""
    return {
        "llm": {
            "provider": settings.llm_provider,
            "model": settings.llm_model,
            "temperature": settings.llm_temperature,
            "max_tokens": settings.llm_max_tokens
        },
        "embedding": {
            "provider": settings.embedding_provider,
            "model": settings.embedding_model,
            "dimension": settings.embedding_dimension
        },
        "retrieval": {
            "top_k": settings.retrieval_top_k
        },
        "vector_store": {
            "url": settings.qdrant_url,
            "collection": settings.qdrant_collection
        }
    }


@app.post("/events/recommend")
async def recommend_events(request: EventRecommendationRequest):
    """Get event recommendations based on query - 解行並重 (Theory and Practice Integration)."""
    if not event_recommender:
        raise HTTPException(
            status_code=503,
            detail="Event recommender not available."
        )
    
    try:
        recommendations = event_recommender.get_event_recommendations(
            user_query=request.query,
            top_k=request.top_k,
            min_similarity=request.min_similarity,
            upcoming_only=request.upcoming_only
        )
        
        return {
            "query": request.query,
            "recommendations": recommendations,
            "count": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error getting event recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events/upcoming")
async def get_upcoming_events(limit: int = 6):
    """Get upcoming events sorted by date."""
    if not event_recommender:
        raise HTTPException(
            status_code=503,
            detail="Event recommender not available."
        )
    
    try:
        events = event_recommender.get_upcoming_events(limit=limit)
        return {
            "upcoming_events": events,
            "count": len(events)
        }
        
    except Exception as e:
        logger.error(f"Error getting upcoming events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/audio/recommend")
async def recommend_audio(request: AudioRecommendationRequest):
    """Get audio recommendations based on query and answer similarity."""
    if not audio_recommender:
        raise HTTPException(
            status_code=503,
            detail="Audio recommender not available."
        )
    
    try:
        recommendations = audio_recommender.get_audio_recommendations(
            query_and_answer=request.query_and_answer,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )
        
        return {
            "query_and_answer": request.query_and_answer,
            "recommendations": recommendations,
            "count": len(recommendations)
        }
        
    except Exception as e:
        logger.error(f"Error getting audio recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/audio/{audio_id}")
async def get_audio_by_id(audio_id: str):
    """Get a specific audio chunk by ID."""
    if not audio_recommender:
        raise HTTPException(
            status_code=503,
            detail="Audio recommender not available."
        )
    
    try:
        audio = audio_recommender.get_audio_by_id(audio_id)
        if not audio:
            raise HTTPException(status_code=404, detail="Audio chunk not found")
        
        return audio
        
    except Exception as e:
        logger.error(f"Error getting audio by ID: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/query/history")
async def get_query_history(limit: int = 10):
    """Get recent query history from cache."""
    global query_history_cache
    
    # Convert deque to list and get last N items
    history = list(query_history_cache)
    
    # Return most recent first
    history.reverse()
    
    # Limit the results
    if limit > 0:
        history = history[:limit]
    
    return {
        "history": history,
        "total_cached": len(query_history_cache),
        "returned": len(history)
    }


@app.post("/translate")
async def translate_text(request: TranslationRequest):
    """Translate text to specified language (default: English)."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        # Mock translation for now - real implementation later
        mock_translation = f"[Mock Translation to {request.target_language.title()}]\n\nThis is a placeholder translation. The actual implementation will connect to a translation service to provide accurate {request.target_language} translation of the Buddhist content, preserving the meaning and context of specialized terminology."
        
        return {
            "original_text": request.text,
            "translated_text": mock_translation,
            "target_language": request.target_language,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error translating text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/summarize")
async def summarize_text(request: SummarizationRequest):
    """Summarize text into key points using LLM."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        global last_query_cache
        
        # Check if we have cached query result to summarize
        if not last_query_cache or not last_query_cache.get("answer"):
            # If no cache, use the provided text
            text_to_summarize = request.text
            if not text_to_summarize:
                raise HTTPException(
                    status_code=400,
                    detail="No text provided and no recent query result to summarize"
                )
        else:
            # Use cached answer if text not provided
            text_to_summarize = request.text if request.text else last_query_cache.get("answer")
        
        # Create summarization prompt
        summarization_prompt = f"""請將以下佛教文本內容總結成要點，只用中文：

原文：
{text_to_summarize}

請提供：
1. 3-5個主要要點
2. 一句話總結核心思想

格式要求：
• 使用「•」符號列點
• 保持佛教術語的準確性
• 簡潔明瞭，每點不超過50字
• 最後用一句話概括核心概念"""

        # Use the RAG pipeline's LLM to generate summary
        start_time = time.time()
        
        # Get the LLM from rag_pipeline
        llm = rag_pipeline.llm
        
        # Generate summary using the LLM
        summary = llm.invoke(summarization_prompt)
        
        # Extract text from AIMessage if needed
        if hasattr(summary, 'content'):
            summary_text = summary.content
        else:
            summary_text = str(summary)
        
        computation_time = time.time() - start_time
        
        return {
            "original_text": text_to_summarize[:200] + "..." if len(text_to_summarize) > 200 else text_to_summarize,
            "summary": summary_text,
            "max_length": request.max_length,
            "status": "success",
            "computation_time": computation_time,
            "source": "cached_query" if not request.text and last_query_cache else "provided_text"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class QuizRequest(BaseModel):
    user_id: Optional[str] = Field(default="anonymous", description="User identifier")


class QuizAnswerRequest(BaseModel):
    quiz_id: str = Field(..., description="Quiz ID")
    answers: List[str] = Field(..., description="User's answers to quiz questions")
    user_id: Optional[str] = Field(default="anonymous", description="User identifier")


@app.post("/quiz/generate")
async def generate_quiz(request: QuizRequest):
    """Generate quiz questions from highest-ranking reference chunk."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        global last_query_cache
        
        # Check if we have cached query result with sources
        if not last_query_cache or not last_query_cache.get("sources"):
            raise HTTPException(
                status_code=400,
                detail="No reference materials available. Please make a query first."
            )
        
        # Get the highest-ranking reference chunk
        sources = last_query_cache.get("sources", [])
        if not sources:
            raise HTTPException(
                status_code=400,
                detail="No reference sources found in last query."
            )
        
        # Get highest ranking chunk (first one in the sorted list)
        highest_chunk = sources[0]
        chunk_content = highest_chunk.get("text", "") or highest_chunk.get("content", "")
        chunk_title = highest_chunk.get("title", "")
        
        if not chunk_content:
            raise HTTPException(
                status_code=400,
                detail=f"Reference chunk has no content. Available keys: {list(highest_chunk.keys())}"
            )
        
        # Create quiz generation prompt
        quiz_prompt = f"""基於以下佛教文本，請生成2-3個深入思考的問題。這些問題應該鼓勵讀者仔細閱讀並理解文本的深層含義。

文本標題：{chunk_title}

文本內容：
{chunk_content}

請生成的問題要求：
1. 2-3個問題即可
2. 問題應該測試對文本核心概念的理解
3. 問題應該引導深入思考，而非簡單記憶
4. 用中文提問
5. 問題應該是開放式的，允許多種合理的回答

請按以下格式輸出：
問題1：[問題內容]
問題2：[問題內容]
問題3：[問題內容]（如果有的話）"""

        # Generate quiz using LLM
        start_time = time.time()
        llm = rag_pipeline.llm
        quiz_response = llm.invoke(quiz_prompt)
        
        # Extract text from response
        if hasattr(quiz_response, 'content'):
            quiz_text = quiz_response.content
        else:
            quiz_text = str(quiz_response)
        
        # Parse questions from response
        questions = []
        lines = quiz_text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if line and ('問題' in line or line.startswith('Q') or line.startswith('q')):
                # Clean up question text
                question = line.split('：', 1)[-1].strip()
                if question:
                    questions.append(question)
        
        if not questions:
            # Fallback: split by numbers or common patterns
            import re
            question_matches = re.findall(r'[12３]\.\s*(.+)', quiz_text)
            if question_matches:
                questions = [q.strip() for q in question_matches]
        
        # Generate unique quiz ID
        quiz_id = f"quiz_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        computation_time = time.time() - start_time
        
        return {
            "quiz_id": quiz_id,
            "questions": questions,
            "reference_chunk": {
                "title": chunk_title,
                "content": chunk_content[:500] + "..." if len(chunk_content) > 500 else chunk_content,
                "chunk_id": highest_chunk.get("chunk_id", "")
            },
            "source_query": last_query_cache.get("query", ""),
            "computation_time": computation_time,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/quiz/evaluate")
async def evaluate_quiz_answers(request: QuizAnswerRequest):
    """Evaluate user's quiz answers using LLM."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python dashscope_init.py' if needed."
        )
    
    try:
        if not request.answers:
            raise HTTPException(
                status_code=400,
                detail="No answers provided."
            )
        
        # Get the reference chunk from cache (assuming it's still the same)
        global last_query_cache
        if not last_query_cache or not last_query_cache.get("sources"):
            raise HTTPException(
                status_code=400,
                detail="Reference material no longer available."
            )
        
        highest_chunk = last_query_cache.get("sources", [])[0]
        chunk_content = highest_chunk.get("text", "")
        chunk_title = highest_chunk.get("title", "")
        
        # Create evaluation prompt
        answers_text = "\n".join([f"答案{i+1}：{answer}" for i, answer in enumerate(request.answers)])
        
        evaluation_prompt = f"""請評估以下用戶對佛教文本理解問題的回答。

參考文本標題：{chunk_title}

參考文本內容：
{chunk_content}

用戶的回答：
{answers_text}

請根據以下標準評估：
1. 理解準確性：用戶是否正確理解了文本的核心概念？
2. 深度思考：回答是否展現了深入的思考和洞察？
3. 佛學知識：是否適當運用了佛教術語和概念？

請為每個答案提供：
- 評分（1-5分，5分最高）
- 簡短評語（1-2句）
- 鼓勵的話語

最後提供整體評價和修行建議。

請用中文回覆，語氣要溫和且鼓勵性。"""

        # Evaluate using LLM
        start_time = time.time()
        llm = rag_pipeline.llm
        evaluation_response = llm.invoke(evaluation_prompt)
        
        # Extract text from response
        if hasattr(evaluation_response, 'content'):
            evaluation_text = evaluation_response.content
        else:
            evaluation_text = str(evaluation_response)
        
        computation_time = time.time() - start_time
        
        # Store quiz attempt in practice journey (mock storage for now)
        quiz_attempt = {
            "quiz_id": request.quiz_id,
            "user_id": request.user_id,
            "answers": request.answers,
            "evaluation": evaluation_text,
            "reference_chunk": {
                "title": chunk_title,
                "chunk_id": highest_chunk.get("chunk_id", "")
            },
            "timestamp": datetime.now().isoformat(),
            "computation_time": computation_time
        }
        
        # TODO: In a real system, store this in a database
        # For now, we'll just log it
        logger.info(f"Quiz attempt logged for user {request.user_id}: {request.quiz_id}")
        
        # Random Zen master response (10% chance)
        zen_master_response = None
        if random.random() < 0.1:  # 10% chance
            zen_master_responses = [
                "善哉！你的回答展現了真誠的探索精神。繼續在日常生活中實踐這些智慧吧。",
                "很好！記住，理解佛法的真正意義在於將它融入你的心靈和行為中。",
                "不錯的思考！修行的路上，保持初學者的心，每天都是新的開始。",
                "你的回答很用心。在禪修中，最重要的是當下的覺察和慈悲的心。",
                "很好！聖嚴法師常說：「面對它、接受它、處理它、放下它。」願你在生活中實踐這份智慧。"
            ]
            zen_master_response = random.choice(zen_master_responses)
        
        return {
            "quiz_id": request.quiz_id,
            "evaluation": evaluation_text,
            "zen_master_response": zen_master_response,
            "practice_journey_logged": True,
            "computation_time": computation_time,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error evaluating quiz answers: {e}")
        raise HTTPException(status_code=500, detail=str(e))
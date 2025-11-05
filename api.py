from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal, Union
import logging
import time
import uuid
from datetime import datetime
import random
from contextlib import asynccontextmanager
import os

# Auth imports
from auth import (
    register_user, login_user, verify_email,
    get_user_profile, get_current_user,
    UserRegister, UserLogin, EmailVerification
)

from config import settings
from data_loader import ChunkDataLoader
from vector_store import QdrantVectorStore
from rag_pipeline import RAGPipeline
from llm_factory import EmbeddingFactory
from book_recommender import BookRecommender
from query_recommender import QueryRecommender
from event_recommender import EventRecommender
from audio_recommender import AudioRecommender
from query_logger import get_query_logger
from db_helpers import (
    save_quiz_attempt,
    get_quiz_history,
    get_quiz_attempt_detail,
    get_quiz_statistics,
    update_user_achievement,
    check_and_create_master_comment
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize query logger
ENABLE_QUERY_LOGGING = os.getenv("ENABLE_QUERY_LOGGING", "true").lower() in ("true", "1", "yes")
QUERY_LOG_DIR = os.getenv("QUERY_LOG_DIR", "logs")
query_logger = get_query_logger(log_dir=QUERY_LOG_DIR, enable_file_logging=ENABLE_QUERY_LOGGING)

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

# Cache for summarization results (text_hash -> summary_result)
import hashlib
summarization_cache = {}  # Dict[str, dict] - stores summary by text hash


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
        logger.error("Run 'python init_collections.py all' to initialize the vector database.")
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
# Use frontend_v2 (modern UI with Perplexity-style interface)
if os.path.exists("frontend_v2"):
    app.mount("/static", StaticFiles(directory="frontend_v2"), name="static")
elif os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="static")


@app.get("/")
async def root():
    """Redirect to frontend."""
    # Prefer frontend_v2 if available
    if os.path.exists("frontend_v2/index.html"):
        return FileResponse("frontend_v2/index.html")
    elif os.path.exists("frontend/index.html"):
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
    # model, embedding info
    


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


# ============================================================================
# Authentication Endpoints
# ============================================================================

@app.post("/auth/register")
async def register(user: UserRegister, background_tasks: BackgroundTasks):
    """
    Register a new user

    - **email**: Valid email address
    - **password**: Strong password (min 8 characters)
    - **full_name**: User's full name
    - **ddm_student_id**: Optional DDM student ID
    """
    return await register_user(user, background_tasks)


@app.post("/auth/login")
async def login(user: UserLogin):
    """
    Login with email and password

    Returns JWT access token
    """
    return await login_user(user)


@app.post("/auth/verify-email")
async def verify(verification: EmailVerification):
    """
    Verify email address with token from email (POST version)

    - **token**: Verification token from email link
    """
    return await verify_email(verification)


@app.get("/verify-email", response_class=HTMLResponse)
async def verify_email_get(token: str):
    """
    Verify email address via GET request (for email links)

    This endpoint handles verification links from emails.
    """
    verification = EmailVerification(token=token)
    result = await verify_email(verification)

    # Return HTML page for better UX
    if "message" in result and "verified successfully" in result["message"]:
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Email Verified - 佛學入門</title>
            <style>
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    min-height: 100vh;
                    margin: 0;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                }
                .container {
                    background: white;
                    padding: 40px;
                    border-radius: 10px;
                    box-shadow: 0 10px 40px rgba(0,0,0,0.1);
                    text-align: center;
                    max-width: 500px;
                }
                .success-icon {
                    font-size: 64px;
                    color: #10b981;
                    margin-bottom: 20px;
                }
                h1 {
                    color: #1f2937;
                    margin-bottom: 15px;
                }
                p {
                    color: #6b7280;
                    line-height: 1.6;
                    margin-bottom: 25px;
                }
                .button {
                    display: inline-block;
                    background: linear-gradient(to right, #667eea, #764ba2);
                    color: white;
                    padding: 12px 30px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: 500;
                    transition: transform 0.2s;
                }
                .button:hover {
                    transform: translateY(-2px);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="success-icon">✓</div>
                <h1>電子郵件驗證成功！</h1>
                <p>您的帳號已成功驗證。現在您可以登入並開始使用佛學入門學習平台。</p>
                <a href="/" class="button">前往首頁</a>
            </div>
        </body>
        </html>
        """
    else:
        return result


@app.get("/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    """
    Get current user profile (requires authentication)

    Header: Authorization: Bearer <token>
    """
    return await get_user_profile(current_user)


# ============================================================================
# FAQ Endpoints
# ============================================================================

# Load FAQ questions on startup
faq_questions = []
try:
    import json
    with open('faq.json', 'r', encoding='utf-8') as f:
        faq_data = json.load(f)
        faq_questions = faq_data.get('questions', [])
    logger.info(f"Loaded {len(faq_questions)} FAQ questions")
except Exception as e:
    logger.warning(f"Failed to load FAQ questions: {e}")


@app.get("/faq")
async def get_faq(
    limit: Optional[int] = 5,
    random_sample: Optional[bool] = True,
    offset: Optional[int] = 0
):
    """
    Get FAQ questions from the Buddhist dataset

    - **limit**: Number of questions to return (default: 5)
    - **random_sample**: Return random questions (default: True)
    - **offset**: Starting offset for sequential access (default: 0)
    """
    if not faq_questions:
        raise HTTPException(status_code=500, detail="FAQ questions not loaded")

    if random_sample:
        # Return random sample
        sample_size = min(limit, len(faq_questions))
        selected = random.sample(faq_questions, sample_size)
    else:
        # Return sequential questions with offset
        start = offset
        end = min(offset + limit, len(faq_questions))
        selected = faq_questions[start:end]

    return {
        "questions": selected,
        "total_count": len(faq_questions),
        "returned_count": len(selected)
    }


# ============================================================================
# Helper Functions for User Tracking
# ============================================================================

def get_client_ip(request: Request) -> str:
    """Extract client IP from request, considering proxies"""
    # Check for X-Forwarded-For header (proxy/load balancer)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded.split(",")[0].strip()

    # Check for X-Real-IP header (nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    return "unknown"


async def get_user_info(request: Request) -> Dict[str, Optional[str]]:
    """
    Extract user identification info from request

    Returns:
        Dict with ip_address and user_email (if authenticated)
    """
    ip_address = get_client_ip(request)
    user_email = None

    # Try to get authenticated user from Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            # Use the existing auth function to validate token
            from jose import jwt
            from auth import SECRET_KEY, ALGORITHM

            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_email = payload.get("sub") or payload.get("email")  # JWT standard uses "sub" for subject (email)
        except Exception:
            # Token invalid or expired, keep as anonymous
            pass

    return {
        "ip_address": ip_address,
        "user_email": user_email
    }


# ============================================================================
# RAG Endpoints
# ============================================================================

@app.post("/query")
async def query_rag(request: QueryRequest, http_request: Request):
    """Main RAG endpoint for question answering with query logging."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
        )

    # Get user identification
    user_info = await get_user_info(http_request)

    try:
        result = rag_pipeline.query(
            question=request.question,
            top_k=request.top_k,
            filter_dict=request.filter,
            include_sources=request.include_sources
        )

        # Log the query and result
        if ENABLE_QUERY_LOGGING:
            query_logger.log_query(
                query=request.question,
                result=result,
                ip_address=user_info["ip_address"],
                user_email=user_info["user_email"],
                retrieval_mode="rag",
                metadata={
                    "top_k": request.top_k,
                    "filter": request.filter,
                    "include_sources": request.include_sources
                }
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
        # Log the error
        if ENABLE_QUERY_LOGGING:
            query_logger.log_error(
                query=request.question,
                error=e,
                ip_address=user_info["ip_address"],
                user_email=user_info["user_email"],
                metadata={"top_k": request.top_k}
            )

        logger.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/retrieve")
async def retrieve_documents(request: RetrievalRequest):
    """Retrieve relevant documents without synthesis."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
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
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
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
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
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
async def stream_rag(request: QueryRequest, http_request: Request):
    """Streaming RAG endpoint for real-time question answering."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
        )

    # Extract user info for logging
    user_info = await get_user_info(http_request)

    try:
        async def generate_stream():
            # Variables to collect streaming data for cache and logging
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

            # Build result for caching and logging
            final_answer = "".join(collected_answer)
            result = {
                "answer": final_answer,
                "sources": collected_sources,
                "computation_time": computation_time.get("total_time", 0),
                "cached": False
            }

            # Cache the complete result after streaming
            global last_query_cache, query_history_cache
            cache_entry = {
                "query": request.question,
                "answer": final_answer,
                "sources": collected_sources,
                "timestamp": datetime.now().isoformat(),
                "computation_time": computation_time
            }
            last_query_cache = cache_entry
            query_history_cache.append(cache_entry)

            # Log the query after streaming completes
            if ENABLE_QUERY_LOGGING:
                try:
                    query_logger.log_query(
                        query=request.question,
                        result=result,
                        ip_address=user_info["ip_address"],
                        user_email=user_info["user_email"],
                        retrieval_mode="rag_stream",
                        metadata={
                            "top_k": request.top_k,
                            "include_sources": request.include_sources,
                            "synthesis_time": computation_time.get("synthesis_time"),
                            "total_time": computation_time.get("total_time")
                        }
                    )
                except Exception as log_error:
                    logger.error(f"Failed to log query: {log_error}")

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

        # Log the error
        if ENABLE_QUERY_LOGGING:
            try:
                query_logger.log_error(
                    query=request.question,
                    error=e,
                    ip_address=user_info["ip_address"],
                    user_email=user_info["user_email"],
                    metadata={
                        "top_k": request.top_k,
                        "endpoint": "/query/stream"
                    }
                )
            except Exception as log_error:
                logger.error(f"Failed to log error: {log_error}")

        raise HTTPException(status_code=500, detail=str(e))


@app.post("/update_config")
async def update_configuration(request: ConfigUpdateRequest):
    """Update LLM or embedding configuration."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
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


@app.get("/query/statistics")
async def get_query_statistics(date: Optional[str] = None):
    """
    Get query logging statistics for a specific date or today.

    Args:
        date: Date in YYYY-MM-DD format (default: today)

    Returns:
        Query statistics including total queries, user counts, avg times, etc.
    """
    if not ENABLE_QUERY_LOGGING:
        return {
            "error": "Query logging is disabled",
            "message": "Set ENABLE_QUERY_LOGGING=true in .env to enable"
        }

    try:
        stats = query_logger.get_stats(date)
        return stats
    except Exception as e:
        logger.error(f"Error getting query statistics: {e}")
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
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
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
    """Summarize text into key points using LLM with caching."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
        )

    try:
        global last_query_cache, summarization_cache

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

        # Create hash of the text for caching
        text_hash = hashlib.md5(text_to_summarize.encode('utf-8')).hexdigest()

        # Check if summary is already cached
        if text_hash in summarization_cache:
            logger.info(f"Returning cached summary for text hash: {text_hash[:8]}...")
            cached_result = summarization_cache[text_hash].copy()
            cached_result["cached"] = True
            cached_result["computation_time"] = 0.0  # Instant from cache
            return cached_result

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

        result = {
            "original_text": text_to_summarize[:200] + "..." if len(text_to_summarize) > 200 else text_to_summarize,
            "summary": summary_text,
            "max_length": request.max_length,
            "status": "success",
            "computation_time": computation_time,
            "source": "cached_query" if not request.text and last_query_cache else "provided_text",
            "cached": False
        }

        # Store result in cache
        summarization_cache[text_hash] = result.copy()
        logger.info(f"Cached summary for text hash: {text_hash[:8]}... (cache size: {len(summarization_cache)})")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error summarizing text: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class QuizRequest(BaseModel):
    user_id: Optional[str] = Field(default="anonymous", description="User identifier")


class QuizAnswer(BaseModel):
    question_index: int = Field(..., description="Index of the question (0-based)")
    question_type: str = Field(..., description="Type of question: 'multiple_choice' or 'text'")
    answer: str = Field(..., description="User's answer (option letter for multiple choice, text for text questions)")


class QuizAnswerRequest(BaseModel):
    quiz_id: str = Field(..., description="Quiz ID")
    questions: List[Dict[str, Any]] = Field(..., description="The original quiz questions for reference")
    answers: List[QuizAnswer] = Field(..., description="User's answers to quiz questions")
    user_id: Optional[str] = Field(default="anonymous", description="User identifier")


@app.post("/quiz/generate")
async def generate_quiz(request: QuizRequest):
    """Generate mixed-format quiz questions (multiple choice + text-based) from highest-ranking reference chunk."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
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

        # Create quiz generation prompt with mixed question types
        quiz_prompt = f"""基於以下佛教文本，請生成3個測驗問題，包括選擇題和文字題。

文本標題：{chunk_title}

文本內容：
{chunk_content}

請生成以下格式的問題：
1. 一個多選題（測試基本概念理解）
2. 一個多選題（測試進階理解）
3. 一個開放式文字題（測試深度思考與應用）

**格式要求**：
對於多選題，請使用以下JSON格式：
{{
  "type": "multiple_choice",
  "question": "問題內容",
  "options": ["A. 選項1", "B. 選項2", "C. 選項3", "D. 選項4"],
  "correct_answer": "A",
  "explanation": "正確答案的解釋"
}}

對於文字題，請使用以下JSON格式：
{{
  "type": "text",
  "question": "問題內容",
  "reference_answer": "參考答案要點（學員可以有不同表達，但應包含這些核心概念）"
}}

**內容要求**：
1. 多選題應基於文本的核心概念，每題4個選項
2. 選項應有適度難度，避免過於明顯
3. 文字題應引導深入思考，鼓勵結合個人經驗或理解
4. 所有問題用繁體中文

請直接輸出包含3個問題的JSON陣列，格式如下：
[
  {{多選題1}},
  {{多選題2}},
  {{文字題}}
]"""

        # Generate quiz using LLM
        start_time = time.time()
        llm = rag_pipeline.llm
        quiz_response = llm.invoke(quiz_prompt)

        # Extract text from response
        if hasattr(quiz_response, 'content'):
            quiz_text = quiz_response.content
        else:
            quiz_text = str(quiz_response)

        # Parse JSON response
        import json
        import re

        # Try to extract JSON array from response
        try:
            # Remove markdown code blocks if present
            quiz_text_clean = re.sub(r'```json\s*|\s*```', '', quiz_text).strip()

            # Try to find JSON array pattern
            json_match = re.search(r'\[[\s\S]*\]', quiz_text_clean)
            if json_match:
                quiz_text_clean = json_match.group(0)

            questions = json.loads(quiz_text_clean)

            # Validate structure
            if not isinstance(questions, list):
                raise ValueError("Response is not a list")

            # Validate each question
            for i, q in enumerate(questions):
                if not isinstance(q, dict):
                    raise ValueError(f"Question {i+1} is not a dict")
                if "type" not in q or "question" not in q:
                    raise ValueError(f"Question {i+1} missing required fields")

                # Validate multiple choice questions
                if q["type"] == "multiple_choice":
                    if "options" not in q or "correct_answer" not in q:
                        raise ValueError(f"Multiple choice question {i+1} missing options or correct_answer")
                    if not isinstance(q["options"], list) or len(q["options"]) != 4:
                        raise ValueError(f"Multiple choice question {i+1} must have exactly 4 options")

                # Validate text questions
                elif q["type"] == "text":
                    if "reference_answer" not in q:
                        raise ValueError(f"Text question {i+1} missing reference_answer")

        except (json.JSONDecodeError, ValueError) as parse_error:
            logger.error(f"Failed to parse quiz JSON: {parse_error}")
            logger.error(f"Raw response: {quiz_text}")

            # Fallback: generate simple text questions
            questions = [
                {
                    "type": "text",
                    "question": f"根據「{chunk_title}」的內容，請說明其核心概念。",
                    "reference_answer": "請參考文本內容進行回答"
                },
                {
                    "type": "text",
                    "question": "這段文本對你的修行或生活有什麼啟發？",
                    "reference_answer": "開放式回答，可結合個人經驗"
                }
            ]

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
async def evaluate_quiz_answers(request: QuizAnswerRequest, http_request: Request):
    """Evaluate user's mixed-format quiz answers (multiple choice + text) with scoring."""
    if not is_initialized or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="System not initialized. Please ensure Qdrant is running with initialized data. Run 'python init_collections.py all' if needed."
        )

    # Get user identification
    user_info = await get_user_info(http_request)

    try:
        if not request.answers:
            raise HTTPException(
                status_code=400,
                detail="No answers provided."
            )

        if len(request.answers) != len(request.questions):
            raise HTTPException(
                status_code=400,
                detail=f"Number of answers ({len(request.answers)}) does not match number of questions ({len(request.questions)})"
            )

        # Get the reference chunk from cache
        global last_query_cache
        if not last_query_cache or not last_query_cache.get("sources"):
            raise HTTPException(
                status_code=400,
                detail="Reference material no longer available."
            )

        highest_chunk = last_query_cache.get("sources", [])[0]
        chunk_content = highest_chunk.get("text", "") or highest_chunk.get("content", "")
        chunk_title = highest_chunk.get("title", "")

        # Evaluate each answer
        start_time = time.time()
        evaluations = []
        total_score = 0
        max_score = 0

        for i, (question, answer) in enumerate(zip(request.questions, request.answers)):
            question_type = question.get("type")
            question_text = question.get("question")
            user_answer = answer.answer

            if question_type == "multiple_choice":
                # Auto-grade multiple choice
                correct_answer = question.get("correct_answer")
                explanation = question.get("explanation", "")
                is_correct = user_answer.upper() == correct_answer.upper()
                score = 1 if is_correct else 0
                max_score += 1

                evaluations.append({
                    "question_index": i,
                    "question_type": "multiple_choice",
                    "question": question_text,
                    "user_answer": user_answer,
                    "correct_answer": correct_answer,
                    "is_correct": is_correct,
                    "score": score,
                    "max_score": 1,
                    "explanation": explanation,
                    "feedback": "正確！" if is_correct else f"不正確。正確答案是 {correct_answer}。"
                })

                total_score += score

            elif question_type == "text":
                # LLM-based evaluation for text questions
                reference_answer = question.get("reference_answer", "")

                # Pre-check: Reject obviously insufficient answers
                if len(user_answer) < 10:
                    evaluations.append({
                        "question_index": i,
                        "question_type": "text",
                        "question": question_text,
                        "user_answer": user_answer,
                        "reference_answer": reference_answer,
                        "score": 0,
                        "max_score": 5,
                        "understanding_score": 0,
                        "depth_score": 0,
                        "expression_score": 0,
                        "feedback": "回答過於簡短，未能展現對問題的理解與思考。請提供更完整的答案。",
                        "strengths": "回答過於簡短，未見明顯優點",
                        "improvements": "請認真閱讀問題，結合文本內容和個人理解，提供至少50字以上的完整回答。"
                    })
                    total_score += 0
                    max_score += 5
                    continue

                evaluation_prompt = f"""請嚴格評估以下用戶對佛教文本問題的回答。

參考文本標題：{chunk_title}

參考文本內容（前500字）：
{chunk_content[:500]}...

問題：
{question_text}

參考答案要點：
{reference_answer}

用戶的回答：
{user_answer}

**評分標準（總分5分，請嚴格評分）**：

1. **理解準確性（0-2分）**：
   - 0分：完全未理解或答非所問（如「不知道」、「太難」、單字回答）
   - 1分：僅有基本理解，未涉及核心概念
   - 2分：準確理解文本核心概念，答案與問題相關

2. **深度思考（0-2分）**：
   - 0分：無任何思考，敷衍回答（如「好」、「ok」、過短回答）
   - 1分：有基本思考但未深入，缺乏個人見解
   - 2分：展現深入思考、結合個人經驗或洞察

3. **表達完整性（0-1分）**：
   - 0分：回答過短（少於20字）、不完整、或語意不清
   - 1分：表達清晰完整，邏輯連貫

**重要提示**：
- 對於敷衍回答（如「ok」、「好」、「太難」、單字）必須給0分
- 回答字數少於20字通常無法獲得高分
- 未提及參考答案要點的回答最多只能得1-2分
- 務必嚴格評分，不要過度寬容

請直接輸出JSON格式，包含以下欄位：
{{
  "score": 0,  // 總分 0-5（三項分數相加）
  "understanding_score": 0,  // 理解準確性 0-2
  "depth_score": 0,  // 深度思考 0-2
  "expression_score": 0,  // 表達完整性 0-1
  "feedback": "具體評語（2-3句，客觀指出問題）",
  "strengths": "回答的優點（若無則說明「回答過於簡短，未見明顯優點」）",
  "improvements": "具體改進建議（必須提供）"
}}

請用繁體中文回覆。"""

                # Use LLM to evaluate
                llm = rag_pipeline.llm
                eval_response = llm.invoke(evaluation_prompt)

                # Extract text from response
                if hasattr(eval_response, 'content'):
                    eval_text = eval_response.content
                else:
                    eval_text = str(eval_response)

                # Parse JSON response
                import json
                import re

                try:
                    # Remove markdown code blocks if present
                    eval_text_clean = re.sub(r'```json\s*|\s*```', '', eval_text).strip()

                    # Try to find JSON object pattern
                    json_match = re.search(r'\{[\s\S]*\}', eval_text_clean)
                    if json_match:
                        eval_text_clean = json_match.group(0)

                    eval_result = json.loads(eval_text_clean)

                    # Validate and extract scores
                    text_score = eval_result.get("score", 3)
                    understanding = eval_result.get("understanding_score", 1)
                    depth = eval_result.get("depth_score", 1)
                    expression = eval_result.get("expression_score", 1)
                    feedback = eval_result.get("feedback", "感謝你的回答！")
                    strengths = eval_result.get("strengths", "")
                    improvements = eval_result.get("improvements", "")

                except (json.JSONDecodeError, ValueError) as parse_error:
                    logger.error(f"Failed to parse evaluation JSON: {parse_error}")
                    logger.error(f"Raw response: {eval_text}")

                    # Fallback scoring
                    text_score = 3
                    understanding = 1
                    depth = 1
                    expression = 1
                    feedback = "感謝你的認真回答！繼續深入思考佛法的智慧。"
                    strengths = "展現了學習的誠意"
                    improvements = ""

                evaluations.append({
                    "question_index": i,
                    "question_type": "text",
                    "question": question_text,
                    "user_answer": user_answer,
                    "reference_answer": reference_answer,
                    "score": text_score,
                    "max_score": 5,
                    "understanding_score": understanding,
                    "depth_score": depth,
                    "expression_score": expression,
                    "feedback": feedback,
                    "strengths": strengths,
                    "improvements": improvements
                })

                total_score += text_score
                max_score += 5

        # Calculate percentage
        percentage = (total_score / max_score * 100) if max_score > 0 else 0

        # Overall feedback based on percentage
        if percentage >= 90:
            overall_grade = "優秀"
            overall_feedback = "非常優秀！你對佛法的理解深刻且全面。"
        elif percentage >= 75:
            overall_grade = "良好"
            overall_feedback = "很好！你展現了扎實的理解，繼續精進。"
        elif percentage >= 60:
            overall_grade = "及格"
            overall_feedback = "不錯！在理解上有一定基礎，建議多閱讀相關文本。"
        else:
            overall_grade = "需加強"
            overall_feedback = "繼續努力！多花時間深入理解佛法的核心概念。"

        computation_time = time.time() - start_time

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

        # Save quiz attempt to database
        attempt_id = None
        try:
            # Get user_id from JWT token if available
            user_uuid = None
            if user_info.get("user_email"):
                # Try to get user_id from database
                from auth import get_db_connection
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute("SELECT id FROM users WHERE email = %s", (user_info["user_email"],))
                    result = cur.fetchone()
                    if result:
                        user_uuid = result['id']
                    conn.close()
                except Exception as e:
                    logger.warning(f"Could not get user_id: {e}")

            attempt_id = save_quiz_attempt(
                quiz_id=request.quiz_id,
                user_id=user_uuid,
                user_email=user_info.get("user_email") or "anonymous",
                source_query=last_query_cache.get("query", ""),
                reference_chunk_title=chunk_title,
                reference_chunk_id=highest_chunk.get("chunk_id", ""),
                questions=request.questions,
                answers=[a.dict() for a in request.answers],
                evaluations=evaluations,
                total_score=total_score,
                max_score=max_score,
                percentage=percentage,
                overall_grade=overall_grade,
                overall_feedback=overall_feedback,
                zen_master_response=zen_master_response,
                time_spent_seconds=0,  # TODO: Get from frontend
                computation_time=computation_time
            )

            logger.info(f"Saved quiz attempt {attempt_id} for {user_info.get('user_email', 'anonymous')}: Score {total_score}/{max_score}")

            # Update achievements
            if user_info.get("user_email") and user_info["user_email"] != "anonymous":
                try:
                    # Get current quiz count
                    from db_helpers import get_db_connection
                    conn = get_db_connection()
                    cur = conn.cursor()
                    cur.execute(
                        "SELECT COUNT(*) as count FROM quiz_attempts WHERE user_email = %s",
                        (user_info["user_email"],)
                    )
                    quiz_count = cur.fetchone()['count']
                    conn.close()

                    # Update quiz count achievements
                    update_user_achievement(user_info["user_email"], "first_quiz", quiz_count)
                    update_user_achievement(user_info["user_email"], "quiz_count_10", quiz_count)
                    update_user_achievement(user_info["user_email"], "quiz_count_50", quiz_count)
                    update_user_achievement(user_info["user_email"], "quiz_count_100", quiz_count)

                    # Update perfect score achievement
                    if percentage == 100:
                        conn = get_db_connection()
                        cur = conn.cursor()
                        cur.execute(
                            "SELECT COUNT(*) as count FROM quiz_attempts WHERE user_email = %s AND percentage = 100",
                            (user_info["user_email"],)
                        )
                        perfect_count = cur.fetchone()['count']
                        conn.close()

                        update_user_achievement(user_info["user_email"], "perfect_score", perfect_count)
                        update_user_achievement(user_info["user_email"], "perfect_score_3", perfect_count)

                    # Check for master comments
                    master_comment = check_and_create_master_comment(
                        user_email=user_info["user_email"],
                        user_id=user_uuid
                    )
                    if master_comment:
                        logger.info(f"Created master comment: {master_comment['title']}")

                except Exception as e:
                    logger.error(f"Error updating achievements: {e}")

        except Exception as e:
            logger.error(f"Error saving quiz attempt to database: {e}")
            # Continue even if database save fails

        return {
            "quiz_id": request.quiz_id,
            "evaluations": evaluations,
            "total_score": total_score,
            "max_score": max_score,
            "percentage": round(percentage, 2),
            "overall_grade": overall_grade,
            "overall_feedback": overall_feedback,
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

@app.get("/quiz/history")
async def get_quiz_history(
    http_request: Request,
    limit: int = 50,
    offset: int = 0
):
    """Get paginated quiz history for the authenticated user."""
    # Get user identification
    user_info = await get_user_info(http_request)

    if not user_info.get("user_email") or user_info["user_email"] == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="Authentication required to view quiz history"
        )

    try:
        from db_helpers import get_quiz_history

        result = get_quiz_history(
            user_email=user_info["user_email"],
            limit=limit,
            offset=offset
        )

        return {
            "total": result["total"],
            "limit": limit,
            "offset": offset,
            "quizzes": result["quizzes"],
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error getting quiz history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/quiz/history/{attempt_id}")
async def get_quiz_attempt_detail(
    attempt_id: int,
    http_request: Request
):
    """Get detailed quiz attempt by ID."""
    # Get user identification
    user_info = await get_user_info(http_request)

    if not user_info.get("user_email") or user_info["user_email"] == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="Authentication required to view quiz details"
        )

    try:
        from db_helpers import get_quiz_attempt_detail

        result = get_quiz_attempt_detail(
            attempt_id=attempt_id,
            user_email=user_info["user_email"]
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Quiz attempt {attempt_id} not found"
            )

        return {
            "quiz_attempt": result,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quiz attempt detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/quiz/statistics")
async def get_quiz_statistics(http_request: Request):
    """Get quiz statistics for the authenticated user."""
    # Get user identification
    user_info = await get_user_info(http_request)

    if not user_info.get("user_email") or user_info["user_email"] == "anonymous":
        raise HTTPException(
            status_code=401,
            detail="Authentication required to view statistics"
        )

    try:
        from db_helpers import get_quiz_statistics

        stats = get_quiz_statistics(user_email=user_info["user_email"])

        return {
            "statistics": stats,
            "status": "success"
        }

    except Exception as e:
        logger.error(f"Error getting quiz statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


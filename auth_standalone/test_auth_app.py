"""
Standalone test application for 佛學普化小助手 authentication system
Run this to test the auth system independently
"""
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

# Import our auth components
from database import create_db_and_tables, User, UserRead, UserCreate, UserUpdate
from auth_backend import auth_backend, fastapi_users, current_active_user
from email_service import email_service
from config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events - create tables on startup"""
    print("🚀 Starting 佛學普化小助手 Auth Test Server...")
    await create_db_and_tables()
    print("✅ Database tables created")
    print(f"📧 Email service initialized (Debug mode: {email_service.debug_mode})")
    yield
    print("🛑 Shutting down auth server...")

# Create FastAPI app
app = FastAPI(
    title="佛學普化小助手 - Authentication API",
    description="Authentication system test server",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include FastAPI-Users routers
app.include_router(
    fastapi_users.get_auth_router(auth_backend), 
    prefix="/auth/jwt", 
    tags=["auth"]
)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Test endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "🙏 佛學普化小助手 Authentication API",
        "docs": "/docs",
        "version": "1.0.0",
        "endpoints": {
            "register": "/auth/register",
            "login": "/auth/jwt/login", 
            "logout": "/auth/jwt/logout",
            "forgot_password": "/auth/forgot-password",
            "reset_password": "/auth/reset-password",
            "profile": "/users/me"
        }
    }

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "database": "connected",
        "email_service": "active" if email_service.api_key else "debug_mode"
    }

@app.get("/protected")
async def protected_route(user: User = Depends(current_active_user)):
    """Test protected route"""
    return {
        "message": f"Hello {user.dharma_name or user.username}! 🙏",
        "user_id": str(user.id),
        "email": user.email,
        "practice_stats": {
            "total_minutes": user.total_practice_minutes,
            "total_sessions": user.total_sessions,
            "current_streak": user.current_streak_days
        }
    }

@app.post("/test-email")
async def test_email(email: str):
    """Test email sending (for debugging)"""
    try:
        success = await email_service.send_password_reset_email(
            email=email,
            token="test-token-123",
            user_name="測試用戶"
        )
        return {
            "success": success,
            "message": "Email sent successfully" if success else "Email failed",
            "debug_mode": email_service.debug_mode
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    print("🚀 Starting Authentication Test Server...")
    print(f"📊 Debug mode: {settings.debug}")
    print(f"📧 Email debug mode: {email_service.debug_mode}")
    print("🌐 Server will be available at: http://localhost:8001")
    print("📚 API Documentation: http://localhost:8001/docs")
    
    uvicorn.run(
        "test_auth_app:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info"
    )
"""
Minimal API server for testing authentication endpoints
Run with: python test_api_server.py
"""

from fastapi import FastAPI, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

# Import auth functions
from auth import (
    register_user, login_user, verify_email,
    get_user_profile, get_current_user,
    UserRegister, UserLogin, EmailVerification
)

# Create FastAPI app
app = FastAPI(
    title="DDM Learning Journey - Test API",
    description="Test server for authentication endpoints",
    version="0.1.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Health Check
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "DDM Learning Journey API",
        "version": "0.1.0",
        "timestamp": "2025-01-01T00:00:00Z"
    }

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
                <a href="http://localhost:8001/login.html" class="button">前往登入</a>
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
# Test Endpoints (for demonstration)
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "DDM Learning Journey API - Test Server",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "auth": {
                "register": "POST /auth/register",
                "login": "POST /auth/login",
                "verify": "POST /auth/verify-email",
                "profile": "GET /auth/me"
            }
        },
        "instructions": "Visit /docs for interactive API documentation"
    }

# ============================================================================
# Run Server
# ============================================================================

if __name__ == "__main__":
    print("="*60)
    print("  DDM Learning Journey - Test API Server")
    print("="*60)
    print("\n Starting server on http://localhost:8000")
    print(" Interactive docs: http://localhost:8000/docs")
    print(" Health check: http://localhost:8000/health")
    print("\n Press Ctrl+C to stop")
    print("="*60 + "\n")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )

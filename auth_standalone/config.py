"""
Configuration settings for 佛學普化小助手 authentication system
"""
import os
from typing import Optional
from pydantic import BaseSettings, validator
import secrets

class Settings(BaseSettings):
    # Database
    database_url: str = "sqlite+aiosqlite:///./buddhist_app.db"
    
    # JWT Settings
    secret_key: str = secrets.token_urlsafe(32)
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    
    # Email Settings
    resend_api_key: Optional[str] = None
    email_from: str = "佛學普化小助手 <noreply@yourdomain.com>"
    password_reset_token_expire_hours: int = 24
    
    # App URLs
    frontend_url: str = "http://localhost:3000"
    backend_url: str = "http://localhost:8000"
    
    # Environment
    debug: bool = True
    environment: str = "development"
    
    # Security
    password_min_length: int = 8
    max_login_attempts: int = 5
    account_lockout_minutes: int = 15
    
    @validator("secret_key", pre=True)
    def validate_secret_key(cls, v):
        if v == "your-secret-key-change-in-production-use-openssl-rand-hex-32":
            if os.getenv("ENVIRONMENT") == "production":
                raise ValueError("Must set a secure SECRET_KEY in production")
            # Generate a random key for development
            return secrets.token_urlsafe(32)
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Global settings instance
settings = Settings()

# Helper functions
def get_database_url() -> str:
    """Get database URL with proper async driver"""
    return settings.database_url

def is_production() -> bool:
    """Check if running in production"""
    return settings.environment.lower() == "production"

def get_password_reset_url(token: str) -> str:
    """Generate password reset URL"""
    return f"{settings.frontend_url}/reset-password?token={token}"
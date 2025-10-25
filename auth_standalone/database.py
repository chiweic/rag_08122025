"""
Database models and setup for 佛學普化小助手 authentication
"""
import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, relationship
from fastapi_users.db import SQLAlchemyBaseUserTableUUID, SQLAlchemyUserDatabase
from fastapi_users import schemas, models
from config import settings

# Database setup
Base = declarative_base()

class User(SQLAlchemyBaseUserTableUUID, Base):
    """User model with Buddhist-specific fields"""
    __tablename__ = "users"
    
    # Basic user info
    username: str = Column(String(50), unique=True, nullable=False, index=True)
    full_name: Optional[str] = Column(String(100), nullable=True)
    dharma_name: Optional[str] = Column(String(50), nullable=True)  # Buddhist name
    
    # Profile settings
    preferred_language: str = Column(String(10), default="zh-TW")
    timezone: str = Column(String(50), default="Asia/Taipei")
    profile_image_url: Optional[str] = Column(String(255), nullable=True)
    
    # Practice stats (denormalized for performance)
    total_practice_minutes: int = Column(Integer, default=0)
    total_sessions: int = Column(Integer, default=0)
    current_streak_days: int = Column(Integer, default=0)
    longest_streak_days: int = Column(Integer, default=0)
    
    # Timestamps
    last_practice_date: Optional[datetime] = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    practice_sessions = relationship("PracticeSession", back_populates="user", cascade="all, delete-orphan")
    bookmarks = relationship("UserBookmark", back_populates="user", cascade="all, delete-orphan")
    achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")

class PracticeSession(Base):
    """User practice sessions (meditation, reading, listening, etc.)"""
    __tablename__ = "practice_sessions"
    
    id: int = Column(Integer, primary_key=True, index=True)
    user_id: uuid.UUID = Column(ForeignKey("users.id"), nullable=False, index=True)
    
    # Practice details
    practice_type: str = Column(String(20), nullable=False)  # meditation, chanting, reading, listening
    duration_minutes: int = Column(Integer, nullable=False)
    
    # Content reference (optional)
    content_id: Optional[str] = Column(String(100), nullable=True)
    content_type: Optional[str] = Column(String(20), nullable=True)  # book, audio, text, video
    content_title: Optional[str] = Column(String(255), nullable=True)
    
    # Practice experience
    mood_before: Optional[str] = Column(String(20), nullable=True)  # peaceful, anxious, neutral, etc.
    mood_after: Optional[str] = Column(String(20), nullable=True)
    notes: Optional[str] = Column(Text, nullable=True)
    
    # Timestamps
    practice_date: datetime = Column(DateTime, nullable=False, index=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="practice_sessions")

class UserBookmark(Base):
    """User bookmarks and favorites"""
    __tablename__ = "user_bookmarks"
    
    id: int = Column(Integer, primary_key=True, index=True)
    user_id: uuid.UUID = Column(ForeignKey("users.id"), nullable=False, index=True)
    
    # Content reference
    content_type: str = Column(String(20), nullable=False)  # book, audio, text, event, query
    content_id: str = Column(String(100), nullable=False)
    content_title: str = Column(String(255), nullable=False)
    content_metadata: Optional[str] = Column(Text, nullable=True)  # JSON string
    
    # Bookmark details
    bookmark_type: str = Column(String(20), default="favorite")  # favorite, want_to_read, completed, studying
    notes: Optional[str] = Column(Text, nullable=True)
    tags: Optional[str] = Column(Text, nullable=True)  # Comma-separated
    
    # Timestamps
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="bookmarks")

class UserAchievement(Base):
    """User achievements and milestones"""
    __tablename__ = "user_achievements"
    
    id: int = Column(Integer, primary_key=True, index=True)
    user_id: uuid.UUID = Column(ForeignKey("users.id"), nullable=False, index=True)
    
    # Achievement details
    achievement_code: str = Column(String(50), nullable=False)  # FIRST_MEDITATION, WEEK_STREAK, etc.
    achievement_name: str = Column(String(100), nullable=False)
    achievement_description: str = Column(Text, nullable=False)
    achievement_icon: str = Column(String(50), nullable=False)  # Emoji or icon code
    
    # Progress tracking
    achievement_value: int = Column(Integer, default=0)  # Points or level
    progress_current: int = Column(Integer, default=0)
    progress_target: int = Column(Integer, nullable=False)
    
    # Status
    is_completed: bool = Column(Boolean, default=False)
    is_displayed: bool = Column(Boolean, default=True)
    
    # Timestamps
    earned_at: Optional[datetime] = Column(DateTime, nullable=True)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="achievements")

class PasswordResetToken(Base):
    """Password reset tokens"""
    __tablename__ = "password_reset_tokens"
    
    id: int = Column(Integer, primary_key=True, index=True)
    user_id: uuid.UUID = Column(ForeignKey("users.id"), nullable=False, index=True)
    token: str = Column(String(255), unique=True, nullable=False, index=True)
    expires_at: datetime = Column(DateTime, nullable=False, index=True)
    is_used: bool = Column(Boolean, default=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow)

# Pydantic schemas for FastAPI-Users
class UserRead(schemas.BaseUser[uuid.UUID]):
    """User read schema"""
    username: str
    full_name: Optional[str]
    dharma_name: Optional[str]
    preferred_language: str
    timezone: str
    profile_image_url: Optional[str]
    total_practice_minutes: int
    total_sessions: int
    current_streak_days: int
    created_at: datetime

class UserCreate(schemas.BaseUserCreate):
    """User creation schema"""
    username: str
    full_name: Optional[str] = None
    dharma_name: Optional[str] = None
    preferred_language: str = "zh-TW"
    timezone: str = "Asia/Taipei"

class UserUpdate(schemas.BaseUserUpdate):
    """User update schema"""
    username: Optional[str] = None
    full_name: Optional[str] = None
    dharma_name: Optional[str] = None
    preferred_language: Optional[str] = None
    timezone: Optional[str] = None
    profile_image_url: Optional[str] = None

# Database engine and session
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

async_session_maker = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def create_db_and_tables():
    """Create database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_async_session() -> AsyncSession:
    """Get async database session"""
    async with async_session_maker() as session:
        yield session

async def get_user_db(session: AsyncSession = None):
    """Get user database instance for FastAPI-Users"""
    if session is None:
        async with async_session_maker() as session:
            yield SQLAlchemyUserDatabase(session, User)
    else:
        yield SQLAlchemyUserDatabase(session, User)
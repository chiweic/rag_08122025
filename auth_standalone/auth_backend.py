"""
Authentication backend using FastAPI-Users with custom managers
"""
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)
from fastapi_users.password import PasswordHelper

from database import User, UserCreate, get_user_db, async_session_maker, PasswordResetToken
from email_service import email_service
from config import settings

logger = logging.getLogger(__name__)

class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    """Custom user manager with Buddhist app specific logic"""
    
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key
    
    def __init__(self, user_db, password_helper: Optional[PasswordHelper] = None):
        super().__init__(user_db, password_helper)
        self.reset_password_token_lifetime_seconds = settings.password_reset_token_expire_hours * 3600
    
    async def on_after_register(self, user: User, request: Optional[Request] = None):
        """Called after successful user registration"""
        logger.info(f"User {user.id} ({user.email}) has registered")
        
        # Send welcome email
        try:
            display_name = user.dharma_name or user.full_name or user.username
            await email_service.send_welcome_email(user.email, display_name)
        except Exception as e:
            logger.error(f"Failed to send welcome email to {user.email}: {e}")
        
        # Initialize user achievements
        await self._initialize_user_achievements(user)
    
    async def on_after_login(
        self, 
        user: User, 
        request: Optional[Request] = None,
        response: Optional[Any] = None,
    ):
        """Called after successful login"""
        logger.info(f"User {user.id} ({user.email}) logged in")
        
        # Update last login timestamp
        async with async_session_maker() as session:
            user.last_login = datetime.utcnow()
            session.add(user)
            await session.commit()
    
    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ):
        """Called after password reset request"""
        logger.info(f"Password reset requested for user {user.id} ({user.email})")
        
        # Store token in database for security tracking
        async with async_session_maker() as session:
            reset_token = PasswordResetToken(
                user_id=user.id,
                token=token,
                expires_at=datetime.utcnow() + timedelta(hours=settings.password_reset_token_expire_hours)
            )
            session.add(reset_token)
            await session.commit()
        
        # Send password reset email
        try:
            display_name = user.dharma_name or user.full_name or user.username
            await email_service.send_password_reset_email(user.email, token, display_name)
        except Exception as e:
            logger.error(f"Failed to send password reset email to {user.email}: {e}")
    
    async def on_after_reset_password(
        self, user: User, request: Optional[Request] = None
    ):
        """Called after successful password reset"""
        logger.info(f"Password reset completed for user {user.id} ({user.email})")
        
        # Mark all reset tokens for this user as used
        async with async_session_maker() as session:
            from sqlalchemy import update
            await session.execute(
                update(PasswordResetToken)
                .where(PasswordResetToken.user_id == user.id)
                .values(is_used=True)
            )
            await session.commit()
    
    async def create(
        self,
        user_create: UserCreate,
        safe: bool = False,
        request: Optional[Request] = None,
    ) -> User:
        """Create a new user with custom validation"""
        
        # Check if username is already taken
        existing_user = await self.user_db.get_by_email(user_create.email)
        if existing_user:
            raise ValueError("Email already registered")
        
        # Check username uniqueness (custom logic)
        if hasattr(user_create, 'username'):
            async with async_session_maker() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(User).where(User.username == user_create.username)
                )
                if result.scalar_one_or_none():
                    raise ValueError("Username already taken")
        
        # Validate dharma name uniqueness (optional)
        if hasattr(user_create, 'dharma_name') and user_create.dharma_name:
            async with async_session_maker() as session:
                from sqlalchemy import select
                result = await session.execute(
                    select(User).where(User.dharma_name == user_create.dharma_name)
                )
                if result.scalar_one_or_none():
                    logger.warning(f"Dharma name '{user_create.dharma_name}' already exists")
        
        # Create user
        user = await super().create(user_create, safe, request)
        return user
    
    async def _initialize_user_achievements(self, user: User):
        """Initialize basic achievements for new user"""
        from database import UserAchievement
        
        basic_achievements = [
            {
                "achievement_code": "REGISTRATION_COMPLETE",
                "achievement_name": "踏上修行路",
                "achievement_description": "完成註冊，開始佛學修行之旅",
                "achievement_icon": "🙏",
                "progress_target": 1,
                "progress_current": 1,
                "is_completed": True,
                "earned_at": datetime.utcnow()
            },
            {
                "achievement_code": "FIRST_MEDITATION",
                "achievement_name": "初心禪修",
                "achievement_description": "完成第一次禪修記錄",
                "achievement_icon": "🧘",
                "progress_target": 1,
                "progress_current": 0,
                "is_completed": False
            },
            {
                "achievement_code": "FIRST_READING",
                "achievement_name": "法乳初嚐",
                "achievement_description": "閱讀第一篇佛學文章",
                "achievement_icon": "📖",
                "progress_target": 1,
                "progress_current": 0,
                "is_completed": False
            },
            {
                "achievement_code": "WEEK_STREAK",
                "achievement_name": "一週精進",
                "achievement_description": "連續修行七天",
                "achievement_icon": "🔥",
                "progress_target": 7,
                "progress_current": 0,
                "is_completed": False
            }
        ]
        
        try:
            async with async_session_maker() as session:
                for achievement_data in basic_achievements:
                    achievement = UserAchievement(
                        user_id=user.id,
                        **achievement_data
                    )
                    session.add(achievement)
                await session.commit()
                logger.info(f"Initialized {len(basic_achievements)} achievements for user {user.id}")
        except Exception as e:
            logger.error(f"Failed to initialize achievements for user {user.id}: {e}")

    async def validate_password(self, password: str, user: UserCreate | User) -> None:
        """Custom password validation"""
        if len(password) < settings.password_min_length:
            raise ValueError(f"密碼長度至少需要 {settings.password_min_length} 個字符")
        
        # Check for at least one number
        if not any(char.isdigit() for char in password):
            raise ValueError("密碼必須包含至少一個數字")
        
        # Check for at least one letter
        if not any(char.isalpha() for char in password):
            raise ValueError("密碼必須包含至少一個字母")
        
        # Check for common weak passwords
        weak_passwords = ['12345678', 'password', 'qwerty123', '88888888']
        if password.lower() in weak_passwords:
            raise ValueError("密碼過於簡單，請選擇更安全的密碼")

# Dependency to get user manager
async def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

# JWT Strategy
def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=settings.access_token_expire_minutes * 60,
        algorithm=settings.algorithm,
    )

# Bearer transport (Authorization: Bearer <token>)
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

# Authentication backend
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# Export current user dependency
from fastapi_users import FastAPIUsers

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

current_active_user = fastapi_users.current_user(active=True)
current_user_optional = fastapi_users.current_user(optional=True)
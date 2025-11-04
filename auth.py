"""
Authentication module for DDM Learning Journey System
Handles user registration, login, email verification, and JWT tokens
"""

from fastapi import Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from pydantic import BaseModel, EmailStr
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from typing import Optional

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production-use-openssl-rand-hex-32")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "learning_journey"),
    "user": os.getenv("DB_USER", "ddm_user"),
    "password": os.getenv("DB_PASSWORD", "your_secure_password_here")
}

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "your-email@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "your-app-password")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS")
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@ddm-learning.org")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8001")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# ============================================================================
# Database Helper Functions
# ============================================================================

def get_db_connection():
    """Get PostgreSQL database connection"""
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

# ============================================================================
# Pydantic Models
# ============================================================================

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    ddm_student_id: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class EmailVerification(BaseModel):
    token: str

class User(BaseModel):
    id: str
    email: str
    full_name: str
    ddm_student_id: Optional[str]
    email_verified: bool

# ============================================================================
# Password & Token Functions
# ============================================================================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    """Create JWT access token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def generate_verification_token() -> str:
    """Generate a secure random token for email verification"""
    return secrets.token_urlsafe(32)

# ============================================================================
# Email Functions
# ============================================================================

def send_verification_email(email: str, token: str, full_name: str):
    """Send email verification link"""
    verification_link = f"{BASE_URL}/verify-email?token={token}"

    subject = "佛學入門 - 請驗證您的電子郵件"

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #0f766e;">歡迎加入佛學入門學習平台！</h2>
            <p>親愛的 {full_name}，</p>
            <p>感謝您註冊法鼓山數位學習平台。請點擊下方連結以驗證您的電子郵件地址：</p>
            <div style="text-align: center; margin: 30px 0;">
                <a href="{verification_link}"
                   style="background: linear-gradient(to right, #14b8a6, #0d9488);
                          color: white;
                          padding: 12px 30px;
                          text-decoration: none;
                          border-radius: 5px;
                          display: inline-block;">
                    驗證電子郵件
                </a>
            </div>
            <p style="color: #666; font-size: 14px;">
                如果按鈕無法點擊，請複製以下連結到瀏覽器：<br>
                <a href="{verification_link}">{verification_link}</a>
            </p>
            <p style="color: #666; font-size: 14px;">
                此驗證連結將在 24 小時後失效。
            </p>
            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
            <p style="color: #999; font-size: 12px;">
                © 2025 佛學入門 - AI數位義工 | 法鼓山數位學習平台
            </p>
        </div>
    </body>
    </html>
    """

    text_body = f"""
    歡迎加入佛學入門學習平台！

    親愛的 {full_name}，

    感謝您註冊法鼓山數位學習平台。請點擊以下連結以驗證您的電子郵件地址：

    {verification_link}

    此驗證連結將在 24 小時後失效。

    © 2025 佛學入門 - AI數位義工
    """

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = FROM_EMAIL
        msg['To'] = email

        part1 = MIMEText(text_body, 'plain', 'utf-8')
        part2 = MIMEText(html_body, 'html', 'utf-8')

        msg.attach(part1)
        msg.attach(part2)

        use_ssl = False
        use_tls = True

        if SMTP_USE_SSL is not None:
            use_ssl = SMTP_USE_SSL.lower() in {"1", "true", "yes"}
            use_tls = not use_ssl
        elif SMTP_USE_TLS is not None:
            use_tls = SMTP_USE_TLS.lower() in {"1", "true", "yes"}
            use_ssl = not use_tls
        elif SMTP_PORT == 465:
            use_ssl = True
            use_tls = False

        if use_ssl:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
        else:
            with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
                if use_tls:
                    server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)

        print(f"Verification email sent to {email}")
    except Exception as e:
        print(f"Failed to send email to {email}: {str(e)}")
        # Don't raise exception - registration should succeed even if email fails

# ============================================================================
# Auth Functions
# ============================================================================

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify JWT token and return current user"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        email: str = payload.get("email")

        if user_id is None or email is None:
            raise credentials_exception

        return {"user_id": user_id, "email": email}
    except JWTError:
        raise credentials_exception

async def get_current_verified_user(current_user: dict = Depends(get_current_user)) -> dict:
    """Get current user and ensure email is verified"""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("SELECT email_verified FROM users WHERE id = %s", (current_user["user_id"],))
    result = cur.fetchone()

    cur.close()
    conn.close()

    if not result or not result["email_verified"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email to access this feature."
        )

    return current_user

# ============================================================================
# API Endpoint Functions
# ============================================================================

async def register_user(user: UserRegister, background_tasks: BackgroundTasks):
    """Register a new user"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Check if user already exists
        cur.execute("SELECT id FROM users WHERE email = %s", (user.email,))
        if cur.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Check if DDM student ID already exists (if provided)
        if user.ddm_student_id:
            cur.execute("SELECT id FROM users WHERE ddm_student_id = %s", (user.ddm_student_id,))
            if cur.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="DDM Student ID already registered"
                )

        # Generate verification token
        verification_token = generate_verification_token()
        token_expires = datetime.utcnow() + timedelta(hours=24)

        # Insert new user
        hashed_pw = hash_password(user.password)
        cur.execute("""
            INSERT INTO users (email, hashed_password, full_name, ddm_student_id,
                              verification_token, verification_token_expires)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id, email, full_name, ddm_student_id, email_verified
        """, (user.email, hashed_pw, user.full_name, user.ddm_student_id,
              verification_token, token_expires))

        new_user = cur.fetchone()
        conn.commit()

        # Send verification email in background
        background_tasks.add_task(
            send_verification_email,
            user.email,
            verification_token,
            user.full_name
        )

        return {
            "message": "Registration successful. Please check your email to verify your account.",
            "user": {
                "id": str(new_user["id"]),
                "email": new_user["email"],
                "full_name": new_user["full_name"],
                "email_verified": new_user["email_verified"]
            }
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")
    finally:
        cur.close()
        conn.close()

async def login_user(user: UserLogin):
    """Login user and return JWT token"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Find user
        cur.execute("""
            SELECT id, email, hashed_password, full_name, ddm_student_id, email_verified
            FROM users
            WHERE email = %s
        """, (user.email,))

        db_user = cur.fetchone()

        if not db_user or not verify_password(user.password, db_user["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Create access token
        access_token = create_access_token({
            "user_id": str(db_user["id"]),
            "email": db_user["email"]
        })

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": str(db_user["id"]),
                "email": db_user["email"],
                "full_name": db_user["full_name"],
                "ddm_student_id": db_user["ddm_student_id"],
                "email_verified": db_user["email_verified"]
            }
        }

    finally:
        cur.close()
        conn.close()

async def verify_email(verification: EmailVerification):
    """Verify user email with token"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Find user with this token
        cur.execute("""
            SELECT id, email, full_name, verification_token_expires
            FROM users
            WHERE verification_token = %s AND email_verified = FALSE
        """, (verification.token,))

        user = cur.fetchone()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )

        # Check if token expired
        if user["verification_token_expires"] < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired. Please request a new one."
            )

        # Mark email as verified
        cur.execute("""
            UPDATE users
            SET email_verified = TRUE,
                verification_token = NULL,
                verification_token_expires = NULL
            WHERE id = %s
        """, (user["id"],))

        # Log verification
        cur.execute("""
            INSERT INTO email_verifications (user_id, verification_token, verified_at)
            VALUES (%s, %s, %s)
        """, (user["id"], verification.token, datetime.utcnow()))

        conn.commit()

        return {
            "message": "Email verified successfully! You can now access all features.",
            "user": {
                "email": user["email"],
                "full_name": user["full_name"]
            }
        }

    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")
    finally:
        cur.close()
        conn.close()

async def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Get current user profile"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT id, email, full_name, ddm_student_id, email_verified, created_at
            FROM users
            WHERE id = %s
        """, (current_user["user_id"],))

        user = cur.fetchone()

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "id": str(user["id"]),
            "email": user["email"],
            "full_name": user["full_name"],
            "ddm_student_id": user["ddm_student_id"],
            "email_verified": user["email_verified"],
            "member_since": user["created_at"].isoformat()
        }

    finally:
        cur.close()
        conn.close()

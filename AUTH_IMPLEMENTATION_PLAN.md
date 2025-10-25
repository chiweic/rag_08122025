# 佛學普化小助手 - Authentication & User Data Implementation Plan

## Executive Summary
This document outlines the complete implementation plan for adding user authentication, registration, and personal data management to the Buddhist Teaching Assistant (佛學普化小助手) application.

---

## 1. System Architecture Overview

### Technology Stack
- **Backend Framework**: FastAPI (Python)
- **Database**: SQLite (development) / PostgreSQL (production)
- **Authentication**: JWT (JSON Web Tokens)
- **Password Security**: Bcrypt hashing
- **Frontend**: JavaScript with session management
- **API Communication**: RESTful endpoints with Bearer token authentication

### High-Level Architecture
```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   Frontend UI   │────▶│   FastAPI       │────▶│   Database      │
│   (JavaScript)  │◀────│   Backend       │◀────│   (SQLite/PG)   │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
   [JWT Tokens]         [Auth Middleware]        [User Tables]
```

---

## 2. Database Schema Design

### 2.1 Core User Tables

#### Users Table
```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100),
    dharma_name VARCHAR(50),  -- Optional Buddhist name
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    profile_image_url VARCHAR(255),
    preferred_language VARCHAR(10) DEFAULT 'zh-TW',
    timezone VARCHAR(50) DEFAULT 'Asia/Taipei'
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
```

#### User Sessions Table
```sql
CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    refresh_token VARCHAR(255) UNIQUE,
    ip_address VARCHAR(45),
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_sessions_user ON user_sessions(user_id);
```

### 2.2 Practice & Learning Tables

#### Practice Sessions
```sql
CREATE TABLE user_practice_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    practice_type VARCHAR(20) NOT NULL, -- 'meditation', 'chanting', 'reading', 'listening'
    duration_minutes INTEGER NOT NULL,
    content_id VARCHAR(100),
    content_type VARCHAR(20), -- 'book', 'audio', 'text', 'video'
    content_title VARCHAR(255),
    notes TEXT,
    mood_before VARCHAR(20), -- 'peaceful', 'anxious', 'neutral', etc.
    mood_after VARCHAR(20),
    practice_date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_practice_user_date ON user_practice_sessions(user_id, practice_date);
```

#### Query History (Enhanced)
```sql
CREATE TABLE user_queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    query_text TEXT NOT NULL,
    response_text TEXT,
    response_sources JSON, -- Store source references as JSON
    session_id VARCHAR(50),
    query_category VARCHAR(50), -- Auto-detected category
    satisfaction_rating INTEGER CHECK (satisfaction_rating >= 1 AND satisfaction_rating <= 5),
    is_bookmarked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_queries_user ON user_queries(user_id);
CREATE INDEX idx_queries_session ON user_queries(session_id);
```

### 2.3 Content Management Tables

#### Bookmarks & Favorites
```sql
CREATE TABLE user_bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    content_type VARCHAR(20) NOT NULL, -- 'book', 'audio', 'text', 'event', 'query'
    content_id VARCHAR(100) NOT NULL,
    content_title VARCHAR(255),
    content_metadata JSON, -- Store additional metadata
    bookmark_type VARCHAR(20) DEFAULT 'favorite', -- 'favorite', 'want_to_read', 'completed', 'studying'
    notes TEXT,
    tags TEXT, -- Comma-separated tags
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bookmarks_user_type ON user_bookmarks(user_id, content_type);
CREATE UNIQUE INDEX idx_bookmarks_unique ON user_bookmarks(user_id, content_type, content_id);
```

#### Learning Progress
```sql
CREATE TABLE user_learning_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    topic VARCHAR(100) NOT NULL, -- '四聖諦', '八正道', '禪修基礎', etc.
    subtopic VARCHAR(100),
    proficiency_level INTEGER DEFAULT 1 CHECK (proficiency_level >= 1 AND proficiency_level <= 5),
    total_study_minutes INTEGER DEFAULT 0,
    last_studied TIMESTAMP,
    study_count INTEGER DEFAULT 0,
    quiz_scores JSON, -- Array of quiz scores
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_learning_user_topic ON user_learning_progress(user_id, topic);
```

### 2.4 Gamification Tables

#### Achievements
```sql
CREATE TABLE user_achievements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    achievement_code VARCHAR(50) NOT NULL, -- 'FIRST_MEDITATION', 'WEEK_STREAK', etc.
    achievement_name VARCHAR(100),
    achievement_description TEXT,
    achievement_icon VARCHAR(50), -- Emoji or icon code
    achievement_value INTEGER, -- Points or level
    progress_current INTEGER DEFAULT 0,
    progress_target INTEGER,
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_displayed BOOLEAN DEFAULT TRUE
);

CREATE UNIQUE INDEX idx_achievements_unique ON user_achievements(user_id, achievement_code);
```

#### Daily Practice Goals
```sql
CREATE TABLE user_practice_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    goal_type VARCHAR(50) NOT NULL, -- 'daily_meditation', 'weekly_reading', etc.
    target_value INTEGER NOT NULL, -- Target minutes/pages/sessions
    current_value INTEGER DEFAULT 0,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_goals_user_period ON user_practice_goals(user_id, period_start, period_end);
```

---

## 3. Backend Implementation

### 3.1 Authentication Module

#### File: `auth.py`
```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr, Field
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
import sqlite3
import secrets

# Configuration
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Security setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Pydantic models
class UserRegister(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    dharma_name: Optional[str] = None

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class UserProfile(BaseModel):
    full_name: Optional[str]
    dharma_name: Optional[str]
    preferred_language: Optional[str]
    timezone: Optional[str]

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

# Router setup
auth_router = APIRouter(prefix="/auth", tags=["authentication"])

# Core authentication endpoints
@auth_router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegister):
    """Register a new user account"""
    # Implementation details...
    pass

@auth_router.post("/login", response_model=TokenResponse)
async def login(credentials: UserLogin):
    """Login with username/email and password"""
    # Implementation details...
    pass

@auth_router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token using refresh token"""
    # Implementation details...
    pass

@auth_router.post("/logout")
async def logout(token: HTTPAuthorizationCredentials = Depends(security)):
    """Logout and invalidate tokens"""
    # Implementation details...
    pass

@auth_router.get("/me")
async def get_current_user(token: HTTPAuthorizationCredentials = Depends(security)):
    """Get current user information"""
    # Implementation details...
    pass

@auth_router.put("/profile")
async def update_profile(
    profile: UserProfile,
    token: HTTPAuthorizationCredentials = Depends(security)
):
    """Update user profile"""
    # Implementation details...
    pass

@auth_router.post("/reset-password-request")
async def request_password_reset(email: EmailStr):
    """Request password reset email"""
    # Implementation details...
    pass

@auth_router.post("/reset-password")
async def reset_password(token: str, new_password: str):
    """Reset password with token"""
    # Implementation details...
    pass
```

### 3.2 User Data Management

#### File: `user_data.py`
```python
from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel

user_router = APIRouter(prefix="/user", tags=["user_data"])

class PracticeSession(BaseModel):
    practice_type: str
    duration_minutes: int
    content_id: Optional[str]
    content_type: Optional[str]
    notes: Optional[str]
    mood_before: Optional[str]
    mood_after: Optional[str]
    practice_date: date

class Bookmark(BaseModel):
    content_type: str
    content_id: str
    content_title: str
    bookmark_type: str = "favorite"
    notes: Optional[str]
    tags: Optional[List[str]]

@user_router.post("/practice-session")
async def log_practice_session(
    session: PracticeSession,
    current_user = Depends(get_current_user)
):
    """Log a meditation/study practice session"""
    pass

@user_router.get("/practice-history")
async def get_practice_history(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    practice_type: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """Get user's practice history with filters"""
    pass

@user_router.post("/bookmark")
async def add_bookmark(
    bookmark: Bookmark,
    current_user = Depends(get_current_user)
):
    """Add a bookmark/favorite"""
    pass

@user_router.get("/bookmarks")
async def get_bookmarks(
    content_type: Optional[str] = None,
    bookmark_type: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """Get user's bookmarks with filters"""
    pass

@user_router.delete("/bookmark/{bookmark_id}")
async def remove_bookmark(
    bookmark_id: int,
    current_user = Depends(get_current_user)
):
    """Remove a bookmark"""
    pass

@user_router.get("/learning-progress")
async def get_learning_progress(
    current_user = Depends(get_current_user)
):
    """Get user's learning progress across topics"""
    pass

@user_router.post("/learning-progress")
async def update_learning_progress(
    topic: str,
    subtopic: Optional[str],
    study_minutes: int,
    quiz_score: Optional[int],
    current_user = Depends(get_current_user)
):
    """Update learning progress for a topic"""
    pass

@user_router.get("/achievements")
async def get_achievements(
    current_user = Depends(get_current_user)
):
    """Get user's earned achievements"""
    pass

@user_router.get("/dashboard")
async def get_dashboard_data(
    current_user = Depends(get_current_user)
):
    """Get comprehensive dashboard data"""
    # Returns:
    # - Recent practice sessions
    # - Progress statistics
    # - Upcoming goals
    # - Recent achievements
    # - Recommended content
    pass

@user_router.get("/statistics")
async def get_user_statistics(
    period: str = Query("month", enum=["week", "month", "year", "all"]),
    current_user = Depends(get_current_user)
):
    """Get detailed practice statistics"""
    pass
```

### 3.3 Integration with Main API

#### Updates to `api.py`
```python
# Add to existing api.py
from auth import auth_router
from user_data import user_router

# Include routers
app.include_router(auth_router)
app.include_router(user_router)

# Middleware for authentication
@app.middleware("http")
async def authenticate_request(request: Request, call_next):
    # Optional: Add authentication checks for protected endpoints
    response = await call_next(request)
    return response

# Enhanced query endpoint with user tracking
@app.post("/query")
async def query_with_user(
    request: QueryRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    # Existing query logic...
    
    # If user is authenticated, save query to history
    if current_user:
        save_user_query(
            user_id=current_user["id"],
            query_text=request.question,
            response_text=response.answer,
            sources=response.sources
        )
    
    return response
```

---

## 4. Frontend Implementation

### 4.1 Authentication UI Components

#### File: `auth.js`
```javascript
class AuthManager {
    constructor() {
        this.token = localStorage.getItem('access_token');
        this.refreshToken = localStorage.getItem('refresh_token');
        this.currentUser = null;
    }

    // Show login modal
    showLoginModal() {
        const modal = document.createElement('div');
        modal.className = 'auth-modal';
        modal.innerHTML = `
            <div class="auth-modal-content">
                <h2>登入 佛學普化小助手</h2>
                <form id="login-form">
                    <input type="text" id="username-email" placeholder="用戶名或電子郵件" required>
                    <input type="password" id="password" placeholder="密碼" required>
                    <button type="submit">登入</button>
                    <p>還沒有帳號？<a href="#" onclick="authManager.showRegisterModal()">立即註冊</a></p>
                </form>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Show register modal
    showRegisterModal() {
        const modal = document.createElement('div');
        modal.className = 'auth-modal';
        modal.innerHTML = `
            <div class="auth-modal-content">
                <h2>註冊新帳號</h2>
                <form id="register-form">
                    <input type="text" id="username" placeholder="用戶名" required>
                    <input type="email" id="email" placeholder="電子郵件" required>
                    <input type="password" id="password" placeholder="密碼 (至少8個字符)" required>
                    <input type="password" id="confirm-password" placeholder="確認密碼" required>
                    <input type="text" id="full-name" placeholder="姓名 (選填)">
                    <input type="text" id="dharma-name" placeholder="法名 (選填)">
                    <button type="submit">註冊</button>
                    <p>已有帳號？<a href="#" onclick="authManager.showLoginModal()">立即登入</a></p>
                </form>
            </div>
        `;
        document.body.appendChild(modal);
    }

    // Handle login
    async handleLogin(usernameOrEmail, password) {
        try {
            const response = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    username_or_email: usernameOrEmail,
                    password: password
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.saveTokens(data.access_token, data.refresh_token);
                await this.loadUserInfo();
                this.updateUIForAuthenticatedUser();
                this.closeAuthModal();
            } else {
                throw new Error('登入失敗');
            }
        } catch (error) {
            alert('登入失敗: ' + error.message);
        }
    }

    // Handle registration
    async handleRegister(userData) {
        try {
            const response = await fetch('/auth/register', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(userData)
            });

            if (response.ok) {
                const data = await response.json();
                this.saveTokens(data.access_token, data.refresh_token);
                await this.loadUserInfo();
                this.updateUIForAuthenticatedUser();
                this.closeAuthModal();
            } else {
                throw new Error('註冊失敗');
            }
        } catch (error) {
            alert('註冊失敗: ' + error.message);
        }
    }

    // Save tokens
    saveTokens(accessToken, refreshToken) {
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
        this.token = accessToken;
        this.refreshToken = refreshToken;
    }

    // Load user information
    async loadUserInfo() {
        if (!this.token) return;

        try {
            const response = await fetch('/auth/me', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });

            if (response.ok) {
                this.currentUser = await response.json();
            } else if (response.status === 401) {
                // Token expired, try refresh
                await this.refreshAccessToken();
            }
        } catch (error) {
            console.error('Failed to load user info:', error);
        }
    }

    // Refresh access token
    async refreshAccessToken() {
        if (!this.refreshToken) return false;

        try {
            const response = await fetch('/auth/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ refresh_token: this.refreshToken })
            });

            if (response.ok) {
                const data = await response.json();
                this.saveTokens(data.access_token, data.refresh_token);
                return true;
            }
        } catch (error) {
            console.error('Failed to refresh token:', error);
        }

        // Refresh failed, clear session
        this.logout();
        return false;
    }

    // Logout
    async logout() {
        try {
            await fetch('/auth/logout', {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
        } catch (error) {
            console.error('Logout error:', error);
        }

        // Clear local storage
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        this.token = null;
        this.refreshToken = null;
        this.currentUser = null;

        // Update UI
        this.updateUIForGuestUser();
    }

    // Update UI for authenticated user
    updateUIForAuthenticatedUser() {
        const authButton = document.querySelector('.auth-button');
        if (authButton && this.currentUser) {
            const displayName = this.currentUser.dharma_name || this.currentUser.username;
            authButton.innerHTML = `
                <span class="user-name">${displayName}</span>
                <button onclick="authManager.showUserMenu()">▼</button>
            `;
        }

        // Show user-specific features
        document.querySelectorAll('.auth-required').forEach(el => {
            el.style.display = 'block';
        });
    }

    // Update UI for guest user
    updateUIForGuestUser() {
        const authButton = document.querySelector('.auth-button');
        if (authButton) {
            authButton.innerHTML = '登入 / 註冊';
            authButton.onclick = () => this.showLoginModal();
        }

        // Hide user-specific features
        document.querySelectorAll('.auth-required').forEach(el => {
            el.style.display = 'none';
        });
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.token && !!this.currentUser;
    }

    // Get authorization headers
    getAuthHeaders() {
        return this.token ? { 'Authorization': `Bearer ${this.token}` } : {};
    }
}

// Initialize auth manager
const authManager = new AuthManager();
```

### 4.2 Practice Tracking Integration

#### File: `practice_tracker.js`
```javascript
class PracticeTracker {
    constructor(authManager) {
        this.authManager = authManager;
        this.currentSession = null;
    }

    // Start practice session
    startPracticeSession(type, contentId = null, contentType = null) {
        if (!this.authManager.isAuthenticated()) return;

        this.currentSession = {
            practice_type: type,
            content_id: contentId,
            content_type: contentType,
            start_time: new Date(),
            mood_before: null
        };

        // Optional: Show mood selection dialog
        this.showMoodDialog('before');
    }

    // End practice session
    async endPracticeSession(notes = '') {
        if (!this.currentSession || !this.authManager.isAuthenticated()) return;

        const duration = Math.round((new Date() - this.currentSession.start_time) / 60000);
        
        // Show mood selection dialog for after practice
        const moodAfter = await this.showMoodDialog('after');

        const sessionData = {
            practice_type: this.currentSession.practice_type,
            duration_minutes: duration,
            content_id: this.currentSession.content_id,
            content_type: this.currentSession.content_type,
            notes: notes,
            mood_before: this.currentSession.mood_before,
            mood_after: moodAfter,
            practice_date: new Date().toISOString().split('T')[0]
        };

        try {
            const response = await fetch('/user/practice-session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...this.authManager.getAuthHeaders()
                },
                body: JSON.stringify(sessionData)
            });

            if (response.ok) {
                this.showPracticeComplete(duration);
                this.checkAchievements();
            }
        } catch (error) {
            console.error('Failed to log practice session:', error);
        }

        this.currentSession = null;
    }

    // Show mood selection dialog
    showMoodDialog(timing) {
        return new Promise((resolve) => {
            const modal = document.createElement('div');
            modal.className = 'mood-modal';
            modal.innerHTML = `
                <div class="mood-content">
                    <h3>${timing === 'before' ? '修行前' : '修行後'}的心情如何？</h3>
                    <div class="mood-options">
                        <button onclick="resolveMood('peaceful')">🙏 平靜</button>
                        <button onclick="resolveMood('joyful')">😊 喜悅</button>
                        <button onclick="resolveMood('neutral')">😐 中性</button>
                        <button onclick="resolveMood('anxious')">😟 焦慮</button>
                        <button onclick="resolveMood('tired')">😴 疲倦</button>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);

            window.resolveMood = (mood) => {
                modal.remove();
                resolve(mood);
            };
        });
    }

    // Show practice complete notification
    showPracticeComplete(duration) {
        const notification = document.createElement('div');
        notification.className = 'practice-notification';
        notification.innerHTML = `
            <div class="notification-content">
                ✨ 修行完成！
                <br>持續時間: ${duration} 分鐘
                <br>功德無量 🙏
            </div>
        `;
        document.body.appendChild(notification);

        setTimeout(() => notification.remove(), 5000);
    }

    // Check for new achievements
    async checkAchievements() {
        try {
            const response = await fetch('/user/achievements', {
                headers: this.authManager.getAuthHeaders()
            });

            if (response.ok) {
                const achievements = await response.json();
                // Show new achievements if any
                this.displayNewAchievements(achievements.new);
            }
        } catch (error) {
            console.error('Failed to check achievements:', error);
        }
    }

    // Auto-track reading sessions
    trackReadingSession(bookId, bookTitle) {
        this.startPracticeSession('reading', bookId, 'book');
        
        // Auto-end session when user navigates away
        window.addEventListener('beforeunload', () => {
            this.endPracticeSession(`閱讀: ${bookTitle}`);
        });
    }

    // Auto-track audio listening
    trackAudioListening(audioId, audioTitle) {
        this.startPracticeSession('listening', audioId, 'audio');
        
        // End session when audio ends or modal closes
        const audioElement = document.querySelector(`#audio-player-${audioId}`);
        if (audioElement) {
            audioElement.addEventListener('ended', () => {
                this.endPracticeSession(`聆聽: ${audioTitle}`);
            });
        }
    }
}

// Initialize practice tracker
const practiceTracker = new PracticeTracker(authManager);
```

### 4.3 User Dashboard

#### File: `dashboard.js`
```javascript
class UserDashboard {
    constructor(authManager) {
        this.authManager = authManager;
    }

    // Show user dashboard
    async showDashboard() {
        if (!this.authManager.isAuthenticated()) {
            this.authManager.showLoginModal();
            return;
        }

        const dashboardData = await this.fetchDashboardData();
        
        const modal = document.createElement('div');
        modal.className = 'dashboard-modal';
        modal.innerHTML = `
            <div class="dashboard-content">
                <div class="dashboard-header">
                    <h2>修行記錄儀表板</h2>
                    <button onclick="closeDashboard()">✕</button>
                </div>
                
                <div class="dashboard-stats">
                    <div class="stat-card">
                        <div class="stat-value">${dashboardData.total_practice_days}</div>
                        <div class="stat-label">修行天數</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${dashboardData.total_practice_hours}</div>
                        <div class="stat-label">總修行時數</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${dashboardData.current_streak}</div>
                        <div class="stat-label">連續天數</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${dashboardData.books_read}</div>
                        <div class="stat-label">已讀書籍</div>
                    </div>
                </div>
                
                <div class="dashboard-sections">
                    <div class="section recent-practice">
                        <h3>最近修行</h3>
                        ${this.renderRecentPractice(dashboardData.recent_sessions)}
                    </div>
                    
                    <div class="section achievements">
                        <h3>成就徽章</h3>
                        ${this.renderAchievements(dashboardData.achievements)}
                    </div>
                    
                    <div class="section learning-progress">
                        <h3>學習進度</h3>
                        ${this.renderLearningProgress(dashboardData.learning_topics)}
                    </div>
                    
                    <div class="section practice-goals">
                        <h3>修行目標</h3>
                        ${this.renderPracticeGoals(dashboardData.goals)}
                    </div>
                </div>
                
                <div class="dashboard-chart">
                    <canvas id="practice-chart"></canvas>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // Render practice chart
        this.renderPracticeChart(dashboardData.chart_data);
    }

    // Fetch dashboard data
    async fetchDashboardData() {
        try {
            const response = await fetch('/user/dashboard', {
                headers: this.authManager.getAuthHeaders()
            });

            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Failed to fetch dashboard data:', error);
        }
        return {};
    }

    // Render recent practice sessions
    renderRecentPractice(sessions) {
        if (!sessions || sessions.length === 0) {
            return '<p>尚無修行記錄</p>';
        }

        return sessions.map(session => `
            <div class="practice-item">
                <span class="practice-type">${this.getPracticeIcon(session.practice_type)}</span>
                <span class="practice-duration">${session.duration_minutes}分鐘</span>
                <span class="practice-date">${this.formatDate(session.practice_date)}</span>
            </div>
        `).join('');
    }

    // Render achievements
    renderAchievements(achievements) {
        if (!achievements || achievements.length === 0) {
            return '<p>繼續修行以獲得成就徽章！</p>';
        }

        return achievements.map(achievement => `
            <div class="achievement-badge" title="${achievement.description}">
                <span class="badge-icon">${achievement.icon}</span>
                <span class="badge-name">${achievement.name}</span>
            </div>
        `).join('');
    }

    // Render learning progress
    renderLearningProgress(topics) {
        if (!topics || topics.length === 0) {
            return '<p>開始學習以追蹤進度</p>';
        }

        return topics.map(topic => `
            <div class="progress-item">
                <div class="progress-header">
                    <span class="topic-name">${topic.name}</span>
                    <span class="topic-level">Lv.${topic.proficiency_level}</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: ${topic.progress_percent}%"></div>
                </div>
            </div>
        `).join('');
    }

    // Helper functions
    getPracticeIcon(type) {
        const icons = {
            'meditation': '🧘',
            'chanting': '📿',
            'reading': '📖',
            'listening': '🎧'
        };
        return icons[type] || '🙏';
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('zh-TW');
    }
}

// Initialize dashboard
const userDashboard = new UserDashboard(authManager);
```

---

## 5. Security Considerations

### 5.1 Password Security
- **Minimum Requirements**: 8+ characters, at least one uppercase, one lowercase, one number
- **Hashing**: Bcrypt with cost factor 12
- **Password History**: Prevent reuse of last 5 passwords
- **Account Lockout**: Lock after 5 failed attempts for 15 minutes

### 5.2 Token Security
- **Access Token**: 30-minute expiry, JWT with RS256
- **Refresh Token**: 7-day expiry, stored securely
- **Token Rotation**: New refresh token on each use
- **Blacklisting**: Maintain blacklist for logout/revocation

### 5.3 API Security
- **Rate Limiting**: 
  - Registration: 5 requests per hour per IP
  - Login: 10 requests per hour per IP
  - API calls: 100 requests per minute per user
- **CORS**: Strict origin validation
- **HTTPS**: Enforce in production
- **Input Validation**: Sanitize all inputs
- **SQL Injection**: Use parameterized queries

### 5.4 Data Protection
- **PII Encryption**: Encrypt sensitive user data at rest
- **Audit Logging**: Log all authentication events
- **Data Retention**: Clear old session data regularly
- **GDPR Compliance**: Provide data export/deletion options

---

## 6. Deployment Considerations

### 6.1 Development Environment
```bash
# SQLite database
DATABASE_URL=sqlite:///./buddhist_app.db

# JWT Configuration
SECRET_KEY=development-secret-key-change-in-production
ALGORITHM=HS256

# Session Configuration
SESSION_EXPIRE_MINUTES=30
REFRESH_EXPIRE_DAYS=7
```

### 6.2 Production Environment
```bash
# PostgreSQL database
DATABASE_URL=postgresql://user:pass@localhost/buddhist_app

# JWT Configuration (use environment variables)
SECRET_KEY=${JWT_SECRET_KEY}
ALGORITHM=RS256

# Redis for sessions
REDIS_URL=redis://localhost:6379

# Email service for password reset
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=${EMAIL_USERNAME}
SMTP_PASSWORD=${EMAIL_PASSWORD}
```

### 6.3 Database Migration
```python
# migrations/001_create_user_tables.py
import sqlite3

def upgrade():
    conn = sqlite3.connect('buddhist_app.db')
    cursor = conn.cursor()
    
    # Create all tables
    with open('schema.sql', 'r') as f:
        cursor.executescript(f.read())
    
    conn.commit()
    conn.close()

def downgrade():
    # Drop all tables
    pass
```

---

## 7. Testing Strategy

### 7.1 Unit Tests
```python
# test_auth.py
import pytest
from fastapi.testclient import TestClient

def test_user_registration():
    # Test successful registration
    # Test duplicate username
    # Test invalid email
    # Test weak password
    pass

def test_user_login():
    # Test successful login
    # Test invalid credentials
    # Test account lockout
    pass

def test_token_refresh():
    # Test successful refresh
    # Test expired refresh token
    # Test invalid refresh token
    pass
```

### 7.2 Integration Tests
```python
# test_user_flow.py
def test_complete_user_journey():
    # Register new user
    # Login
    # Update profile
    # Log practice session
    # Add bookmark
    # Check achievements
    # View dashboard
    # Logout
    pass
```

---

## 8. Monitoring & Analytics

### 8.1 User Metrics
- Daily/Monthly Active Users
- Registration conversion rate
- Session duration
- Practice engagement metrics
- Feature adoption rates

### 8.2 System Metrics
- API response times
- Authentication success/failure rates
- Database query performance
- Token refresh patterns
- Error rates by endpoint

### 8.3 Practice Analytics
- Most popular practice types
- Average session duration by type
- User retention by practice frequency
- Content engagement metrics
- Achievement completion rates

---

## 9. Future Enhancements

### Phase 2 Features
- **Social Features**: Share practice milestones
- **Teacher Connections**: Link students with teachers
- **Group Practice**: Virtual group meditation sessions
- **Progress Sharing**: Share learning progress with community

### Phase 3 Features
- **AI Recommendations**: Personalized content based on practice patterns
- **Practice Reminders**: Smart notifications based on user habits
- **Offline Support**: PWA with offline capability
- **Mobile Apps**: Native iOS/Android applications

### Phase 4 Features
- **Multi-language Support**: English, Traditional/Simplified Chinese
- **Advanced Analytics**: ML-powered insights
- **Virtual Retreats**: Online retreat participation tracking
- **Certification System**: Course completion certificates

---

## 10. Implementation Timeline

### Week 1-2: Core Authentication
- Database setup
- Basic auth endpoints
- JWT implementation
- Frontend login/register

### Week 3-4: User Data Management
- Practice tracking
- Bookmarks system
- Query history enhancement
- Basic dashboard

### Week 5-6: Advanced Features
- Achievements system
- Learning progress
- Practice goals
- Analytics dashboard

### Week 7-8: Testing & Deployment
- Comprehensive testing
- Security audit
- Performance optimization
- Production deployment

---

## Conclusion

This implementation plan provides a comprehensive approach to adding user authentication and personal data management to the Buddhist Teaching Assistant application. The system is designed to be:

- **Secure**: Following industry best practices for authentication and data protection
- **Scalable**: Architecture supports growth from hundreds to millions of users
- **User-friendly**: Intuitive interface with meaningful features for Buddhist practitioners
- **Maintainable**: Clean code structure with clear separation of concerns

The phased approach allows for iterative development and testing, ensuring each component is robust before moving to the next phase.
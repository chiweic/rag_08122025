"""
Database helper functions for Learning Journey System
Handles database connections and common operations for quiz history, learning sessions, etc.
"""

import psycopg2
from psycopg2.extras import RealDictCursor, Json
from typing import Optional, Dict, List, Any
import os
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
    "database": os.getenv("DB_NAME", "learning_journey"),
    "user": os.getenv("DB_USER", "ddm_user"),
    "password": os.getenv("DB_PASSWORD", "your_secure_password_here")
}


def get_db_connection():
    """Get database connection with RealDictCursor"""
    try:
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise


def save_quiz_attempt(
    quiz_id: str,
    user_id: Optional[str],
    user_email: str,
    source_query: str,
    reference_chunk_title: str,
    reference_chunk_id: str,
    questions: List[Dict],
    answers: List[Dict],
    evaluations: List[Dict],
    total_score: int,
    max_score: int,
    percentage: float,
    overall_grade: str,
    overall_feedback: str,
    zen_master_response: Optional[str],
    time_spent_seconds: int = 0,
    computation_time: float = 0.0
) -> int:
    """
    Save quiz attempt to database
    Returns the ID of the created quiz attempt
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Convert lists to JSON
        questions_json = Json(questions)
        answers_json = Json(answers)
        evaluations_json = Json(evaluations)

        query = """
        INSERT INTO quiz_attempts (
            quiz_id, user_id, user_email, source_query,
            reference_chunk_title, reference_chunk_id,
            questions, answers, evaluations,
            total_score, max_score, percentage, overall_grade,
            overall_feedback, zen_master_response,
            time_spent_seconds, computation_time
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        RETURNING id
        """

        cur.execute(query, (
            quiz_id, user_id, user_email, source_query,
            reference_chunk_title, reference_chunk_id,
            questions_json, answers_json, evaluations_json,
            total_score, max_score, percentage, overall_grade,
            overall_feedback, zen_master_response,
            time_spent_seconds, computation_time
        ))

        result = cur.fetchone()
        attempt_id = result['id']

        conn.commit()
        logger.info(f"Saved quiz attempt {quiz_id} for user {user_email} (ID: {attempt_id})")

        return attempt_id

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error saving quiz attempt: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_quiz_history(user_email: str, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
    """Get quiz history for a user"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get total count
        count_query = "SELECT COUNT(*) as total FROM quiz_attempts WHERE user_email = %s"
        cur.execute(count_query, (user_email,))
        total = cur.fetchone()['total']

        # Get quiz attempts
        query = """
        SELECT
            id, quiz_id, source_query, reference_chunk_title,
            total_score, max_score, percentage, overall_grade,
            created_at,
            jsonb_array_length(questions) as question_count
        FROM quiz_attempts
        WHERE user_email = %s
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
        """

        cur.execute(query, (user_email, limit, offset))
        quizzes = cur.fetchall()

        return {
            "total": total,
            "quizzes": [dict(q) for q in quizzes]
        }

    except Exception as e:
        logger.error(f"Error getting quiz history: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_quiz_attempt_detail(attempt_id: int, user_email: str) -> Optional[Dict]:
    """Get detailed quiz attempt by ID"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
        SELECT
            id, quiz_id, source_query,
            reference_chunk_title, reference_chunk_id,
            questions, answers, evaluations,
            total_score, max_score, percentage,
            overall_grade, overall_feedback, zen_master_response,
            time_spent_seconds, created_at
        FROM quiz_attempts
        WHERE id = %s AND user_email = %s
        """

        cur.execute(query, (attempt_id, user_email))
        result = cur.fetchone()

        return dict(result) if result else None

    except Exception as e:
        logger.error(f"Error getting quiz attempt detail: {e}")
        raise
    finally:
        if conn:
            conn.close()


def get_quiz_statistics(user_email: str) -> Dict[str, Any]:
    """Get quiz statistics for a user"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Overall statistics
        overall_query = """
        SELECT
            COUNT(*) as total_attempts,
            COALESCE(AVG(percentage), 0) as average_score,
            COALESCE(MAX(percentage), 0) as best_score,
            COALESCE(
                (SELECT AVG(percentage)
                 FROM (SELECT percentage FROM quiz_attempts
                       WHERE user_email = %s
                       ORDER BY created_at DESC LIMIT 10) recent),
                0
            ) as recent_average
        FROM quiz_attempts
        WHERE user_email = %s
        """

        cur.execute(overall_query, (user_email, user_email))
        overall_stats = dict(cur.fetchone())

        # Grade distribution
        grade_query = """
        SELECT overall_grade, COUNT(*) as count
        FROM quiz_attempts
        WHERE user_email = %s
        GROUP BY overall_grade
        """

        cur.execute(grade_query, (user_email,))
        grade_dist = {row['overall_grade']: row['count'] for row in cur.fetchall()}

        # Topics covered (by reference chunk title)
        topics_query = """
        SELECT
            reference_chunk_title as topic,
            COUNT(*) as count,
            AVG(percentage) as avg_score
        FROM quiz_attempts
        WHERE user_email = %s AND reference_chunk_title IS NOT NULL
        GROUP BY reference_chunk_title
        ORDER BY count DESC
        LIMIT 10
        """

        cur.execute(topics_query, (user_email,))
        topics = [dict(row) for row in cur.fetchall()]

        # Monthly improvement trend (last 6 months)
        trend_query = """
        SELECT
            TO_CHAR(created_at, 'YYYY-MM') as month,
            AVG(percentage) as avg_score,
            COUNT(*) as quiz_count
        FROM quiz_attempts
        WHERE user_email = %s
          AND created_at >= NOW() - INTERVAL '6 months'
        GROUP BY TO_CHAR(created_at, 'YYYY-MM')
        ORDER BY month
        """

        cur.execute(trend_query, (user_email,))
        trend = [dict(row) for row in cur.fetchall()]

        return {
            "total_attempts": overall_stats['total_attempts'],
            "average_score": float(overall_stats['average_score']),
            "best_score": float(overall_stats['best_score']),
            "recent_average": float(overall_stats['recent_average']),
            "grade_distribution": grade_dist,
            "topics_covered": topics,
            "improvement_trend": trend
        }

    except Exception as e:
        logger.error(f"Error getting quiz statistics: {e}")
        raise
    finally:
        if conn:
            conn.close()


def update_user_achievement(user_email: str, achievement_type: str, current_value: int) -> bool:
    """Update user achievement progress"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Call the stored procedure
        cur.execute(
            "SELECT update_achievement_progress(%s, %s, %s)",
            (user_email, achievement_type, current_value)
        )

        conn.commit()
        logger.info(f"Updated achievement {achievement_type} for {user_email}: {current_value}")

        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error updating achievement: {e}")
        return False
    finally:
        if conn:
            conn.close()


def check_and_create_master_comment(user_email: str, user_id: Optional[str] = None) -> Optional[Dict]:
    """Check for master comment triggers and create if needed"""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check for triggers
        cur.execute("SELECT * FROM check_master_comment_triggers(%s)", (user_email,))
        triggers = cur.fetchall()

        if not triggers:
            return None

        # Create comment for the first trigger found
        trigger = triggers[0]

        # Check if this comment was already created
        check_query = """
        SELECT id FROM master_comments
        WHERE user_email = %s
          AND trigger_type = %s
          AND created_at > NOW() - INTERVAL '1 day'
        """

        cur.execute(check_query, (user_email, trigger['trigger_type']))
        existing = cur.fetchone()

        if existing:
            logger.info(f"Master comment already exists for {trigger['trigger_type']}")
            return None

        # Create new master comment
        insert_query = """
        INSERT INTO master_comments (
            user_id, user_email, comment_type, title, content,
            trigger_type, trigger_value, master_name, is_ai_generated
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id, title, content
        """

        cur.execute(insert_query, (
            user_id,
            user_email,
            'milestone',
            trigger['title'],
            trigger['content'],
            trigger['trigger_type'],
            Json(trigger['trigger_value']),
            '聖嚴法師',
            True
        ))

        result = cur.fetchone()
        conn.commit()

        logger.info(f"Created master comment for {user_email}: {trigger['trigger_type']}")

        return dict(result)

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error checking master comments: {e}")
        return None
    finally:
        if conn:
            conn.close()

"""
Query Logger Module
Tracks all user queries, results, and user identification for debugging and analytics
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import hashlib


class QueryLogger:
    """Logs user queries with identification and results"""

    def __init__(self, log_dir: str = "logs", enable_file_logging: bool = True):
        """
        Initialize query logger

        Args:
            log_dir: Directory to store query logs
            enable_file_logging: Whether to write to log files (in addition to console)
        """
        self.log_dir = Path(log_dir)
        self.enable_file_logging = enable_file_logging

        # Create log directory if it doesn't exist
        if self.enable_file_logging:
            self.log_dir.mkdir(exist_ok=True)

            # Create subdirectories for different log types
            (self.log_dir / "queries").mkdir(exist_ok=True)
            (self.log_dir / "daily").mkdir(exist_ok=True)

        # Setup logger
        self.logger = logging.getLogger("query_logger")
        self.logger.setLevel(logging.INFO)

        # Console handler (always enabled)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # File handler for daily logs (if enabled)
        if self.enable_file_logging:
            daily_log_file = self.log_dir / "daily" / f"{datetime.now().strftime('%Y-%m-%d')}.log"
            file_handler = logging.FileHandler(daily_log_file, encoding='utf-8')
            file_handler.setLevel(logging.INFO)
            file_formatter = logging.Formatter(
                '%(asctime)s - [%(levelname)s] - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

    def _hash_ip(self, ip: str) -> str:
        """Hash IP address for privacy (GDPR-friendly)"""
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    def _get_user_identifier(self, ip: str, user_email: Optional[str] = None) -> Dict[str, str]:
        """
        Generate user identifier from IP and optional email

        Args:
            ip: User's IP address
            user_email: User's email if logged in

        Returns:
            Dict with user identification info
        """
        user_id = {
            "ip_hash": self._hash_ip(ip),
            "ip_raw": ip,  # Store raw IP for debugging (can be disabled in production)
            "authenticated": user_email is not None,
            "user_email": user_email if user_email else "anonymous"
        }
        return user_id

    def log_query(
        self,
        query: str,
        result: Dict[str, Any],
        ip_address: str,
        user_email: Optional[str] = None,
        retrieval_mode: str = "rag",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a query with full context

        Args:
            query: The user's question
            result: The RAG result dictionary
            ip_address: User's IP address
            user_email: User's email if authenticated
            retrieval_mode: Type of retrieval (rag, retrieve_only, etc.)
            metadata: Additional metadata to log

        Returns:
            Query log ID (timestamp-based)
        """
        timestamp = datetime.now()
        query_id = timestamp.strftime('%Y%m%d_%H%M%S_%f')

        # Extract relevant result information
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        computation_time = result.get("computation_time", 0)

        # Ensure computation_time is a number
        if not isinstance(computation_time, (int, float)):
            computation_time = 0

        # Build user identification
        user_info = self._get_user_identifier(ip_address, user_email)

        # Create log entry
        log_entry = {
            "query_id": query_id,
            "timestamp": timestamp.isoformat(),
            "user": user_info,
            "query": {
                "question": query,
                "retrieval_mode": retrieval_mode,
                "character_count": len(query),
                "word_count": len(query.split())
            },
            "result": {
                "answer": answer,
                "answer_length": len(answer),
                "answer_word_count": len(answer.split()),
                "sources_count": len(sources),
                "computation_time": computation_time,
                "cached": result.get("cached", False)
            },
            "sources": [
                {
                    "id": src.get("id"),
                    "header": src.get("header"),
                    "score": src.get("score"),
                    "content_preview": src.get("content", "")[:200] + "..." if src.get("content") else ""
                }
                for src in sources
            ],
            "metadata": metadata or {}
        }

        # Log to console/file
        log_message = (
            f"QUERY | User: {user_info['user_email']} ({user_info['ip_hash']}) | "
            f"Q: \"{query[:100]}{'...' if len(query) > 100 else ''}\" | "
            f"Mode: {retrieval_mode} | "
            f"Sources: {len(sources)} | "
            f"Time: {computation_time:.2f}s"
        )
        self.logger.info(log_message)

        # Write detailed JSON log to file (if enabled)
        if self.enable_file_logging:
            query_log_file = self.log_dir / "queries" / f"{query_id}.json"
            with open(query_log_file, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, ensure_ascii=False, indent=2)

        return query_id

    def log_error(
        self,
        query: str,
        error: Exception,
        ip_address: str,
        user_email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Log a query error

        Args:
            query: The user's question
            error: The exception that occurred
            ip_address: User's IP address
            user_email: User's email if authenticated
            metadata: Additional metadata

        Returns:
            Error log ID
        """
        timestamp = datetime.now()
        error_id = timestamp.strftime('%Y%m%d_%H%M%S_%f')

        user_info = self._get_user_identifier(ip_address, user_email)

        error_entry = {
            "error_id": error_id,
            "timestamp": timestamp.isoformat(),
            "user": user_info,
            "query": query,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": None  # Can add traceback if needed
            },
            "metadata": metadata or {}
        }

        # Log to console/file
        log_message = (
            f"ERROR | User: {user_info['user_email']} ({user_info['ip_hash']}) | "
            f"Q: \"{query[:100]}{'...' if len(query) > 100 else ''}\" | "
            f"Error: {type(error).__name__}: {str(error)}"
        )
        self.logger.error(log_message)

        # Write detailed JSON log to file (if enabled)
        if self.enable_file_logging:
            error_log_file = self.log_dir / "queries" / f"ERROR_{error_id}.json"
            with open(error_log_file, 'w', encoding='utf-8') as f:
                json.dump(error_entry, f, ensure_ascii=False, indent=2)

        return error_id

    def get_stats(self, date: Optional[str] = None) -> Dict[str, Any]:
        """
        Get query statistics for a specific date or today

        Args:
            date: Date in YYYY-MM-DD format (default: today)

        Returns:
            Statistics dictionary
        """
        if not self.enable_file_logging:
            return {"error": "File logging disabled"}

        target_date = date if date else datetime.now().strftime('%Y-%m-%d')
        query_files = list((self.log_dir / "queries").glob(f"{target_date.replace('-', '')}*.json"))

        stats = {
            "date": target_date,
            "total_queries": 0,
            "authenticated_queries": 0,
            "anonymous_queries": 0,
            "total_errors": 0,
            "unique_users": set(),
            "avg_computation_time": 0,
            "avg_sources_count": 0,
            "retrieval_modes": {}
        }

        total_time = 0
        total_sources = 0

        for query_file in query_files:
            try:
                with open(query_file, 'r', encoding='utf-8') as f:
                    entry = json.load(f)

                if "error_id" in entry:
                    stats["total_errors"] += 1
                    continue

                stats["total_queries"] += 1

                user_email = entry.get("user", {}).get("user_email", "anonymous")
                if user_email != "anonymous":
                    stats["authenticated_queries"] += 1
                    stats["unique_users"].add(user_email)
                else:
                    stats["anonymous_queries"] += 1

                total_time += entry.get("result", {}).get("computation_time", 0)
                total_sources += entry.get("result", {}).get("sources_count", 0)

                mode = entry.get("query", {}).get("retrieval_mode", "unknown")
                stats["retrieval_modes"][mode] = stats["retrieval_modes"].get(mode, 0) + 1

            except Exception as e:
                self.logger.warning(f"Error reading log file {query_file}: {e}")

        if stats["total_queries"] > 0:
            stats["avg_computation_time"] = total_time / stats["total_queries"]
            stats["avg_sources_count"] = total_sources / stats["total_queries"]

        stats["unique_users"] = len(stats["unique_users"])

        return stats


# Global query logger instance
_query_logger: Optional[QueryLogger] = None


def get_query_logger(
    log_dir: str = "logs",
    enable_file_logging: bool = True
) -> QueryLogger:
    """Get or create the global query logger instance"""
    global _query_logger
    if _query_logger is None:
        _query_logger = QueryLogger(log_dir, enable_file_logging)
    return _query_logger

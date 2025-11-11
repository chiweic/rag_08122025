#!/usr/bin/env python3
"""
PostgreSQL Database Examination Tool

This script helps examine the ddm_postgres database structure and content.

Usage:
    # List all tables
    python examine_postgres.py --list-tables

    # Examine specific table
    python examine_postgres.py --table table_name

    # Show table schema
    python examine_postgres.py --schema table_name

    # Execute custom query
    python examine_postgres.py --query "SELECT * FROM table_name LIMIT 10"

    # Export table to JSON
    python examine_postgres.py --export table_name --output output.json

Author: DDM RAG Team
Created: 2025-11-10
"""

import os
import sys
import json
import argparse
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import psycopg2
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logger.warning("psycopg2 not available. Install with: pip install psycopg2-binary")


def get_db_connection():
    """
    Create PostgreSQL database connection.

    Returns:
        Connection object or None if connection fails
    """
    if not PSYCOPG2_AVAILABLE:
        raise ImportError("psycopg2 未安裝。請執行: pip install psycopg2-binary")

    # Try multiple common environment variable patterns
    db_config = {
        'host': os.getenv('POSTGRES_HOST', os.getenv('DB_HOST', 'localhost')),
        'port': int(os.getenv('POSTGRES_PORT', os.getenv('DB_PORT', '5432'))),
        'database': os.getenv('POSTGRES_DB', os.getenv('DB_NAME', 'ddm_postgres')),
        'user': os.getenv('POSTGRES_USER', os.getenv('DB_USER', 'postgres')),
        'password': os.getenv('POSTGRES_PASSWORD', os.getenv('DB_PASSWORD', ''))
    }

    logger.info(f"連接到 PostgreSQL: {db_config['user']}@{db_config['host']}:{db_config['port']}/{db_config['database']}")

    try:
        conn = psycopg2.connect(**db_config)
        logger.info("✅ 數據庫連接成功")
        return conn
    except Exception as e:
        logger.error(f"❌ 數據庫連接失敗: {e}")
        logger.info("\n提示：請在 .env 文件中設置以下環境變量:")
        logger.info("  POSTGRES_HOST=localhost")
        logger.info("  POSTGRES_PORT=5432")
        logger.info("  POSTGRES_DB=ddm_postgres")
        logger.info("  POSTGRES_USER=your_username")
        logger.info("  POSTGRES_PASSWORD=your_password")
        raise


def list_tables(conn) -> List[str]:
    """List all tables in the database."""
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """

    with conn.cursor() as cur:
        cur.execute(query)
        tables = [row[0] for row in cur.fetchall()]

    return tables


def get_table_schema(conn, table_name: str) -> List[Dict[str, Any]]:
    """Get schema information for a table."""
    query = """
        SELECT
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position;
    """

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (table_name,))
        columns = cur.fetchall()

    return columns


def get_table_count(conn, table_name: str) -> int:
    """Get row count for a table."""
    query = f"SELECT COUNT(*) FROM {table_name};"

    with conn.cursor() as cur:
        cur.execute(query)
        count = cur.fetchone()[0]

    return count


def preview_table(conn, table_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Preview table contents."""
    query = f"SELECT * FROM {table_name} LIMIT %s;"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query, (limit,))
        rows = cur.fetchall()

    return rows


def execute_query(conn, query: str) -> List[Dict[str, Any]]:
    """Execute custom query."""
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()

    return rows


def export_table_to_json(conn, table_name: str, output_path: str, limit: Optional[int] = None):
    """Export table to JSON file."""
    if limit:
        query = f"SELECT * FROM {table_name} LIMIT {limit};"
    else:
        query = f"SELECT * FROM {table_name};"

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(query)
        rows = cur.fetchall()

    # Convert to JSON-serializable format
    json_data = []
    for row in rows:
        json_row = {}
        for key, value in row.items():
            # Handle datetime, date, and other non-serializable types
            if hasattr(value, 'isoformat'):
                json_row[key] = value.isoformat()
            else:
                json_row[key] = value
        json_data.append(json_row)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 導出 {len(json_data)} 行到 {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PostgreSQL 數據庫檢查工具"
    )
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="列出所有表"
    )
    parser.add_argument(
        "--table",
        type=str,
        help="檢查指定表"
    )
    parser.add_argument(
        "--schema",
        type=str,
        help="顯示表結構"
    )
    parser.add_argument(
        "--query",
        type=str,
        help="執行自定義 SQL 查詢"
    )
    parser.add_argument(
        "--export",
        type=str,
        help="導出表到 JSON"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="export.json",
        help="導出文件路徑 (預設：export.json)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="預覽/導出行數限制 (預設：10，0=全部)"
    )

    args = parser.parse_args()

    # Connect to database
    try:
        conn = get_db_connection()
    except Exception as e:
        logger.error(f"無法連接到數據庫: {e}")
        sys.exit(1)

    try:
        # List tables
        if args.list_tables:
            logger.info("\n" + "="*60)
            logger.info("數據庫表列表")
            logger.info("="*60)

            tables = list_tables(conn)

            if not tables:
                logger.warning("未找到任何表")
            else:
                for i, table in enumerate(tables, 1):
                    count = get_table_count(conn, table)
                    logger.info(f"{i}. {table} ({count:,} 行)")

        # Show table schema
        elif args.schema:
            logger.info("\n" + "="*60)
            logger.info(f"表結構: {args.schema}")
            logger.info("="*60)

            schema = get_table_schema(conn, args.schema)

            if not schema:
                logger.error(f"表 '{args.schema}' 不存在")
            else:
                for col in schema:
                    data_type = col['data_type']
                    if col['character_maximum_length']:
                        data_type += f"({col['character_maximum_length']})"

                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f"DEFAULT {col['column_default']}" if col['column_default'] else ""

                    logger.info(f"  {col['column_name']:<30} {data_type:<20} {nullable:<10} {default}")

        # Examine table
        elif args.table:
            logger.info("\n" + "="*60)
            logger.info(f"表檢查: {args.table}")
            logger.info("="*60)

            # Get count
            count = get_table_count(conn, args.table)
            logger.info(f"總行數: {count:,}")

            # Get schema
            schema = get_table_schema(conn, args.table)
            logger.info(f"\n列數: {len(schema)}")
            logger.info("\n列名:")
            for col in schema:
                logger.info(f"  - {col['column_name']} ({col['data_type']})")

            # Preview data
            logger.info(f"\n數據預覽 (前 {args.limit} 行):")
            rows = preview_table(conn, args.table, limit=args.limit)

            for i, row in enumerate(rows, 1):
                logger.info(f"\n--- 行 {i} ---")
                for key, value in row.items():
                    # Truncate long values
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:100] + "..."
                    logger.info(f"  {key}: {value_str}")

        # Execute custom query
        elif args.query:
            logger.info("\n" + "="*60)
            logger.info("執行查詢")
            logger.info("="*60)
            logger.info(f"SQL: {args.query}\n")

            rows = execute_query(conn, args.query)

            logger.info(f"返回 {len(rows)} 行\n")

            for i, row in enumerate(rows, 1):
                logger.info(f"--- 行 {i} ---")
                for key, value in row.items():
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:100] + "..."
                    logger.info(f"  {key}: {value_str}")

        # Export table
        elif args.export:
            logger.info("\n" + "="*60)
            logger.info(f"導出表: {args.export}")
            logger.info("="*60)

            limit = args.limit if args.limit > 0 else None
            export_table_to_json(conn, args.export, args.output, limit=limit)

        else:
            parser.print_help()

    finally:
        conn.close()
        logger.info("\n✅ 數據庫連接已關閉")


if __name__ == "__main__":
    main()

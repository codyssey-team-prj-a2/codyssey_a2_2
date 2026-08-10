"""SQLite database access layer: schema creation and CRUD helpers."""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import config

logger = logging.getLogger(__name__)

NEWS_SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    content TEXT,
    url TEXT NOT NULL UNIQUE,
    source TEXT,
    category TEXT,
    published_at TEXT,
    collected_at TEXT,
    collection_method TEXT,
    status TEXT NOT NULL DEFAULT 'raw',
    summary TEXT,
    sentiment TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

ANALYSIS_SCHEMA = """
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_date TEXT,
    end_date TEXT,
    category TEXT,
    analysis_type TEXT,
    result TEXT,
    created_at TEXT NOT NULL
);
"""


def now_str() -> str:
    """Current UTC time formatted as YYYY-MM-DD HH:MM:SS."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection with row access by column name."""
    config.ensure_directories()
    path = db_path or config.DB_PATH
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create tables if they do not already exist."""
    conn = get_connection(db_path)
    try:
        conn.execute(NEWS_SCHEMA)
        conn.execute(ANALYSIS_SCHEMA)
        conn.commit()
        logger.info("데이터베이스 초기화 완료: %s", db_path or config.DB_PATH)
    finally:
        conn.close()


def article_exists(conn: sqlite3.Connection, url: str) -> sqlite3.Row | None:
    """Return the existing row for this URL, or None."""
    cursor = conn.execute("SELECT * FROM news WHERE url = ?", (url,))
    return cursor.fetchone()


def insert_article(conn: sqlite3.Connection, article: dict[str, Any]) -> int:
    """Insert a new article row and return its id."""
    timestamp = now_str()
    cursor = conn.execute(
        """
        INSERT INTO news (
            title, description, content, url, source, category,
            published_at, collected_at, collection_method, status,
            summary, sentiment, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            article.get("title"),
            article.get("description"),
            article.get("content"),
            article.get("url"),
            article.get("source"),
            article.get("category"),
            article.get("published_at"),
            article.get("collected_at"),
            article.get("collection_method"),
            article.get("status", "raw"),
            article.get("summary"),
            article.get("sentiment"),
            timestamp,
            timestamp,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def upsert_article(conn: sqlite3.Connection, article: dict[str, Any]) -> int:
    """Insert the article, or update it in place if the URL already exists."""
    existing = article_exists(conn, article["url"])
    if existing is None:
        return insert_article(conn, article)

    conn.execute(
        """
        UPDATE news SET
            title = ?, description = ?, content = ?, source = ?, category = ?,
            published_at = ?, collected_at = ?, collection_method = ?, updated_at = ?
        WHERE url = ?
        """,
        (
            article.get("title"),
            article.get("description"),
            article.get("content"),
            article.get("source"),
            article.get("category"),
            article.get("published_at"),
            article.get("collected_at"),
            article.get("collection_method"),
            now_str(),
            article["url"],
        ),
    )
    conn.commit()
    return existing["id"]


def save_article(conn: sqlite3.Connection, article: dict[str, Any], duplicate_policy: str = "skip") -> tuple[int | None, str]:
    """Save an article according to the duplicate policy.

    Returns (row_id_or_None, outcome) where outcome is one of
    "inserted", "updated", "skipped".
    """
    existing = article_exists(conn, article["url"])
    if existing is not None and duplicate_policy == "skip":
        logger.warning("중복 뉴스 건너뜀 (URL 이미 존재): %s", article["url"])
        return None, "skipped"
    if existing is not None and duplicate_policy == "upsert":
        row_id = upsert_article(conn, article)
        return row_id, "updated"
    row_id = insert_article(conn, article)
    return row_id, "inserted"


def update_summary(conn: sqlite3.Connection, article_id: int, summary: str, status: str = "summarized") -> None:
    conn.execute(
        "UPDATE news SET summary = ?, status = ?, updated_at = ? WHERE id = ?",
        (summary, status, now_str(), article_id),
    )
    conn.commit()


def update_status(conn: sqlite3.Connection, article_id: int, status: str) -> None:
    conn.execute(
        "UPDATE news SET status = ?, updated_at = ? WHERE id = ?",
        (status, now_str(), article_id),
    )
    conn.commit()


def update_sentiment(conn: sqlite3.Connection, article_id: int, sentiment: str) -> None:
    conn.execute(
        "UPDATE news SET sentiment = ?, updated_at = ? WHERE id = ?",
        (sentiment, now_str(), article_id),
    )
    conn.commit()


def update_cleaned_fields(conn: sqlite3.Connection, article_id: int, fields: dict[str, Any]) -> None:
    """Update arbitrary cleaned fields (title/description/content/published_at/status/...)."""
    if not fields:
        return
    columns = ", ".join(f"{key} = ?" for key in fields)
    values: list[Any] = list(fields.values())
    values.append(now_str())
    values.append(article_id)
    conn.execute(f"UPDATE news SET {columns}, updated_at = ? WHERE id = ?", values)
    conn.commit()


def fetch_articles(
    conn: sqlite3.Connection,
    status: str | None = None,
    category: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    keyword: str | None = None,
    article_id: int | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> list[sqlite3.Row]:
    """Flexible article query used by clean/summarize/list/export/report."""
    query = "SELECT * FROM news WHERE 1=1"
    params: list[Any] = []

    if article_id is not None:
        query += " AND id = ?"
        params.append(article_id)
    if status is not None:
        query += " AND status = ?"
        params.append(status)
    if category is not None:
        query += " AND category = ?"
        params.append(category)
    if start_date is not None:
        query += " AND date(published_at) >= date(?)"
        params.append(start_date)
    if end_date is not None:
        query += " AND date(published_at) <= date(?)"
        params.append(end_date)
    if keyword is not None:
        query += " AND (title LIKE ? OR description LIKE ?)"
        like = f"%{keyword}%"
        params.extend([like, like])

    query += " ORDER BY collected_at DESC"
    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    cursor = conn.execute(query, params)
    return cursor.fetchall()


def get_article_by_id(conn: sqlite3.Connection, article_id: int) -> sqlite3.Row | None:
    cursor = conn.execute("SELECT * FROM news WHERE id = ?", (article_id,))
    return cursor.fetchone()


def count_articles(conn: sqlite3.Connection, **filters: Any) -> int:
    return len(fetch_articles(conn, **filters))


def save_analysis_result(
    conn: sqlite3.Connection,
    start_date: str | None,
    end_date: str | None,
    category: str | None,
    analysis_type: str,
    result: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO analysis_results (start_date, end_date, category, analysis_type, result, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (start_date, end_date, category, analysis_type, result, now_str()),
    )
    conn.commit()
    return cursor.lastrowid


def fetch_latest_analysis(
    conn: sqlite3.Connection,
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
) -> sqlite3.Row | None:
    query = "SELECT * FROM analysis_results WHERE 1=1"
    params: list[Any] = []
    if start_date is not None:
        query += " AND start_date = ?"
        params.append(start_date)
    if end_date is not None:
        query += " AND end_date = ?"
        params.append(end_date)
    if category is not None:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY created_at DESC LIMIT 1"
    cursor = conn.execute(query, params)
    return cursor.fetchone()

"""SQLite 연결/스키마/CRUD 공통 함수 (clean 데이터 전용)."""
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "news_pipeline.db"


def configure(db_path: str | None) -> None:
    """main.py가 기동 시 config.json의 storage.db_path로 덮어쓰기 위해 호출한다."""
    global DB_PATH
    if db_path:
        DB_PATH = BASE_DIR / db_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT,
    method TEXT,
    category TEXT,
    title TEXT,
    content TEXT,
    url TEXT UNIQUE,
    published_at TEXT,
    collected_at TEXT,
    cleaned_at TEXT,
    summary TEXT,
    is_summarized INTEGER DEFAULT 0,
    sentiment TEXT,
    sentiment_reason TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date_from TEXT,
    date_to TEXT,
    category TEXT,
    trends TEXT,
    keywords TEXT,
    implications TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_by_url(url: str) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM news WHERE url = ?", (url,))
        return cur.fetchone()
    finally:
        conn.close()


def insert_news(record: dict) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO news
               (source_name, method, category, title, content, url,
                published_at, collected_at, cleaned_at)
               VALUES (:source_name, :method, :category, :title, :content, :url,
                       :published_at, :collected_at, :cleaned_at)""",
            record,
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_by_id(news_id: int) -> sqlite3.Row | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM news WHERE id = ?", (news_id,))
        return cur.fetchone()
    finally:
        conn.close()


def list_news(limit: int | None = None, unsummarized_only: bool = False) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        sql = "SELECT * FROM news"
        if unsummarized_only:
            sql += " WHERE is_summarized = 0"
        sql += " ORDER BY id"
        if limit is not None:
            sql += " LIMIT ?"
            cur = conn.execute(sql, (limit,))
        else:
            cur = conn.execute(sql)
        return cur.fetchall()
    finally:
        conn.close()


def update_summary(news_id: int, summary: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE news SET summary = ?, is_summarized = 1 WHERE id = ?", (summary, news_id)
        )
        conn.commit()
    finally:
        conn.close()


def build_filter_sql(  # noqa: PLR0913 -- query_news/count_news가 공유하는 필터 조립 함수
    date_from, date_to, category, keyword, status, sentiment
) -> tuple[str, list]:
    sql = ""
    params: list = []
    if date_from:
        sql += " AND substr(published_at, 1, 10) >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND substr(published_at, 1, 10) <= ?"
        params.append(date_to)
    if category:
        sql += " AND category = ?"
        params.append(category)
    if keyword:
        sql += " AND (title LIKE ? OR content LIKE ?)"
        params += [f"%{keyword}%", f"%{keyword}%"]
    if status == "summarized":
        sql += " AND is_summarized = 1"
    elif status == "unsummarized":
        sql += " AND is_summarized = 0"
    if sentiment:
        sql += " AND sentiment = ?"
        params.append(sentiment)
    return sql, params


# 문자열을 그대로 SQL에 꽂지 않도록, 허용된 정렬 기준만 화이트리스트로 관리한다.
# 목록 화면(list/browse)은 "발행일" 컬럼을 보여주므로, 기본 정렬도 그 컬럼(published_at)
# 기준 최신순이어야 화면에 보이는 날짜가 뒤죽박죽으로 보이지 않는다.
# published_at이 초 단위까지 완전히 같은 기사가 실제로 존재하는데(같은 배치로 수집된
# 크롤링 기사 등), 1차 기준만 있으면 동점 안에서의 순서를 SQLite가 보장하지 않아
# id가 뒤섞여 보인다. 그래서 항상 id DESC를 2차 기준으로 붙여 동점을 없앤다.
ORDER_BY_PUBLISHED_DESC = "published_at_desc"
ORDER_BY_COLLECTED_DESC = "collected_at_desc"
ORDER_BY_ID_DESC = "id_desc"
_ORDER_BY_SQL = {
    ORDER_BY_PUBLISHED_DESC: "published_at DESC, id DESC",
    ORDER_BY_COLLECTED_DESC: "collected_at DESC, id DESC",
    ORDER_BY_ID_DESC: "id DESC",
}


def query_news(  # noqa: PLR0913 -- 조회 필터 함수라 옵션 인자가 많은 것이 자연스러움
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    keyword: str | None = None,
    status: str | None = None,
    sentiment: str | None = None,
    order_by: str = ORDER_BY_PUBLISHED_DESC,
    limit: int | None = None,
    offset: int = 0,
) -> list[sqlite3.Row]:
    where_sql, params = build_filter_sql(date_from, date_to, category, keyword, status, sentiment)
    order_sql = _ORDER_BY_SQL.get(order_by, _ORDER_BY_SQL[ORDER_BY_PUBLISHED_DESC])
    sql = "SELECT * FROM news WHERE 1=1" + where_sql + " ORDER BY " + order_sql
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params = params + [limit, offset]

    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def count_news(  # noqa: PLR0913 -- query_news와 동일한 필터를 그대로 받는 카운트 함수
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    keyword: str | None = None,
    status: str | None = None,
    sentiment: str | None = None,
) -> int:
    where_sql, params = build_filter_sql(date_from, date_to, category, keyword, status, sentiment)
    sql = "SELECT COUNT(*) FROM news WHERE 1=1" + where_sql

    conn = get_connection()
    try:
        return conn.execute(sql, params).fetchone()[0]
    finally:
        conn.close()


def insert_analysis_result(  # noqa: PLR0913 -- 분석 결과의 각 필드를 그대로 받는 저장 함수
    date_from, date_to, category, trends: str, keywords: str, implications: str
) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO analysis_results
               (date_from, date_to, category, trends, keywords, implications)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (date_from, date_to, category, trends, keywords, implications),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def count_existing_urls(urls: list[str]) -> int:
    """주어진 url 목록 중 이미 news 테이블에 존재하는 건수를 센다 (중복 수집 방지율 집계용)."""
    if not urls:
        return 0
    conn = get_connection()
    try:
        placeholders = ",".join("?" * len(urls))
        cur = conn.execute(f"SELECT COUNT(*) FROM news WHERE url IN ({placeholders})", urls)
        return cur.fetchone()[0]
    finally:
        conn.close()


def list_categories() -> list[str]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM news WHERE category IS NOT NULL ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]
    finally:
        conn.close()


def get_latest_analysis() -> sqlite3.Row | None:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT * FROM analysis_results ORDER BY id DESC LIMIT 1")
        return cur.fetchone()
    finally:
        conn.close()


def list_analysis_results(  # noqa: PLR0913 -- 분석 이력 필터 함수라 옵션 인자가 많은 것이 자연스러움
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
    limit: int | None = None,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM analysis_results WHERE 1=1"
    params: list = []
    if date_from:
        sql += " AND substr(created_at, 1, 10) >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND substr(created_at, 1, 10) <= ?"
        params.append(date_to)
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY id DESC"

    conn = get_connection()
    try:
        if limit is not None:
            return conn.execute(sql + " LIMIT ?", params + [limit]).fetchall()
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def list_news_without_sentiment(limit: int | None = None) -> list[sqlite3.Row]:
    conn = get_connection()
    try:
        sql = "SELECT * FROM news WHERE sentiment IS NULL ORDER BY id"
        if limit is not None:
            return conn.execute(sql + " LIMIT ?", (limit,)).fetchall()
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def update_sentiment(news_id: int, sentiment: str, reason: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE news SET sentiment = ?, sentiment_reason = ? WHERE id = ?",
            (sentiment, reason, news_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_news(news_id: int, record: dict) -> None:
    conn = get_connection()
    try:
        record = {**record, "id": news_id}
        conn.execute(
            """UPDATE news SET
               source_name=:source_name, method=:method, category=:category,
               title=:title, content=:content, published_at=:published_at,
               collected_at=:collected_at, cleaned_at=:cleaned_at
               WHERE id=:id""",
            record,
        )
        conn.commit()
    finally:
        conn.close()

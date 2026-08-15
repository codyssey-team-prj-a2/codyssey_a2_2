# src/lib/db/sqlite_mgr.py
import sqlite3
import os
from lib.system import config_mgr

# src/lib/db/sqlite_mgr.py
import sqlite3
import os
from lib.system import config_mgr

# ==========================================
# 1. DB 연결 및 초기화 영역
# ==========================================
def get_db_connection():
    cfg = config_mgr.load_config()
    db_path = cfg.get("storage", {}).get("db_path") or os.path.join("./data", "codyssey.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # 딕셔너리 형태로 결과를 반환하도록 Row 팩토리 설정 (사용하기 편함)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def initialize_db():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    schema_path = os.path.join(current_dir, "schema.sql")
    
    if not os.path.exists(schema_path):
        return False

    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_script = f.read()

    try:
        with get_db_connection() as conn:
            conn.executescript(schema_script)
            conn.commit()
            _migrate_schema(conn)
        return True
    except Exception as e:
        print(f"[DB 초기화 에러] {e}")
        return False

def _migrate_schema(conn):
    """
    기존에 생성된 DB에 schema.sql 신규 컬럼(예: sentiment)이 없다면 추가한다.
    CREATE TABLE IF NOT EXISTS 는 이미 존재하는 테이블의 컬럼을 갱신하지 않기 때문에 필요하다.
    """
    existing_cols = {row["name"] for row in conn.execute("PRAGMA table_info(clean_news)")}
    migrations = {
        "sentiment": "ALTER TABLE clean_news ADD COLUMN sentiment TEXT",
        "sentiment_reason": "ALTER TABLE clean_news ADD COLUMN sentiment_reason TEXT",
    }
    for col, ddl in migrations.items():
        if col not in existing_cols:
            conn.execute(ddl)
    conn.commit()

# ==========================================
# 2. 팀원들을 위한 데이터 조작 함수 모음
# ==========================================

def upsert_clean_news(news_list):
    """
    [ clean.py 작업자용 ]
    정제된 뉴스 리스트를 받아 DB에 적재합니다. 
    이미 존재하는 news_id 라면 title과 content만 업데이트(Upsert)합니다.
    
    :param news_list: [{"news_id": "URL", "source": "...", "category": "...", "title": "...", "content": "...", "pub_date": "..."}, ...]
    :return: 적재 성공 건수
    """
    if not news_list: return 0
    
    sql = """
        INSERT INTO clean_news (news_id, source, category, title, content, pub_date)
        VALUES (:news_id, :source, :category, :title, :content, :pub_date)
        ON CONFLICT(news_id) DO UPDATE SET 
            title = excluded.title,
            content = excluded.content;
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany(sql, news_list)
            conn.commit()
            return cursor.rowcount
    except Exception as e:
        print(f"[DB Upsert 에러] {e}")
        return 0

def get_unsummarized_news(limit=50):
    """
    [ summarize.py 작업자용 ]
    is_summarized 플래그가 0인(아직 요약되지 않은) 기사 목록을 가져옵니다.
    """
    limit = max(limit, 1)  # SQLite는 음수 LIMIT을 "무제한"으로 해석하므로 방어적으로 clamp
    sql = """
        SELECT news_id, title, content 
        FROM clean_news 
        WHERE is_summarized = 0 
        LIMIT ?
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (limit,))
            # Row 객체를 딕셔너리로 변환하여 반환
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return []

def update_ai_summary(news_id, ai_summary):
    """
    [ summarize.py 작업자용 ]
    특정 기사에 AI 요약문을 저장하고 플래그(is_summarized)를 1로 변경합니다.
    """
    sql = """
        UPDATE clean_news 
        SET ai_summary = ?, is_summarized = 1 
        WHERE news_id = ?
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (ai_summary, news_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"[DB Update 에러] {e}")
        return False

# ==========================================
# 3. 품질 지표 및 TOP N 집계 SQL (report.py 작업자용)
# ==========================================

def date_range_conditions(date_from, date_to, column="pub_date"):
    """
    date_from/date_to 중 하나만 주어져도 그 방향으로 필터링되도록 독립적인
    >=/<= 조건을 만든다(analyze.py의 query_clean_news와 동일한 방식).
    BETWEEN을 쓰면 둘 다 있어야만 조건이 걸려서 한쪽만 지정 시 필터가 무시되는 버그가 있었다.
    """
    conditions = []
    params = []
    if date_from:
        conditions.append(f"{column} >= ?")
        params.append(date_from)
    if date_to:
        conditions.append(f"{column} <= ?")
        params.append(date_to)
    return conditions, params


def get_clean_news_count(date_from=None, date_to=None):
    """
    [ report.py 작업자용 ]
    clean_news 테이블의 전체(또는 기간 내) 건수를 셉니다.
    """
    conditions, params = date_range_conditions(date_from, date_to)
    sql = "SELECT COUNT(*) AS cnt FROM clean_news"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    try:
        with get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"] if row else 0
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return 0

def get_summarize_success_rate(date_from=None, date_to=None):
    """
    [ report.py 작업자용 ]
    ② AI 요약 성공률 = (요약 성공 건수 / 요약 시도 대상 전체 건수) * 100
    is_summarized=1 인 건수를 성공 건수로, clean_news 전체 건수를 시도 대상으로 집계합니다.
    date_from/date_to 지정 시 pub_date 기준으로 대상을 좁힙니다.
    """
    conditions, params = date_range_conditions(date_from, date_to)
    sql = "SELECT COUNT(*) AS total, SUM(is_summarized) AS success FROM clean_news"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    try:
        with get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        total = row["total"] or 0
        success = row["success"] or 0
        rate = round((success / total) * 100, 2) if total else 0.0
        return {"total_target": total, "success_count": success, "rate": rate}
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return {"total_target": 0, "success_count": 0, "rate": 0.0}

def get_category_top_n(n=3, date_from=None, date_to=None):
    """
    [ report.py 작업자용 ]
    ② 카테고리별 뉴스 수집량 TOP N (기본 3) 을 GROUP BY + LIMIT 으로 집계합니다.
    """
    conditions, params = date_range_conditions(date_from, date_to)
    sql = "SELECT category, COUNT(*) AS cnt FROM clean_news"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " GROUP BY category ORDER BY cnt DESC LIMIT ?"
    params.append(n)
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return []

def get_keyword_top_n(n=5, date_from=None, date_to=None):
    """
    [ report.py 작업자용 ]
    ① 최다 출현 핵심 키워드 TOP N (기본 5).
    ai_insight.core_keywords (콤마 구분 문자열)를 모두 모아 collections.Counter로 집계합니다.
    date_from/date_to 지정 시, 분석 기간(period_from~period_to)이 요청 범위와
    겹치는 ai_insight 레코드만 대상으로 합니다.
    """
    from collections import Counter

    conditions = []
    params = []
    if date_to:
        conditions.append("period_from <= ?")
        params.append(date_to)
    if date_from:
        conditions.append("period_to >= ?")
        params.append(date_from)

    sql = "SELECT core_keywords FROM ai_insight"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return []

    counter = Counter()
    for row in rows:
        keywords = row["core_keywords"] or ""
        for keyword in keywords.split(","):
            keyword = keyword.strip()
            if keyword:
                counter[keyword] += 1
    return counter.most_common(n)

# ==========================================
# 4. 내보내기용 조회 SQL (export.py 작업자용)
# ==========================================

def get_news_for_export(status="all", date_from=None, date_to=None):
    """
    [ export.py 작업자용 ]
    CSV/Excel/JSONL로 내보낼 clean_news 목록을 조회합니다.

    :param status: "all"(전체) 또는 "summarized"(is_summarized=1 인 기사만)
    :param date_from: 조회 시작일 (YYYY-MM-DD), 단독 지정 시 이 날짜 이후 전체
    :param date_to: 조회 종료일 (YYYY-MM-DD), 단독 지정 시 이 날짜 이전 전체
    """
    sql = """
        SELECT news_id, source, category, title, content, pub_date,
               ai_summary, is_summarized, created_at
        FROM clean_news
    """
    conditions, params = date_range_conditions(date_from, date_to)

    if status == "summarized":
        conditions.append("is_summarized = 1")

    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY pub_date, news_id"

    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return []

# ==========================================
# 5. CLI 데이터 탐색용 조회 SQL (list.py / show.py 작업자용)
# ==========================================

def get_news_list(page=1, size=10, category=None, date=None, keyword=None):
    """
    [ list.py / show.py 작업자용 ]
    clean_news 목록을 페이징(LIMIT/OFFSET)하여 조회합니다.
    category, date, keyword 필터링을 지원하며, 테이블 고유값(rowid)을 idx로 반환합니다.
    """
    page = max(page, 1)
    size = max(size, 1)
    offset = (page - 1) * size

    conditions = []
    params = []

    if category:
        conditions.append("category = ?")
        params.append(category)
    if date:
        conditions.append("pub_date LIKE ?")
        params.append(f"{date}%")
    
    # 키워드 검색: 제목(title) 또는 본문(content)에 포함되어 있는지 확인
    if keyword:
        conditions.append("(title LIKE ? OR content LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    try:
        with get_db_connection() as conn:
            total = conn.execute(
                f"SELECT COUNT(*) AS cnt FROM clean_news{where_clause}", params
            ).fetchone()["cnt"]

            # rowid를 고유 인덱스 번호(idx)로 추출
            rows = conn.execute(
                f"""
                SELECT rowid as idx, news_id, source, category, title, pub_date, is_summarized, content, ai_summary, sentiment, sentiment_reason, created_at
                FROM clean_news{where_clause}
                ORDER BY pub_date DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                params + [size, offset],
            ).fetchall()

        total_pages = (total + size - 1) // size if total else 0
        return {
            "items": [dict(row) for row in rows],
            "page": page,
            "size": size,
            "total": total,
            "total_pages": total_pages,
        }
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return {"items": [], "page": page, "size": size, "total": 0, "total_pages": 0}


def get_news_by_id(identifier):
    """
    [ show.py / list_news.py 작업자용 ]
    고유 index(rowid) 번호 또는 news_id(문자열 URL)를 통해 뉴스 1건의 상세 정보를 조회합니다.
    """
    try:
        with get_db_connection() as conn:
            # 입력값이 숫자면 고유 인덱스(rowid)로, 문자열이면 news_id(URL 등)로 유연하게 검색
            if str(identifier).isdigit():
                sql = "SELECT rowid as idx, * FROM clean_news WHERE rowid = ?"
            else:
                sql = "SELECT rowid as idx, * FROM clean_news WHERE news_id = ?"
                
            row = conn.execute(sql, (identifier,)).fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return None

# ==========================================
# 6. 감성 분석용 SQL [보너스] (sentiment.py 작업자용)
# ==========================================

def get_news_for_sentiment(target="unanalyzed", news_id=None, limit=10):
    """
    [ sentiment.py 작업자용 ]
    감성 분석 대상 뉴스를 조회합니다.

    :param target: "unanalyzed"(sentiment IS NULL 인 기사만, 기본), "all"(전체), "id"(단건)
    """
    limit = max(limit, 1)  # SQLite는 음수 LIMIT을 "무제한"으로 해석하므로 방어적으로 clamp
    if target == "id":
        if not news_id:
            return []
        sql = "SELECT news_id, title, ai_summary, content FROM clean_news WHERE news_id = ?"
        params = (news_id,)
    elif target == "all":
        sql = "SELECT news_id, title, ai_summary, content FROM clean_news LIMIT ?"
        params = (limit,)
    else:
        sql = "SELECT news_id, title, ai_summary, content FROM clean_news WHERE sentiment IS NULL LIMIT ?"
        params = (limit,)

    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return []

def update_sentiment(news_id, sentiment, reason):
    """
    [ sentiment.py 작업자용 ]
    특정 뉴스의 AI 감성 분석 결과(긍정/부정/중립, 이유)를 저장합니다.
    """
    sql = "UPDATE clean_news SET sentiment = ?, sentiment_reason = ? WHERE news_id = ?"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (sentiment, reason, news_id))
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"[DB Update 에러] {e}")
        return False

def get_sentiment_distribution(date_from=None, date_to=None):
    """
    [ report.py 작업자용 ]
    감성 분석이 완료된 뉴스의 감성별 분포(긍정/부정/중립)를 집계합니다.
    date_from/date_to 지정 시 pub_date 기준으로 대상을 좁힙니다.
    """
    conditions, params = date_range_conditions(date_from, date_to)
    conditions.insert(0, "sentiment IS NOT NULL")
    sql = "SELECT sentiment, COUNT(*) AS cnt FROM clean_news WHERE " + " AND ".join(conditions)
    sql += " GROUP BY sentiment"
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return []

def upsert_ai_insight(insight_data):
    """
    [ analyze.py 작업자용 ]
    AI 종합 분석 결과를 저장합니다. 
    동일 기간/카테고리가 이미 존재하면 내용을 덮어씁니다(Upsert).
    """
    sql = """
        INSERT INTO ai_insight (target_category, period_from, period_to, main_trend, core_keywords, implications)
        VALUES (:target_category, :period_from, :period_to, :main_trend, :core_keywords, :implications)
        ON CONFLICT(target_category, period_from, period_to) DO UPDATE SET 
            main_trend = excluded.main_trend,
            core_keywords = excluded.core_keywords,
            implications = excluded.implications,
            created_at = CURRENT_TIMESTAMP;
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, insight_data)
            conn.commit()
            return True
    except Exception as e:
        print(f"[DB Insight Upsert 에러] {e}")
        return False

def get_by_news_id(news_id):
    """
    [ clean.py 작업자용 ]
    news_id(URL) 기준으로 이미 저장된 기사가 있는지 확인합니다.
    duplicate_policy가 'skip'일 때 중복 여부 판단에 사용합니다.
    """
    sql = "SELECT news_id FROM clean_news WHERE news_id = ?"
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (news_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return None

def query_clean_news(date_from=None, date_to=None, category=None):
    """
    [ analyze.py 작업자용 ]
    pub_date 기간 및 category로 필터링한 뉴스 목록을 가져옵니다.
    date_from/date_to는 'YYYY-MM-DD' 형식, 셋 다 None이면 전체 대상입니다.
    """
    conditions = []
    params = []
    if date_from:
        conditions.append("pub_date >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("pub_date <= ?")
        params.append(date_to)
    if category:
        conditions.append("category = ?")
        params.append(category)

    sql = "SELECT news_id, source, category, title, content, ai_summary, pub_date FROM clean_news"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY pub_date DESC"

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return []
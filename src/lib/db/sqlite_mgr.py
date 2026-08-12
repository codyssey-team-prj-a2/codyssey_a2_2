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
    db_dir = cfg.get("db_path", "./data")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "codyssey.db")
    
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
        return True
    except Exception as e:
        print(f"[DB 초기화 에러] {e}")
        return False

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

def get_clean_news_count(date_from=None, date_to=None):
    """
    [ report.py 작업자용 ]
    clean_news 테이블의 전체(또는 기간 내) 건수를 셉니다.
    """
    sql = "SELECT COUNT(*) AS cnt FROM clean_news"
    params = []
    if date_from and date_to:
        sql += " WHERE pub_date BETWEEN ? AND ?"
        params = [date_from, date_to]
    try:
        with get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
            return row["cnt"] if row else 0
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return 0

def get_summarize_success_rate():
    """
    [ report.py 작업자용 ]
    ② AI 요약 성공률 = (요약 성공 건수 / 요약 시도 대상 전체 건수) * 100
    is_summarized=1 인 건수를 성공 건수로, clean_news 전체 건수를 시도 대상으로 집계합니다.
    """
    sql = "SELECT COUNT(*) AS total, SUM(is_summarized) AS success FROM clean_news"
    try:
        with get_db_connection() as conn:
            row = conn.execute(sql).fetchone()
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
    sql = "SELECT category, COUNT(*) AS cnt FROM clean_news"
    params = []
    if date_from and date_to:
        sql += " WHERE pub_date BETWEEN ? AND ?"
        params = [date_from, date_to]
    sql += " GROUP BY category ORDER BY cnt DESC LIMIT ?"
    params.append(n)
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[DB Select 에러] {e}")
        return []

def get_keyword_top_n(n=5):
    """
    [ report.py 작업자용 ]
    ① 최다 출현 핵심 키워드 TOP N (기본 5).
    ai_insight.core_keywords (콤마 구분 문자열)를 모두 모아 collections.Counter로 집계합니다.
    """
    from collections import Counter

    sql = "SELECT core_keywords FROM ai_insight"
    try:
        with get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
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
    :param date_from: 조회 시작일 (YYYY-MM-DD), date_to 와 함께 지정 시 BETWEEN 필터 적용
    :param date_to: 조회 종료일 (YYYY-MM-DD)
    """
    sql = """
        SELECT news_id, source, category, title, content, pub_date,
               ai_summary, is_summarized, created_at
        FROM clean_news
    """
    conditions = []
    params = []

    if status == "summarized":
        conditions.append("is_summarized = 1")
    if date_from and date_to:
        conditions.append("pub_date BETWEEN ? AND ?")
        params += [date_from, date_to]

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
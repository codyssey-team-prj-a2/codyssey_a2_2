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
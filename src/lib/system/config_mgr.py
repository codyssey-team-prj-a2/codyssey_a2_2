# lib/system/config_mgr.py
import json
import os
from pathlib import Path

# src/lib/system/ 기준 3단계 상위 = src/ 폴더
SRC_DIR = Path(__file__).resolve().parents[2]

CONFIG_FILE = SRC_DIR / "config.json"
ENV_FILE = SRC_DIR / ".env"


def load_config():
    """config.json 읽기 (빈 파일 또는 손상 시 예외 처리)"""
    if not os.path.exists(CONFIG_FILE) or os.path.getsize(CONFIG_FILE) == 0:
        save_config({})
        return {}
        
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        save_config({})
        return {}


def save_config(config_data):
    """config.json 저장"""
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)


def set_env(key, value):
    """ .env 파일 값 기록 """
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
    with open(ENV_FILE, 'w', encoding='utf-8') as f:
        updated = False
        for line in lines:
            if line.startswith(f"{key}="):
                f.write(f"{key}={value}\n")
                updated = True
            else:
                f.write(line)
        if not updated:
            f.write(f"{key}={value}\n")


def get_env(key):
    """.env 파일 값 조회"""
    if not os.path.exists(ENV_FILE):
        return None
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith(f"{key}="):
                val = line.strip().split("=", 1)[1]
                return val.strip().strip("'\"")
    return None


# ====================================================
# 실제 데이터 유효성 검증 함수 (설정 상태 실시간 판단)
# ====================================================
def is_ai_setup_complete():
    """1. AI 설정: 플랫폼, 모델명, API Key가 모두 실제 존재해야 완료"""
    prov = get_env("LLM_PROVIDER")
    model = get_env("LLM_MODEL")
    key = get_env("LLM_API_KEY")
    return bool(prov and model and key)


def is_news_setup_complete():
    """2. 뉴스 피드 설정: 등록된 뉴스 소스가 1개 이상 존재해야 완료"""
    cfg = load_config()
    sources = cfg.get("news_sources", [])
    return len(sources) > 0


def is_db_setup_complete():
    """3. DB 경로 설정: storage.db_path 설정이 지정되어 있어야 완료"""
    cfg = load_config()
    db_path = cfg.get("storage", {}).get("db_path")
    return bool(db_path)


def is_log_setup_complete():
    """4. 로그 설정: file 경로와 level이 모두 설정되어 있어야 완료"""
    cfg = load_config()
    logging_cfg = cfg.get("logging", {})
    return bool(logging_cfg.get("file") and logging_cfg.get("level"))


def get_setup_status():
    """각 설정별 실제 실시간 진행 상태 반환"""
    return {
        "setup_ai": is_ai_setup_complete(),
        "setup_news": is_news_setup_complete(),
        "setup_db": is_db_setup_complete(),
        "setup_log": is_log_setup_complete()
    }


def get_setup_progress():
    """전체 설정 완료 개수와 총 개수 반환"""
    status = get_setup_status()
    cnt = sum([
        status["setup_ai"],
        status["setup_news"],
        status["setup_db"],
        status["setup_log"]
    ])
    return cnt, 4
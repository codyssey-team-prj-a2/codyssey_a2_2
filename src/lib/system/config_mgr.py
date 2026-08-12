import json
import os
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2]

CONFIG_FILE = SRC_DIR / "config.json"
ENV_FILE = SRC_DIR / ".env"


def load_config():
    """config.json 읽기 (빈 파일 또는 손상 시 예외 처리)"""
    # CONFIG_FILE 변수 사용
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
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

def set_env(key, value):
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
    """간이 .env 읽기 함수 (현재 설정된 값 확인용)"""
    if not os.path.exists(ENV_FILE):
        return None
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.strip().split("=", 1)[1]
    return None

def get_setup_progress():
    """설정 진행 상황 반환 (완료된 갯수, 전체 갯수)"""
    cfg = load_config()
    cnt = sum([cfg.get("setup_ai", False), cfg.get("setup_news", False), cfg.get("setup_log", False)])
    return cnt, 3
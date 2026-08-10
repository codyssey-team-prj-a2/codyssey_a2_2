import json
import os

CONFIG_FILE = "config.json"
ENV_FILE = ".env"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"setup_ai": False, "setup_news": False, "setup_log": False, "news_sources": []}
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

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
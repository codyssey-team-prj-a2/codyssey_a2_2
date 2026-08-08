"""config.json / .env 로딩 및 저장."""
import json
from pathlib import Path

from dotenv import load_dotenv, set_key
import os

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"
ENV_PATH = BASE_DIR / ".env"

DEFAULT_CONFIG = {
    "ai": {"provider": "google", "model": "gemini-2.5-flash", "request_delay_sec": 4.0},
    "duplicate_policy": "skip",
    "request_delay_sec": 1.0,
    "sources": [],
}


def load_env() -> None:
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    load_dotenv(dotenv_path=ENV_PATH)


def get_env(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)


def set_env_var(key: str, value: str) -> None:
    if not ENV_PATH.exists():
        ENV_PATH.touch()
    set_key(str(ENV_PATH), key, value)
    os.environ[key] = value


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

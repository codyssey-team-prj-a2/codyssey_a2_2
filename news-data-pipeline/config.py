"""Configuration loading: config.json + environment variables (.env)."""

import json
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
import os

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config.json"

DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
CLEAN_DIR = DATA_DIR / "clean"
DB_DIR = DATA_DIR / "database"
SAMPLE_DIR = DATA_DIR / "sample"
DB_PATH = DB_DIR / "news.db"

REPORTS_DIR = BASE_DIR / "reports"
CHARTS_DIR = BASE_DIR / "charts"
LOGS_DIR = BASE_DIR / "logs"
LOG_PATH = LOGS_DIR / "app.log"

# .env is optional; the pipeline must still work without an API key.
load_dotenv(BASE_DIR / ".env")

_DEFAULT_CONFIG: dict[str, Any] = {
    "duplicate_policy": "skip",
    "http_timeout_seconds": 10,
    "crawl_delay_seconds": 1.5,
    "user_agent": "news-data-pipeline/1.0",
    "max_content_length": 5000,
    "openai_model": "gpt-4o-mini",
    "rss_sources": [],
    "crawl_targets": [],
}


def ensure_directories() -> None:
    """Create every directory the pipeline writes to, if missing."""
    for directory in (RAW_DIR, CLEAN_DIR, DB_DIR, SAMPLE_DIR, REPORTS_DIR, CHARTS_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    """Load config.json, falling back to defaults for any missing key."""
    config = dict(_DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except (json.JSONDecodeError, OSError) as exc:
            logging.getLogger(__name__).warning("config.json을 읽는 중 오류 발생, 기본값 사용: %s", exc)
    return config


def get_openai_api_key() -> str | None:
    """Read the OpenAI API key from the environment. Returns None if unset."""
    return os.environ.get("OPENAI_API_KEY") or None


def get_openai_base_url() -> str | None:
    """Read an optional OpenAI-compatible base URL (for proxies/alternate providers)."""
    return os.environ.get("OPENAI_BASE_URL") or None


def setup_logging() -> None:
    """Configure logging to both console and logs/app.log."""
    ensure_directories()
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return  # already configured

    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

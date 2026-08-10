"""Data cleaning: required-field validation, text normalization, date normalization."""

import logging
import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ("title", "url", "published_at")

# Common date formats seen across RSS feeds and APIs.
_DATE_FORMATS = (
    "%a, %d %b %Y %H:%M:%S %z",   # RFC 822 (most RSS)
    "%a, %d %b %Y %H:%M:%S %Z",
    "%Y-%m-%dT%H:%M:%S%z",        # ISO 8601 with offset
    "%Y-%m-%dT%H:%M:%SZ",         # ISO 8601 UTC
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def strip_html(text: str) -> str:
    """Remove HTML tags, keeping the visible text."""
    return BeautifulSoup(text, "html.parser").get_text()


def normalize_text(text: str | None, max_length: int = 5000) -> str | None:
    """Strip HTML, collapse whitespace, trim odd characters, and cap length."""
    if text is None:
        return None
    cleaned = strip_html(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned.replace("​", "")  # zero-width space
    if not cleaned:
        return None
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip() + "..."
    return cleaned


def normalize_date(raw_date: str | None) -> str | None:
    """Parse a variety of date formats into 'YYYY-MM-DD HH:MM:SS' (UTC-naive).

    Returns None if the date cannot be parsed.
    """
    if not raw_date:
        return None
    raw_date = raw_date.strip()

    for fmt in _DATE_FORMATS:
        try:
            parsed = datetime.strptime(raw_date, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(tz=None).replace(tzinfo=None)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue

    logger.warning("날짜 형식을 인식할 수 없음: %r", raw_date)
    return None


def validate_required_fields(article: dict[str, Any]) -> list[str]:
    """Return the list of missing required fields (empty list = valid)."""
    missing = []
    for field in REQUIRED_FIELDS:
        value = article.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def clean_article(article: dict[str, Any], max_content_length: int = 5000) -> dict[str, Any] | None:
    """Clean a single article dict (as returned by database.fetch_articles as a Row-mapping).

    Returns a dict of cleaned fields to update, or None if the article
    lacks required fields and cannot be cleaned.
    """
    working = dict(article)

    working["title"] = normalize_text(working.get("title"), max_length=300)
    working["description"] = normalize_text(working.get("description"), max_length=1000)
    working["content"] = normalize_text(working.get("content"), max_length=max_content_length)
    working["published_at"] = normalize_date(working.get("published_at"))

    missing = validate_required_fields(working)
    if missing:
        logger.warning("필수 필드 누락으로 정제 실패 (id=%s): %s", article.get("id"), missing)
        return None

    if not working.get("source"):
        working["source"] = "Unknown"
    if not working.get("category"):
        working["category"] = "Unknown"

    return {
        "title": working["title"],
        "description": working["description"],
        "content": working["content"],
        "published_at": working["published_at"],
        "source": working["source"],
        "category": working["category"],
        "status": "clean",
    }

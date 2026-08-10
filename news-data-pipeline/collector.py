"""News collection: RSS feeds, a generic JSON API, and simple web crawling.

Ethics note: RSS/API collection is preferred. crawl_news_page() is provided
as a demonstration of BeautifulSoup crawling and must be used sparingly —
respect robots.txt, set a real User-Agent, add delay between requests, and
never hammer a site with bulk requests. See README.md for details.
"""

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import feedparser
import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _headers(cfg: dict[str, Any]) -> dict[str, str]:
    return {"User-Agent": cfg.get("user_agent", "news-data-pipeline/1.0")}


def fetch_from_rss(feed_url: str, source: str, category: str, cfg: dict[str, Any], limit: int | None = None) -> list[dict[str, Any]]:
    """Collect articles from an RSS/Atom feed using feedparser."""
    articles: list[dict[str, Any]] = []
    try:
        response = requests.get(feed_url, headers=_headers(cfg), timeout=cfg.get("http_timeout_seconds", 10))
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
    except requests.exceptions.Timeout:
        logger.error("RSS 요청 타임아웃: %s", feed_url)
        return articles
    except requests.exceptions.ConnectionError:
        logger.error("RSS 연결 오류: %s", feed_url)
        return articles
    except requests.exceptions.HTTPError as exc:
        logger.error("RSS HTTP 오류 (%s): %s", feed_url, exc)
        return articles
    except Exception as exc:  # unexpected parsing/network failure
        logger.error("RSS 수집 중 예상치 못한 오류 (%s): %s", feed_url, exc)
        return articles

    entries = parsed.entries[:limit] if limit else parsed.entries
    for entry in entries:
        articles.append(
            {
                "title": entry.get("title"),
                "description": entry.get("summary"),
                "content": entry.get("summary"),
                "url": entry.get("link"),
                "source": source,
                "category": category,
                "published_at": entry.get("published", entry.get("updated")),
                "collected_at": _now_str(),
                "collection_method": "rss",
            }
        )
    logger.info("RSS에서 %d건 수집: %s", len(articles), feed_url)
    return articles


def fetch_from_api(api_url: str, source: str, category: str, cfg: dict[str, Any], params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Collect articles from a generic JSON news API.

    Expects a JSON response with a top-level "articles" list containing
    title/description/content/url/publishedAt-style fields. Adjust the
    field mapping below to match the specific API you configure.
    """
    articles: list[dict[str, Any]] = []
    try:
        response = requests.get(api_url, headers=_headers(cfg), params=params, timeout=cfg.get("http_timeout_seconds", 10))
        response.raise_for_status()
        payload = response.json()
    except requests.exceptions.Timeout:
        logger.error("API 요청 타임아웃: %s", api_url)
        return articles
    except requests.exceptions.ConnectionError:
        logger.error("API 연결 오류: %s", api_url)
        return articles
    except requests.exceptions.HTTPError as exc:
        logger.error("API HTTP 오류 (%s): %s", api_url, exc)
        return articles
    except json.JSONDecodeError:
        logger.error("API 응답 JSON 파싱 오류: %s", api_url)
        return articles
    except Exception as exc:
        logger.error("API 수집 중 예상치 못한 오류 (%s): %s", api_url, exc)
        return articles

    for item in payload.get("articles", []):
        articles.append(
            {
                "title": item.get("title"),
                "description": item.get("description"),
                "content": item.get("content") or item.get("description"),
                "url": item.get("url"),
                "source": item.get("source", {}).get("name", source) if isinstance(item.get("source"), dict) else source,
                "category": category,
                "published_at": item.get("publishedAt"),
                "collected_at": _now_str(),
                "collection_method": "api",
            }
        )
    logger.info("API에서 %d건 수집: %s", len(articles), api_url)
    return articles


def _robots_allows(url: str, user_agent: str) -> bool:
    """Best-effort robots.txt check. On failure, assume disallowed (fail closed)."""
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch(user_agent, url)
    except Exception as exc:
        logger.warning("robots.txt 확인 실패, 안전하게 크롤링 건너뜀 (%s): %s", url, exc)
        return False


def crawl_news_page(url: str, source: str, category: str, cfg: dict[str, Any]) -> dict[str, Any] | None:
    """Crawl a single news article page with BeautifulSoup.

    Respects robots.txt, uses a descriptive User-Agent, and applies a delay
    before the request. Adjust the CSS selectors below per target site.
    """
    user_agent = cfg.get("user_agent", "news-data-pipeline/1.0")
    if not _robots_allows(url, user_agent):
        logger.warning("robots.txt 정책에 따라 크롤링 금지됨: %s", url)
        return None

    time.sleep(cfg.get("crawl_delay_seconds", 1.5))

    try:
        response = requests.get(url, headers=_headers(cfg), timeout=cfg.get("http_timeout_seconds", 10))
        response.raise_for_status()
    except requests.exceptions.Timeout:
        logger.error("크롤링 요청 타임아웃: %s", url)
        return None
    except requests.exceptions.ConnectionError:
        logger.error("크롤링 연결 오류: %s", url)
        return None
    except requests.exceptions.HTTPError as exc:
        logger.error("크롤링 HTTP 오류 (%s): %s", url, exc)
        return None
    except Exception as exc:
        logger.error("크롤링 중 예상치 못한 오류 (%s): %s", url, exc)
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else None

    paragraphs = soup.find_all("p")
    content = " ".join(p.get_text(strip=True) for p in paragraphs[:20])

    if not title:
        logger.warning("크롤링 결과에 제목이 없어 건너뜀: %s", url)
        return None

    return {
        "title": title,
        "description": content[:200] if content else None,
        "content": content or None,
        "url": url,
        "source": source,
        "category": category,
        "published_at": None,
        "collected_at": _now_str(),
        "collection_method": "crawl",
    }


def collect_all(cfg: dict[str, Any], limit: int | None = None, category_filter: str | None = None, source_filter: str | None = None, method: str = "rss") -> list[dict[str, Any]]:
    """Run collection across all configured sources for the requested method."""
    collected: list[dict[str, Any]] = []

    if method in ("rss", "all"):
        for feed in cfg.get("rss_sources", []):
            if category_filter and feed.get("category") != category_filter:
                continue
            if source_filter and feed.get("name") != source_filter:
                continue
            collected.extend(fetch_from_rss(feed["url"], feed["name"], feed["category"], cfg, limit=limit))

    if method in ("crawl", "all"):
        for target in cfg.get("crawl_targets", []):
            if category_filter and target.get("category") != category_filter:
                continue
            if source_filter and target.get("name") != source_filter:
                continue
            article = crawl_news_page(target["url"], target["name"], target["category"], cfg)
            if article:
                collected.append(article)

    if limit:
        collected = collected[:limit]

    return collected

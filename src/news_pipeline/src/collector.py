"""fetch: RSS/API/크롤링 소스에서 뉴스를 수집해 raw_store에 저장한다."""
import re
import time
from datetime import datetime, timezone

import feedparser
import requests
from bs4 import BeautifulSoup

from src import config_loader, raw_store, ui
from src.logger import get_logger

log = get_logger("collector")

DEFAULT_TIMEOUT = 10
USER_AGENT = "news-pipeline-edu-project/0.1 (learning purpose)"
HN_BASE = "https://hacker-news.firebaseio.com/v0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_via_rss(
    source: dict, limit: int, delay: float = 0.0, timeout: int = DEFAULT_TIMEOUT, progress_cb=None
) -> tuple[list[dict], int]:
    try:
        resp = requests.get(source["url"], timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning(f"[rss] {source['name']} 요청 실패: {e}")
        return [], 1

    feed = feedparser.parse(resp.content)
    records = []
    fail = 0
    for entry in feed.entries[:limit]:
        title = entry.get("title", "")
        if not title:
            fail += 1
            continue
        records.append({
            "source_name": source["name"],
            "method": "rss",
            "category": source.get("category", "종합"),
            "title": title,
            "content": entry.get("summary", title),
            "url": entry.get("link", ""),
            "published_at": entry.get("published", None),
            "collected_at": _now_iso(),
        })
    return records, fail


def fetch_via_api(
    source: dict, limit: int, delay: float = 1.0, timeout: int = DEFAULT_TIMEOUT, progress_cb=None
) -> tuple[list[dict], int]:
    try:
        resp = requests.get(f"{HN_BASE}/topstories.json", timeout=timeout)
        resp.raise_for_status()
        story_ids = resp.json()[:limit]
    except requests.RequestException as e:
        log.warning(f"[api] {source['name']} 목록 요청 실패: {e}")
        return [], limit

    records = []
    fail = 0
    for story_id in story_ids:
        try:
            item_resp = requests.get(f"{HN_BASE}/item/{story_id}.json", timeout=timeout)
            item_resp.raise_for_status()
            item = item_resp.json() or {}
        except requests.RequestException as e:
            log.warning(f"[api] {source['name']} item({story_id}) 요청 실패: {e}")
            item = {}
        finally:
            time.sleep(delay)
            if progress_cb:
                progress_cb()

        title = item.get("title", "")
        if not title:
            fail += 1
            continue
        published_at = None
        if item.get("time"):
            published_at = datetime.fromtimestamp(item["time"], tz=timezone.utc).isoformat()
        records.append({
            "source_name": source["name"],
            "method": "api",
            "category": source.get("category", "IT"),
            "title": title,
            "content": item.get("text") or f"{title} ({item.get('url', '')})",
            "url": item.get("url") or f"https://news.ycombinator.com/item?id={story_id}",
            "published_at": published_at,
            "collected_at": _now_iso(),
        })
    return records, fail


_DATE_RE = re.compile(r"(\d{1,2})월\s*(\d{1,2})일")


def _parse_relative_date(text: str) -> str | None:
    m = _DATE_RE.search(text)
    if not m:
        return None
    month, day = int(m.group(1)), int(m.group(2))
    year = datetime.now().year
    try:
        return datetime(year, month, day, tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def fetch_via_crawl(
    source: dict, limit: int, delay: float = 0.0, timeout: int = DEFAULT_TIMEOUT, progress_cb=None
) -> tuple[list[dict], int]:
    try:
        resp = requests.get(source["url"], timeout=timeout, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
    except requests.RequestException as e:
        log.warning(f"[crawl] {source['name']} 요청 실패: {e}")
        return [], 1

    soup = BeautifulSoup(resp.text, "html.parser")
    content_div = soup.select_one("div.mw-parser-output")
    if not content_div:
        log.warning(f"[crawl] {source['name']} 콘텐츠 영역을 찾지 못했습니다")
        return [], 1

    records = []
    fail = 0
    for li in content_div.find_all("li")[:limit]:
        bold_link = li.select_one("b a")
        if bold_link:
            title = bold_link.get_text(strip=True)
            url = bold_link.get("href", source["url"])
        else:
            first_link = li.find("a")
            title = li.get_text(" ", strip=True)[:80]
            url = first_link.get("href", source["url"]) if first_link else source["url"]

        text = li.get_text(" ", strip=True)
        if not title or not text:
            fail += 1
            continue
        records.append({
            "source_name": source["name"],
            "method": "crawl",
            "category": source.get("category", "종합"),
            "title": title,
            "content": text,
            "url": url,
            "published_at": _parse_relative_date(text),
            "collected_at": _now_iso(),
        })
    return records, fail


METHOD_HANDLERS = {"rss": fetch_via_rss, "api": fetch_via_api, "crawl": fetch_via_crawl}


def run_fetch(source_name: str = "all", limit: int = 20) -> None:
    config = config_loader.load_config()
    sources = config.get("news_sources", [])
    if not sources:
        ui.print_warning("등록된 소스가 없습니다. config add-source 로 먼저 추가하세요.")
        return

    targets = [
        s for s in sources
        if s.get("enabled", True) and (source_name == "all" or s["name"] == source_name)
    ]
    if not targets:
        ui.print_error(f"'{source_name}' 이름의 활성화된 소스를 찾을 수 없습니다.")
        return

    fetch_cfg = config.get("fetch", {})
    delay = fetch_cfg.get("request_delay_sec", 1.0)
    timeout = fetch_cfg.get("timeout_sec", DEFAULT_TIMEOUT)
    result_rows = []

    with ui.progress_bar() as progress:
        task_ids = {}
        for src in targets:
            # api는 아이템별로 개별 요청을 하므로 건수만큼, rss/crawl은 요청 1번이라 1단계로 채운다.
            total = limit if src["method"] == "api" else 1
            label = f"{src['name']} ({src['method']})"
            task_ids[src["name"]] = progress.add_task(label, total=total)

        for src in targets:
            task_id = task_ids[src["name"]]
            handler = METHOD_HANDLERS.get(src["method"])
            if handler is None:
                log.warning(f"알 수 없는 수집 방식: {src['method']}")
                progress.update(task_id, completed=progress.tasks[task_id].total)
                result_rows.append([src["name"], src["method"], 0, 0])
                continue

            if src["method"] == "api":
                records, fail = handler(
                    src, limit, delay, timeout, progress_cb=lambda: progress.advance(task_id)
                )
            else:
                records, fail = handler(src, limit, delay, timeout)
                progress.update(task_id, completed=1)

            for record in records:
                raw_store.append(src["name"], record)
            log.info(
                f"수집 완료: source={src['name']} method={src['method']} "
                f"성공={len(records)}건 실패={fail}건"
            )
            result_rows.append([src["name"], src["method"], len(records), fail])

    ui.print_table("수집 결과", ["소스", "방식", "성공", "실패"], result_rows)
    total_success = sum(r[2] for r in result_rows)
    total_fail = sum(r[3] for r in result_rows)
    ui.print_success(
        f"수집 완료: 성공 {total_success}건, 실패 {total_fail}건 (raw 저장소에 저장됨)"
    )

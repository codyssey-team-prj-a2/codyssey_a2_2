"""clean: raw_store에서 읽어 검증/정규화 후 db.py로 저장한다."""
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

from src import config_loader, db, normalize, raw_store, ui
from src.logger import get_logger

log = get_logger("cleaner")


def _normalize_text(text: str) -> str:
    text = BeautifulSoup(text, "html.parser").get_text(" ")
    return re.sub(r"\s+", " ", text).strip()


def _normalize_date(published_at: str | None, collected_at: str) -> str:
    if published_at:
        for parser in (
            lambda s: parsedate_to_datetime(s),
            lambda s: datetime.fromisoformat(s),
        ):
            try:
                dt = parser(published_at)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                continue
    return collected_at


def run_clean(policy: str | None = None) -> None:
    db.init_db()
    config = config_loader.load_config()
    policy = policy or config.get("fetch", {}).get("duplicate_policy", "skip")
    if policy not in ("skip", "upsert"):
        ui.print_error(f"알 수 없는 중복 정책: {policy}")
        return

    raw_records = raw_store.read_all()
    if not raw_records:
        ui.print_warning("정제할 raw 데이터가 없습니다. 먼저 fetch를 실행하세요.")
        return

    stats = {
        "total": len(raw_records), "invalid": 0,
        "inserted": 0, "updated": 0, "duplicate_skipped": 0,
    }

    with ui.progress_bar() as progress:
        task = progress.add_task("데이터 정제 중", total=len(raw_records))
        for raw in raw_records:
            title = (raw.get("title") or "").strip()
            content = (raw.get("content") or "").strip()
            url = (raw.get("url") or "").strip()
            if not title or not content or not url:
                stats["invalid"] += 1
                progress.advance(task)
                continue

            collected_at = raw.get("collected_at") or datetime.now(timezone.utc).isoformat()
            clean_record = {
                "source_name": raw.get("source_name", ""),
                "method": raw.get("method", ""),
                "category": raw.get("category", "종합"),
                "title": _normalize_text(title),
                "content": _normalize_text(content),
                "url": normalize.normalize_url(url),
                "published_at": _normalize_date(raw.get("published_at"), collected_at),
                "collected_at": collected_at,
                "cleaned_at": datetime.now(timezone.utc).isoformat(),
            }

            existing = db.get_by_url(clean_record["url"])
            if existing:
                if policy == "upsert":
                    db.update_news(existing["id"], clean_record)
                    stats["updated"] += 1
                else:
                    stats["duplicate_skipped"] += 1
            else:
                db.insert_news(clean_record)
                stats["inserted"] += 1
            progress.advance(task)

    log.info(f"정제 완료: policy={policy} {stats}")
    ui.print_table(
        "정제 결과",
        ["항목", "건수"],
        [
            ["raw 전체", stats["total"]],
            ["필수 필드 누락(제외)", stats["invalid"]],
            ["신규 저장", stats["inserted"]],
            ["갱신(upsert)", stats["updated"]],
            ["중복 스킵", stats["duplicate_skipped"]],
        ],
    )
    ui.print_success(f"정제 완료 (정책: {policy})")

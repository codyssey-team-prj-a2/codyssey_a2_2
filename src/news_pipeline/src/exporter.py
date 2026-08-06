"""export: 뉴스 데이터를 CSV/JSONL/Excel로 내보낸다."""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import db, ui
from src.logger import get_logger

log = get_logger("exporter")

BASE_DIR = Path(__file__).resolve().parent.parent
EXPORT_DIR = BASE_DIR / "reports" / "exports"

COLUMNS = [
    "id", "source_name", "method", "category", "title", "content", "url",
    "published_at", "summary", "is_summarized", "sentiment", "sentiment_reason",
]


def run_export(fmt: str, status: str | None = None) -> None:
    db.init_db()
    rows = db.query_news(status=status)
    if not rows:
        ui.print_warning("내보낼 데이터가 없습니다.")
        return

    records = [{col: row[col] for col in COLUMNS} for row in rows]

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = EXPORT_DIR / f"export_{ts}.{'xlsx' if fmt == 'excel' else fmt}"

    if fmt == "csv":
        pd.DataFrame(records).to_csv(out_path, index=False, encoding="utf-8-sig")
    elif fmt == "jsonl":
        with open(out_path, "w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    elif fmt == "excel":
        pd.DataFrame(records).to_excel(out_path, index=False)
    else:
        ui.print_error(f"지원하지 않는 형식입니다: {fmt}")
        return

    log.info(f"내보내기 완료: {out_path} ({len(records)}건)")
    ui.print_success(f"내보내기 완료: {out_path} ({len(records)}건)")


def run_history() -> None:
    """내보낸 파일 목록을 보여준다 (CSV/Excel은 터미널에서 내용 미리보기가 어려워 목록만)."""
    files = sorted(EXPORT_DIR.glob("export_*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        ui.print_warning("아직 내보낸 파일이 없습니다.")
        return
    ui.print_file_table("내보낸 파일 목록", files)

"""export: 뉴스 데이터를 CSV/JSONL/Excel로 내보낸다."""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config_loader, db, ui
from src.logger import get_logger

log = get_logger("exporter")

BASE_DIR = Path(__file__).resolve().parent.parent

COLUMNS = [
    "id", "source_name", "method", "category", "title", "content", "url",
    "published_at", "summary", "is_summarized", "sentiment", "sentiment_reason",
]


def _export_dir() -> Path:
    config = config_loader.load_config()
    return BASE_DIR / config.get("report", {}).get("output_dir", "reports") / "exports"


def run_export(  # noqa: PLR0913 -- export 필터 함수라 옵션 인자가 많은 것이 자연스러움
    fmt: str,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> None:
    db.init_db()
    rows = db.query_news(status=status, date_from=date_from, date_to=date_to)
    if not rows:
        ui.print_warning("내보낼 데이터가 없습니다.")
        return

    records = [{col: row[col] for col in COLUMNS} for row in rows]

    export_dir = _export_dir()
    export_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = export_dir / f"export_{ts}.{'xlsx' if fmt == 'excel' else fmt}"

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
    files = sorted(
        _export_dir().glob("export_*.*"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not files:
        ui.print_warning("아직 내보낸 파일이 없습니다.")
        return
    ui.print_file_table("내보낸 파일 목록", files)

"""Export news data to CSV, JSONL, or Excel."""

import csv
import json
import logging
import sqlite3
from pathlib import Path

import pandas as pd

import database

logger = logging.getLogger(__name__)

EXPORT_COLUMNS = [
    "id", "title", "description", "content", "url", "source", "category",
    "published_at", "collected_at", "collection_method", "status",
    "summary", "sentiment", "created_at", "updated_at",
]


def export_to_csv(articles: list[sqlite3.Row], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        for article in articles:
            writer.writerow({col: article[col] for col in EXPORT_COLUMNS})
    logger.info("CSV로 %d건 내보내기 완료: %s", len(articles), output_path)
    return output_path


def export_to_jsonl(articles: list[sqlite3.Row], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for article in articles:
            row = {col: article[col] for col in EXPORT_COLUMNS}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    logger.info("JSONL로 %d건 내보내기 완료: %s", len(articles), output_path)
    return output_path


def export_to_xlsx(articles: list[sqlite3.Row], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{col: article[col] for col in EXPORT_COLUMNS} for article in articles]
    df = pd.DataFrame(rows, columns=EXPORT_COLUMNS)
    df.to_excel(output_path, index=False, engine="openpyxl")
    logger.info("Excel로 %d건 내보내기 완료: %s", len(articles), output_path)
    return output_path


def export_articles(
    conn: sqlite3.Connection,
    fmt: str,
    output_path: Path,
    status: str | None = None,
    category: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> Path:
    articles = database.fetch_articles(conn, status=status, category=category, start_date=start_date, end_date=end_date)

    if fmt == "csv":
        return export_to_csv(articles, output_path)
    if fmt == "jsonl":
        return export_to_jsonl(articles, output_path)
    if fmt == "xlsx":
        return export_to_xlsx(articles, output_path)
    raise ValueError(f"지원하지 않는 export 형식: {fmt}")

"""Report generation: overview, quality metrics, top-N, AI insights, chart links."""

import logging
import sqlite3
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import database

logger = logging.getLogger(__name__)


def compute_quality_metrics(articles: list[sqlite3.Row]) -> dict[str, float]:
    """Compute basic data-quality metrics over a set of articles."""
    total = len(articles)
    if total == 0:
        return {"completeness": 0.0, "duplicate_rate": 0.0, "summary_success_rate": 0.0, "required_field_rate": 0.0}

    required_fields = ("title", "url", "published_at")
    complete_count = 0
    required_ok_count = 0
    summarized_count = 0
    seen_urls: set[str] = set()
    duplicate_count = 0

    for article in articles:
        row = dict(article)
        if all(row.get(f) not in (None, "") for f in required_fields):
            required_ok_count += 1
        all_fields = ("title", "description", "content", "url", "source", "category", "published_at")
        if all(row.get(f) not in (None, "") for f in all_fields):
            complete_count += 1
        if row.get("status") == "summarized" or row.get("summary"):
            summarized_count += 1
        if row["url"] in seen_urls:
            duplicate_count += 1
        seen_urls.add(row["url"])

    return {
        "completeness": round(complete_count / total * 100, 1),
        "duplicate_rate": round(duplicate_count / total * 100, 1),
        "summary_success_rate": round(summarized_count / total * 100, 1),
        "required_field_rate": round(required_ok_count / total * 100, 1),
    }


def top_keywords(articles: list[sqlite3.Row], top_n: int = 10) -> list[tuple[str, int]]:
    """Very simple keyword frequency counter over titles (Korean/English tokens)."""
    import re

    stopwords = {"the", "a", "an", "of", "to", "in", "on", "and", "for", "is", "it", "이", "그", "저", "것", "수", "등", "및"}
    counter: Counter[str] = Counter()
    for article in articles:
        title = article["title"] or ""
        tokens = re.findall(r"[가-힣]{2,}|[A-Za-z]{2,}", title)
        for token in tokens:
            lowered = token.lower()
            if lowered in stopwords:
                continue
            counter[token] += 1
    return counter.most_common(top_n)


def top_news_by_recency(articles: list[sqlite3.Row], top_n: int = 10) -> list[sqlite3.Row]:
    """Most recently published articles, used as a simple TOP-N news list."""
    sortable = [a for a in articles if a["published_at"]]
    sortable.sort(key=lambda a: a["published_at"], reverse=True)
    return sortable[:top_n]


def category_breakdown(articles: list[sqlite3.Row], top_n: int = 10) -> list[tuple[str, int]]:
    counter = Counter(a["category"] or "Unknown" for a in articles)
    return counter.most_common(top_n)


def build_report_text(
    articles: list[sqlite3.Row],
    start_date: str | None,
    end_date: str | None,
    category: str | None,
    ai_insight: str | None,
    chart_paths: list[Path],
    fmt: str = "md",
) -> str:
    """Assemble the full report as Markdown or plain text."""
    metrics = compute_quality_metrics(articles)
    keywords = top_keywords(articles)
    recent_news = top_news_by_recency(articles)
    categories = category_breakdown(articles)

    is_md = fmt == "md"
    h1 = "# " if is_md else ""
    h2 = "## " if is_md else "- "
    bullet = "- " if is_md else "  * "

    lines: list[str] = []
    lines.append(f"{h1}뉴스 데이터 파이프라인 리포트")
    lines.append(f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    lines.append(f"{h2}데이터 개요")
    lines.append(f"{bullet}분석 기간: {start_date or '전체'} ~ {end_date or '전체'}")
    lines.append(f"{bullet}수집 뉴스 수: {len(articles)}건")
    lines.append(f"{bullet}분석 카테고리: {category or '전체'}")
    lines.append("")

    lines.append(f"{h2}품질 지표")
    lines.append(f"{bullet}데이터 완전성: {metrics['completeness']}%")
    lines.append(f"{bullet}중복률: {metrics['duplicate_rate']}%")
    lines.append(f"{bullet}요약 성공률: {metrics['summary_success_rate']}%")
    lines.append(f"{bullet}필수 필드 충족률: {metrics['required_field_rate']}%")
    lines.append("")

    lines.append(f"{h2}TOP 키워드")
    if keywords:
        for word, count in keywords:
            lines.append(f"{bullet}{word}: {count}회")
    else:
        lines.append(f"{bullet}(데이터 없음)")
    lines.append("")

    lines.append(f"{h2}카테고리별 뉴스 수")
    for cat, count in categories:
        lines.append(f"{bullet}{cat}: {count}건")
    lines.append("")

    lines.append(f"{h2}최신 뉴스 TOP {len(recent_news)}")
    for article in recent_news:
        lines.append(f"{bullet}[{article['published_at']}] {article['title']} ({article['url']})")
    lines.append("")

    lines.append(f"{h2}AI 인사이트 분석")
    lines.append(ai_insight if ai_insight else "(AI 분석 결과 없음 — OPENAI_API_KEY 설정 후 analyze 명령을 실행하세요)")
    lines.append("")

    lines.append(f"{h2}생성된 차트")
    if chart_paths:
        for path in chart_paths:
            lines.append(f"{bullet}{path}")
    else:
        lines.append(f"{bullet}(생성된 차트 없음)")

    return "\n".join(lines)


def generate_report(
    conn: sqlite3.Connection,
    start_date: str | None,
    end_date: str | None,
    category: str | None,
    fmt: str,
    output_path: Path,
    chart_paths: list[Path],
) -> Path:
    """Query articles, build the report text, write it to disk, and return the path."""
    articles = database.fetch_articles(conn, category=category, start_date=start_date, end_date=end_date)
    analysis_row = database.fetch_latest_analysis(conn, start_date=start_date, end_date=end_date, category=category)
    ai_insight = analysis_row["result"] if analysis_row else None

    report_text = build_report_text(articles, start_date, end_date, category, ai_insight, chart_paths, fmt=fmt)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    logger.info("리포트 생성 완료: %s", output_path)
    return output_path

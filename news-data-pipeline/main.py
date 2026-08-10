"""CLI entry point for the news data pipeline.

Usage:
    python main.py fetch --limit 20
    python main.py clean --all
    python main.py summarize --unsummarized
    python main.py analyze --start-date 2026-08-01 --end-date 2026-08-09
    python main.py report --format md
    python main.py export --format csv
    python main.py list --category technology
    python main.py show --id 10
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import config
import database
import cleaner
import collector
import reporter
import exporter
import visualizer

logger = logging.getLogger(__name__)


def cmd_fetch(args: argparse.Namespace) -> None:
    cfg = config.load_config()
    method = args.method or "rss"
    articles = collector.collect_all(
        cfg, limit=args.limit, category_filter=args.category, source_filter=args.source, method=method
    )

    if args.dry_run:
        print(f"[DRY RUN] {len(articles)}건이 수집될 예정입니다 (DB에 저장하지 않음):")
        for article in articles:
            print(f"  - {article['title']} ({article['url']})")
        return

    database.init_db()
    conn = database.get_connection()
    duplicate_policy = cfg.get("duplicate_policy", "skip")
    inserted = updated = skipped = 0
    try:
        for article in articles:
            if not article.get("url"):
                logger.warning("URL이 없는 기사를 건너뜀: %s", article.get("title"))
                continue
            _, outcome = database.save_article(conn, article, duplicate_policy=duplicate_policy)
            if outcome == "inserted":
                inserted += 1
            elif outcome == "updated":
                updated += 1
            else:
                skipped += 1
    finally:
        conn.close()

    logger.info("수집 완료: 신규 %d건, 업데이트 %d건, 건너뜀 %d건", inserted, updated, skipped)
    print(f"수집 완료: 신규 {inserted}건, 업데이트 {updated}건, 건너뜀 {skipped}건")


def cmd_load_sample(args: argparse.Namespace) -> None:
    """Load the bundled sample dataset so the pipeline can run without API keys."""
    cfg = config.load_config()
    sample_path = config.SAMPLE_DIR / "sample_news.json"
    if not sample_path.exists():
        print(f"샘플 데이터 파일을 찾을 수 없습니다: {sample_path}")
        return

    with open(sample_path, "r", encoding="utf-8") as f:
        sample_articles = json.load(f)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    for article in sample_articles:
        article["collected_at"] = now
        article["collection_method"] = "sample"

    database.init_db()
    conn = database.get_connection()
    duplicate_policy = cfg.get("duplicate_policy", "skip")
    inserted = updated = skipped = 0
    try:
        for article in sample_articles:
            _, outcome = database.save_article(conn, article, duplicate_policy=duplicate_policy)
            if outcome == "inserted":
                inserted += 1
            elif outcome == "updated":
                updated += 1
            else:
                skipped += 1
    finally:
        conn.close()

    logger.info("샘플 데이터 로드 완료: 신규 %d건, 업데이트 %d건, 건너뜀 %d건", inserted, updated, skipped)
    print(f"샘플 데이터 로드 완료: 신규 {inserted}건, 업데이트 {updated}건, 건너뜀 {skipped}건")


def cmd_clean(args: argparse.Namespace) -> None:
    cfg = config.load_config()
    database.init_db()
    conn = database.get_connection()
    try:
        if args.id:
            articles = [database.get_article_by_id(conn, args.id)]
            articles = [a for a in articles if a is not None]
        else:
            articles = database.fetch_articles(conn, status="raw")

        cleaned_count = failed_count = 0
        for article in articles:
            cleaned_fields = cleaner.clean_article(dict(article), max_content_length=cfg.get("max_content_length", 5000))
            if cleaned_fields is None:
                database.update_status(conn, article["id"], "failed")
                failed_count += 1
                continue
            database.update_cleaned_fields(conn, article["id"], cleaned_fields)
            cleaned_count += 1

        logger.info("정제 완료: 성공 %d건, 실패 %d건", cleaned_count, failed_count)
        print(f"정제 완료: 성공 {cleaned_count}건, 실패 {failed_count}건")
    finally:
        conn.close()


def _require_openai_client(cfg: dict):
    api_key = config.get_openai_api_key()
    if not api_key:
        print("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일에 키를 설정하세요.")
        logger.error("OPENAI_API_KEY 미설정으로 AI 기능을 실행할 수 없음")
        return None
    import summarizer

    base_url = config.get_openai_base_url()
    return summarizer.get_openai_client(api_key, base_url=base_url)


def cmd_summarize(args: argparse.Namespace) -> None:
    import summarizer

    cfg = config.load_config()
    client = _require_openai_client(cfg)
    if client is None:
        return

    database.init_db()
    conn = database.get_connection()
    try:
        if args.id:
            rows = [database.get_article_by_id(conn, args.id)]
            rows = [r for r in rows if r is not None]
        elif args.all:
            rows = database.fetch_articles(conn, limit=args.limit)
        else:  # default / --unsummarized
            rows = [r for r in database.fetch_articles(conn, limit=args.limit) if not r["summary"]]

        model = cfg.get("openai_model", "gpt-4o-mini")
        success = failed = 0
        for row in rows:
            if row["summary"]:
                continue  # never re-summarize already-summarized news
            summary = summarizer.summarize_text(client, model, row["title"] or "", row["content"] or row["description"] or "")
            if summary is None:
                database.update_status(conn, row["id"], "failed")
                failed += 1
                continue
            database.update_summary(conn, row["id"], summary, status="summarized")
            success += 1

            sentiment = summarizer.analyze_sentiment(client, model, row["title"] or "", summary)
            if sentiment:
                database.update_sentiment(conn, row["id"], sentiment)

        logger.info("요약 완료: 성공 %d건, 실패 %d건", success, failed)
        print(f"요약 완료: 성공 {success}건, 실패 {failed}건")
    finally:
        conn.close()


def cmd_analyze(args: argparse.Namespace) -> None:
    import analyzer

    cfg = config.load_config()
    client = _require_openai_client(cfg)
    if client is None:
        return

    database.init_db()
    conn = database.get_connection()
    try:
        articles = database.fetch_articles(conn, category=args.category, start_date=args.start_date, end_date=args.end_date)
        summaries = [a["summary"] for a in articles if a["summary"]]

        model = cfg.get("openai_model", "gpt-4o-mini")
        result = analyzer.run_insight_analysis(client, model, summaries)
        if result is None:
            print("분석할 요약 데이터가 없거나 API 호출에 실패했습니다.")
            return

        database.save_analysis_result(conn, args.start_date, args.end_date, args.category, "insight", result)
        print("AI 인사이트 분석 완료:\n")
        print(result)
    finally:
        conn.close()


def cmd_report(args: argparse.Namespace) -> None:
    database.init_db()
    conn = database.get_connection()
    try:
        articles = database.fetch_articles(conn, category=args.category, start_date=args.start_date, end_date=args.end_date)

        visualizer.setup_korean_font()
        chart_paths = []
        cat_chart = visualizer.plot_category_distribution(
            [a["category"] or "Unknown" for a in articles], config.CHARTS_DIR / "category_distribution.png"
        )
        if cat_chart:
            chart_paths.append(cat_chart)
        trend_chart = visualizer.plot_daily_trend(
            [a["collected_at"] for a in articles if a["collected_at"]], config.CHARTS_DIR / "daily_collection_trend.png"
        )
        if trend_chart:
            chart_paths.append(trend_chart)
        sentiment_values = [a["sentiment"] for a in articles if a["sentiment"]]
        if sentiment_values:
            sentiment_chart = visualizer.plot_sentiment_distribution(sentiment_values, config.CHARTS_DIR / "sentiment_distribution.png")
            if sentiment_chart:
                chart_paths.append(sentiment_chart)

        fmt = args.format
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = config.REPORTS_DIR / f"report_{timestamp}.{fmt}"
        reporter.generate_report(conn, args.start_date, args.end_date, args.category, fmt, output_path, chart_paths)
        print(f"리포트 생성 완료: {output_path}")
    finally:
        conn.close()


def cmd_export(args: argparse.Namespace) -> None:
    database.init_db()
    conn = database.get_connection()
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ext = args.format
        output_path = config.REPORTS_DIR / f"news_export_{timestamp}.{ext}"
        exporter.export_articles(
            conn, args.format, output_path,
            status=args.status, category=args.category,
            start_date=args.start_date, end_date=args.end_date,
        )
        print(f"내보내기 완료: {output_path}")
    finally:
        conn.close()


def cmd_list(args: argparse.Namespace) -> None:
    database.init_db()
    conn = database.get_connection()
    try:
        offset = (args.page - 1) * args.page_size
        rows = database.fetch_articles(
            conn, category=args.category, start_date=args.date, end_date=args.date,
            keyword=args.keyword, limit=args.page_size, offset=offset,
        )
        if not rows:
            print("조회된 뉴스가 없습니다.")
            return
        for row in rows:
            print(f"[{row['id']}] {row['title']}  ({row['category']}, {row['status']}, {row['published_at']})")
    finally:
        conn.close()


def cmd_show(args: argparse.Namespace) -> None:
    database.init_db()
    conn = database.get_connection()
    try:
        row = database.get_article_by_id(conn, args.id)
        if row is None:
            print(f"id={args.id} 뉴스를 찾을 수 없습니다.")
            return
        for key in row.keys():
            print(f"{key}: {row[key]}")
    finally:
        conn.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="뉴스 데이터 파이프라인 CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_fetch = subparsers.add_parser("fetch", help="뉴스 수집")
    p_fetch.add_argument("--limit", type=int, default=None)
    p_fetch.add_argument("--category", type=str, default=None)
    p_fetch.add_argument("--source", type=str, default=None)
    p_fetch.add_argument("--method", type=str, choices=["rss", "api", "crawl", "all"], default="rss")
    p_fetch.add_argument("--dry-run", action="store_true")
    p_fetch.set_defaults(func=cmd_fetch)

    p_sample = subparsers.add_parser("load-sample", help="API 키 없이 테스트할 수 있는 샘플 뉴스 데이터 로드")
    p_sample.set_defaults(func=cmd_load_sample)

    p_clean = subparsers.add_parser("clean", help="데이터 정제")
    p_clean.add_argument("--all", action="store_true")
    p_clean.add_argument("--id", type=int, default=None)
    p_clean.add_argument("--duplicate-policy", type=str, choices=["skip", "upsert"], default=None)
    p_clean.set_defaults(func=cmd_clean)

    p_summarize = subparsers.add_parser("summarize", help="AI 뉴스 요약")
    p_summarize.add_argument("--all", action="store_true")
    p_summarize.add_argument("--id", type=int, default=None)
    p_summarize.add_argument("--unsummarized", action="store_true")
    p_summarize.add_argument("--limit", type=int, default=None)
    p_summarize.set_defaults(func=cmd_summarize)

    p_analyze = subparsers.add_parser("analyze", help="AI 인사이트 분석")
    p_analyze.add_argument("--start-date", type=str, default=None)
    p_analyze.add_argument("--end-date", type=str, default=None)
    p_analyze.add_argument("--category", type=str, default=None)
    p_analyze.set_defaults(func=cmd_analyze)

    p_report = subparsers.add_parser("report", help="리포트 생성")
    p_report.add_argument("--start-date", type=str, default=None)
    p_report.add_argument("--end-date", type=str, default=None)
    p_report.add_argument("--category", type=str, default=None)
    p_report.add_argument("--format", type=str, choices=["txt", "md"], default="md")
    p_report.set_defaults(func=cmd_report)

    p_export = subparsers.add_parser("export", help="데이터 내보내기")
    p_export.add_argument("--format", type=str, choices=["csv", "jsonl", "xlsx"], required=True)
    p_export.add_argument("--status", type=str, default=None)
    p_export.add_argument("--category", type=str, default=None)
    p_export.add_argument("--start-date", type=str, default=None)
    p_export.add_argument("--end-date", type=str, default=None)
    p_export.set_defaults(func=cmd_export)

    p_list = subparsers.add_parser("list", help="뉴스 목록 조회")
    p_list.add_argument("--category", type=str, default=None)
    p_list.add_argument("--date", type=str, default=None)
    p_list.add_argument("--keyword", type=str, default=None)
    p_list.add_argument("--page", type=int, default=1)
    p_list.add_argument("--page-size", type=int, default=20)
    p_list.set_defaults(func=cmd_list)

    p_show = subparsers.add_parser("show", help="뉴스 상세 조회")
    p_show.add_argument("--id", type=int, required=True)
    p_show.set_defaults(func=cmd_show)

    return parser


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    config.setup_logging()
    config.ensure_directories()
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as exc:
        logger.exception("명령 실행 중 처리되지 않은 오류 발생: %s", exc)
        print(f"오류가 발생했습니다: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()

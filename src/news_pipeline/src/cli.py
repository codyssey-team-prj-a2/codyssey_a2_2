"""argparse 서브커맨드 정의. main.py는 이 모듈의 main()을 호출만 한다."""
import argparse

from src import ui, setup as setup_mod
from src.prompt import Cancelled
from src.logger import get_logger

log = get_logger("cli")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="main.py", description="뉴스 AI 파이프라인 CLI")
    sub = parser.add_subparsers(dest="command")

    config_p = sub.add_parser("config", help="소스/API 키 설정 관리")
    config_sub = config_p.add_subparsers(dest="config_command")
    config_sub.add_parser("set-api-key", help="AI API 키 등록")
    config_sub.add_parser("add-source", help="뉴스 소스 등록")
    config_sub.add_parser("list", help="등록된 소스 목록")
    remove_p = config_sub.add_parser("remove", help="소스 삭제")
    remove_p.add_argument("--name", required=True)

    fetch_p = sub.add_parser("fetch", help="뉴스 수집")
    fetch_p.add_argument("--source", default="all")
    fetch_p.add_argument("--limit", type=int, default=20)

    clean_p = sub.add_parser("clean", help="데이터 정제")
    clean_p.add_argument("--policy", choices=["skip", "upsert"], default=None)

    summarize_p = sub.add_parser("summarize", help="AI 요약")
    target_group = summarize_p.add_mutually_exclusive_group(required=True)
    target_group.add_argument("--all", action="store_true")
    target_group.add_argument("--id", type=int)
    target_group.add_argument("--unsummarized", action="store_true")
    summarize_p.add_argument("--limit", type=int, default=10)
    summarize_p.add_argument("--force", action="store_true")

    analyze_p = sub.add_parser("analyze", help="AI 인사이트 분석")
    analyze_p.add_argument("--date-from", dest="date_from")
    analyze_p.add_argument("--date-to", dest="date_to")
    analyze_p.add_argument("--category")

    report_p = sub.add_parser("report", help="리포트 생성")
    report_p.add_argument("--format", choices=["txt", "md"], default="md")
    report_p.add_argument("--output", default=None)
    report_p.add_argument("--date-from", dest="date_from", default=None)
    report_p.add_argument("--date-to", dest="date_to", default=None)
    report_p.add_argument("--category", default=None)

    export_p = sub.add_parser("export", help="데이터 내보내기")
    export_p.add_argument("--format", choices=["csv", "jsonl", "excel"], required=True)
    export_p.add_argument("--status", default=None)

    list_p = sub.add_parser("list", help="[보너스] 뉴스 목록 조회")
    list_p.add_argument("--category", default=None)
    list_p.add_argument("--date", default=None)
    list_p.add_argument("--keyword", default=None)
    list_p.add_argument("--page", type=int, default=1)
    list_p.add_argument("--page-size", dest="page_size", type=int, default=10)

    show_p = sub.add_parser("show", help="[보너스] 뉴스 상세 조회")
    show_p.add_argument("--id", type=int, required=True)

    browse_p = sub.add_parser("browse", help="[보너스] list+show 통합 대화형 둘러보기")
    browse_p.add_argument("--category", default=None)
    browse_p.add_argument("--date-from", dest="date_from", default=None)
    browse_p.add_argument("--date-to", dest="date_to", default=None)
    browse_p.add_argument("--keyword", default=None)
    browse_p.add_argument("--status", default=None)
    browse_p.add_argument("--sentiment", default=None)
    browse_p.add_argument("--page", type=int, default=1)
    browse_p.add_argument("--page-size", dest="page_size", type=int, default=10)

    sentiment_p = sub.add_parser("sentiment", help="[보너스] AI 감성 분석")
    sentiment_group = sentiment_p.add_mutually_exclusive_group()
    sentiment_group.add_argument("--all", action="store_true")
    sentiment_group.add_argument("--id", type=int)
    sentiment_group.add_argument("--unanalyzed", action="store_true")
    sentiment_p.add_argument("--limit", type=int, default=10)

    return parser


def cmd_config(args) -> None:
    if args.config_command == "set-api-key":
        setup_mod.set_api_key()
    elif args.config_command == "add-source":
        setup_mod.add_source()
    elif args.config_command == "list":
        setup_mod.list_sources()
    elif args.config_command == "remove":
        setup_mod.remove_source(args.name)
    else:
        ui.print_warning("config 서브커맨드를 지정하세요 (set-api-key/add-source/list/remove)")


def cmd_fetch(args) -> None:
    try:
        from src.collector import run_fetch
    except ImportError:
        ui.print_warning("fetch 기능은 아직 구현되지 않았습니다 (Phase 3 예정)")
        return
    run_fetch(source_name=args.source, limit=args.limit)


def cmd_clean(args) -> None:
    try:
        from src.cleaner import run_clean
    except ImportError:
        ui.print_warning("clean 기능은 아직 구현되지 않았습니다 (Phase 4 예정)")
        return
    run_clean(policy=args.policy)


def cmd_summarize(args) -> None:
    try:
        from src.summarizer import run_summarize
    except ImportError:
        ui.print_warning("summarize 기능은 아직 구현되지 않았습니다 (Phase 5 예정)")
        return
    if args.id is not None:
        target, target_id = "id", args.id
    elif args.all:
        target, target_id = "all", None
    else:
        target, target_id = "unsummarized", None
    run_summarize(target=target, target_id=target_id, limit=args.limit, force=args.force)


def cmd_analyze(args) -> None:
    try:
        from src.analyzer import run_analyze
    except ImportError:
        ui.print_warning("analyze 기능은 아직 구현되지 않았습니다 (Phase 6 예정)")
        return
    run_analyze(date_from=args.date_from, date_to=args.date_to, category=args.category)


def cmd_report(args) -> None:
    try:
        from src.reporter import run_report
    except ImportError:
        ui.print_warning("report 기능은 아직 구현되지 않았습니다 (Phase 8 예정)")
        return
    run_report(
        fmt=args.format, output=args.output,
        date_from=args.date_from, date_to=args.date_to, category=args.category,
    )


def cmd_export(args) -> None:
    try:
        from src.exporter import run_export
    except ImportError:
        ui.print_warning("export 기능은 아직 구현되지 않았습니다 (Phase 9 예정)")
        return
    run_export(fmt=args.format, status=args.status)


def cmd_list(args) -> None:
    try:
        from src.viewer import run_list
    except ImportError:
        ui.print_warning("list 기능은 아직 구현되지 않았습니다 (Phase 10 예정)")
        return
    run_list(
        category=args.category,
        date=args.date,
        keyword=args.keyword,
        page=args.page,
        page_size=args.page_size,
    )


def cmd_show(args) -> None:
    try:
        from src.viewer import run_show
    except ImportError:
        ui.print_warning("show 기능은 아직 구현되지 않았습니다 (Phase 10 예정)")
        return
    run_show(news_id=args.id)


def cmd_browse(args) -> None:
    try:
        from src.viewer import run_browse
    except ImportError:
        ui.print_warning("browse 기능은 아직 구현되지 않았습니다")
        return
    run_browse(
        category=args.category, date_from=args.date_from, date_to=args.date_to,
        keyword=args.keyword, status=args.status, sentiment=args.sentiment,
        page=args.page, page_size=args.page_size,
    )


def cmd_sentiment(args) -> None:
    try:
        from src.sentiment import run_sentiment
    except ImportError:
        ui.print_warning("sentiment 기능은 아직 구현되지 않았습니다 (Phase 11 예정)")
        return
    if args.id is not None:
        target, target_id = "id", args.id
    elif args.all:
        target, target_id = "all", None
    else:
        target, target_id = "unanalyzed", None
    run_sentiment(target=target, target_id=target_id, limit=args.limit)


DISPATCH = {
    "config": cmd_config,
    "fetch": cmd_fetch,
    "clean": cmd_clean,
    "summarize": cmd_summarize,
    "analyze": cmd_analyze,
    "report": cmd_report,
    "export": cmd_export,
    "list": cmd_list,
    "show": cmd_show,
    "browse": cmd_browse,
    "sentiment": cmd_sentiment,
}


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return
    handler = DISPATCH.get(args.command)
    if handler is None:
        parser.print_help()
        return
    try:
        handler(args)
    except Cancelled:
        ui.print_warning("취소했습니다.")

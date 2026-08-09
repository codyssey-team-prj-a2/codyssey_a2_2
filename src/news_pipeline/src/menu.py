"""인자 없이 실행했을 때 뜨는 대화형 메인 메뉴.

화살표+숫자로 고르는 메뉴(questionary)를 기본으로 쓰고, 지원하지 않는 터미널에서는
prompt.py가 자동으로 번호 입력 방식으로 대체한다. 로직은 cli.py의 핸들러를 재사용한다.

모든 하위 메뉴는 같은 규칙을 따른다:
- 마지막 항목은 항상 '0. 뒤로가기' (prompt.ask_select가 공통으로 보장)
- 화면 맨 위에 상위(메인) 메뉴 + '메인 메뉴 › OOO' 브레드크럼을 같이 보여준다
- 작업 하나가 끝나도 곧장 메인 메뉴로 돌아가지 않고, 같은 하위 메뉴 안에서
  '다시 실행 / 결과 보기 / 뒤로가기'를 고르게 해서 반복 작업이 쉽도록 한다
"""
from argparse import Namespace

from src import analyzer, cli, config_loader, db, exporter, reporter, prompt, viewer
from src import setup as setup_mod, ui
from src.prompt import BACK, Cancelled
from src.logger import get_logger

log = get_logger("menu")

MAIN_TITLE = "뉴스 AI 파이프라인"

MAIN_CHOICES = [
    ("fetch", "뉴스 수집 (fetch)"),
    ("clean", "데이터 정제 (clean)"),
    ("summarize", "AI 요약 (summarize)"),
    ("analyze", "인사이트 분석 (analyze)"),
    ("report", "리포트 생성 (report)"),
    ("export", "데이터 내보내기 (export)"),
    ("config", "소스/설정 관리 (config)"),
    ("viewer", "뉴스 조회 (browse)"),
    ("sentiment", "감성 분석 (sentiment) [보너스]"),
]


def _dashboard_subtitle() -> str:
    try:
        db.init_db()
        total = db.count_news()
        summarized = db.count_news(status="summarized")
        return f"누적 {total}건 · 요약 {summarized}건"
    except Exception:
        return ""


def _show_banner() -> None:
    ui.console.clear()
    ui.print_banner(MAIN_TITLE, _dashboard_subtitle())


def _show_context(sub_title: str) -> None:
    """하위 메뉴에서도 상위(메인) 메뉴가 같이 보이도록 위에 함께 그린다."""
    _show_banner()
    ref_lines = "\n".join(
        f"[dim]{i}. {label}[/dim]" for i, (_, label) in enumerate(MAIN_CHOICES, start=1)
    )
    ui.print_panel(ref_lines, title="[dim]메인 메뉴[/dim]", style="grey50")
    ui.print_section(f"메인 메뉴 › {sub_title}")


def _pause() -> None:
    try:
        ui.console.input("\n[dim]계속하려면 Enter[/dim] ")
    except KeyboardInterrupt:
        pass


def _select_or_cancel(message: str, choices: list[tuple[str, str]]) -> str:
    value = prompt.ask_select(message, choices)
    if value == BACK:
        raise Cancelled()
    return value


def _pick_category(message: str = "카테고리를 고르세요") -> str | None:
    """DB에 실제로 있는 카테고리 목록을 보여주고 고르게 한다. 없으면 필터 없이 진행."""
    db.init_db()
    categories = db.list_categories()
    if not categories:
        return None
    choice = prompt.ask_select(
        message, [(c, c) for c in categories], back_label="전체(필터 없음)"
    )
    return None if choice == BACK else choice


def _pick_news_id() -> int | None:
    """뉴스 ID 목록을 보여주고 하나를 고르게 한다(취소/목록없음이면 None)."""
    return viewer.pick_id()


def _run_submenu(
    title: str, do_action, show_result=None, result_label: str = "결과 보기"
) -> None:
    """공통 하위 메뉴 루프: 진입 시 액션 1회 실행 -> '다시 실행/결과 보기/뒤로가기' 반복."""
    def _run_once() -> None:
        _show_context(title)
        try:
            do_action()
        except Cancelled:
            ui.print_warning("취소했습니다.")

    _run_once()
    while True:
        opts = [("rerun", "다시 실행")]
        if show_result:
            opts.append(("result", result_label))
        choice = prompt.ask_select("이어서 무엇을 할까요?", opts)
        if choice == BACK:
            return
        if choice == "rerun":
            _run_once()
        elif choice == "result":
            _show_context(f"{title} · {result_label}")
            try:
                show_result()
            except Cancelled:
                pass
            _show_context(title)


# ── 뉴스 수집 ────────────────────────────────────────────────────────────
def _do_fetch() -> None:
    sources = config_loader.load_config().get("news_sources", [])
    choices = [("all", "전체")] + [(s["name"], f"{s['name']} ({s['method']})") for s in sources]
    source = _select_or_cancel("수집할 소스를 고르세요", choices)
    limit = prompt.ask_int("수집 건수", default=20)
    cli.cmd_fetch(Namespace(source=source, limit=limit))


def _menu_fetch() -> None:
    _run_submenu("뉴스 수집 (fetch)", _do_fetch)


# ── 데이터 정제 ──────────────────────────────────────────────────────────
def _do_clean() -> None:
    policy = prompt.ask_text("중복 처리 정책 (skip/upsert, 비우면 config 기본값)", default="")
    cli.cmd_clean(Namespace(policy=policy or None))


def _show_clean_result() -> None:
    cli.cmd_browse(Namespace(
        category=None, date_from=None, date_to=None, keyword=None, status=None, sentiment=None,
        page=1, page_size=10,
    ))


def _menu_clean() -> None:
    _run_submenu("데이터 정제 (clean)", _do_clean, _show_clean_result, "정제된 뉴스 둘러보기")


# ── AI 요약 ──────────────────────────────────────────────────────────────
def _do_summarize() -> None:
    mode = _select_or_cancel(
        "요약 대상을 고르세요",
        [("all", "전체"), ("id", "특정 ID"), ("unsummarized", "미요약분")],
    )
    ns_kwargs = {"all": False, "id": None, "unsummarized": False}
    limit = 10
    if mode == "all":
        ns_kwargs["all"] = True
        limit = prompt.ask_int("최대 건수", default=10)
    elif mode == "id":
        news_id = _pick_news_id()
        if news_id is None:
            raise Cancelled()
        ns_kwargs["id"] = news_id
    else:
        ns_kwargs["unsummarized"] = True
        limit = prompt.ask_int("최대 건수", default=10)
    force = prompt.ask_confirm("이미 요약된 뉴스도 다시 요약할까요?", default=False)
    cli.cmd_summarize(Namespace(limit=limit, force=force, **ns_kwargs))


def _show_summarize_result() -> None:
    cli.cmd_browse(Namespace(
        category=None, date_from=None, date_to=None, keyword=None,
        status="summarized", sentiment=None, page=1, page_size=10,
    ))


def _menu_summarize() -> None:
    _run_submenu(
        "AI 요약 (summarize)", _do_summarize, _show_summarize_result, "요약된 뉴스 둘러보기"
    )


# ── 인사이트 분석 ────────────────────────────────────────────────────────
def _do_analyze() -> None:
    date_from = prompt.ask_text("시작일 (YYYY-MM-DD, 생략 가능)", default="")
    date_to = prompt.ask_text("종료일 (YYYY-MM-DD, 생략 가능)", default="")
    category = _pick_category("카테고리를 고르세요 (생략 가능)")
    cli.cmd_analyze(
        Namespace(date_from=date_from or None, date_to=date_to or None, category=category)
    )


def _menu_analyze() -> None:
    _run_submenu(
        "인사이트 분석 (analyze)", _do_analyze, analyzer.run_history, "이전 분석 결과 보기"
    )


# ── 리포트 생성 ──────────────────────────────────────────────────────────
def _do_report() -> None:
    fmt = _select_or_cancel("리포트 형식을 고르세요", [("md", "md"), ("txt", "txt")])
    date_from = prompt.ask_text("시작일 (YYYY-MM-DD, 생략하면 전체 기간)", default="")
    date_to = prompt.ask_text("종료일 (YYYY-MM-DD, 생략하면 전체 기간)", default="")
    category = _pick_category("카테고리를 고르세요 (생략하면 전체)")
    cli.cmd_report(Namespace(
        format=fmt, output=None,
        date_from=date_from or None, date_to=date_to or None, category=category,
    ))


def _menu_report() -> None:
    _run_submenu(
        "리포트 생성 (report)", _do_report, reporter.run_history, "생성된 리포트 목록 보기"
    )


# ── 데이터 내보내기 ──────────────────────────────────────────────────────
def _do_export() -> None:
    fmt = _select_or_cancel(
        "내보내기 형식을 고르세요", [("csv", "CSV"), ("jsonl", "JSONL"), ("excel", "Excel")]
    )
    status_choice = prompt.ask_select(
        "상태 필터를 고르세요",
        [("summarized", "요약된 것만"), ("unsummarized", "미요약분만")],
        back_label="전체(필터 없음)",
    )
    status = None if status_choice == BACK else status_choice
    date_from = prompt.ask_text("시작일 (YYYY-MM-DD, 생략 가능)", default="")
    date_to = prompt.ask_text("종료일 (YYYY-MM-DD, 생략 가능)", default="")
    cli.cmd_export(Namespace(
        format=fmt, status=status, date_from=date_from or None, date_to=date_to or None
    ))


def _menu_export() -> None:
    _run_submenu(
        "데이터 내보내기 (export)", _do_export, exporter.run_history, "내보낸 파일 목록 보기"
    )


# ── 소스/설정 관리 (자체 반복 메뉴라 별도 구조 유지) ──────────────────────
def _do_remove_source() -> None:
    sources = config_loader.load_config().get("news_sources", [])
    if not sources:
        ui.print_warning("등록된 소스가 없습니다.")
        return
    name = _select_or_cancel(
        "삭제할 소스를 고르세요",
        [(s["name"], f"{s['name']} ({s['method']})") for s in sources],
    )
    setup_mod.remove_source(name)


CONFIG_ACTIONS = {
    "set_key": setup_mod.set_api_key,
    "add_source": setup_mod.add_source,
    "list_sources": setup_mod.list_sources,
    "remove_source": _do_remove_source,
    "set_db_path": setup_mod.set_db_path,
    "set_log": setup_mod.set_log_config,
}


def _menu_config() -> None:
    while True:
        _show_context("소스/설정 관리")
        choice = prompt.ask_select(
            "무엇을 할까요?",
            [
                ("set_key", "AI 플랫폼/모델/API 키 등록"),
                ("add_source", "소스 추가"),
                ("list_sources", "소스 목록"),
                ("remove_source", "소스 삭제"),
                ("set_db_path", "DB 저장 폴더 경로 설정"),
                ("set_log", "로그 폴더 경로/기록 수준 설정"),
            ],
        )
        if choice == BACK:
            return
        try:
            CONFIG_ACTIONS[choice]()
        except Cancelled:
            ui.print_warning("취소했습니다.")
        _pause()


# ── 뉴스 조회 (list+show 통합 browse) ─────────────────────────────────────
def _do_browse() -> None:
    category = _pick_category("카테고리를 고르세요 (생략 가능)")
    date_from = prompt.ask_text("시작일 (YYYY-MM-DD, 생략 가능)", default="")
    date_to = prompt.ask_text("종료일 (YYYY-MM-DD, 생략 가능)", default="")
    keyword = prompt.ask_text("키워드 (생략 가능)", default="")
    cli.cmd_browse(Namespace(
        category=category, date_from=date_from or None, date_to=date_to or None,
        keyword=keyword or None, status=None, sentiment=None, page=1, page_size=10,
    ))


def _menu_viewer() -> None:
    _run_submenu("뉴스 조회 (browse)", _do_browse)


# ── 감성 분석 ────────────────────────────────────────────────────────────
def _do_sentiment() -> None:
    mode = _select_or_cancel(
        "분석 대상을 고르세요",
        [("all", "전체"), ("id", "특정 ID"), ("unanalyzed", "미분석분")],
    )
    ns_kwargs = {"all": False, "id": None, "unanalyzed": False}
    limit = 10
    if mode == "all":
        ns_kwargs["all"] = True
        limit = prompt.ask_int("최대 건수", default=10)
    elif mode == "id":
        news_id = _pick_news_id()
        if news_id is None:
            raise Cancelled()
        ns_kwargs["id"] = news_id
    else:
        ns_kwargs["unanalyzed"] = True
        limit = prompt.ask_int("최대 건수", default=10)
    cli.cmd_sentiment(Namespace(limit=limit, **ns_kwargs))


def _show_sentiment_result() -> None:
    choice = _select_or_cancel(
        "감성 필터를 고르세요",
        [("all", "전체"), ("긍정", "긍정"), ("부정", "부정"), ("중립", "중립")],
    )
    sentiment_filter = None if choice == "all" else choice
    cli.cmd_browse(Namespace(
        category=None, date_from=None, date_to=None, keyword=None,
        status=None, sentiment=sentiment_filter, page=1, page_size=10,
    ))


def _menu_sentiment() -> None:
    _run_submenu(
        "감성 분석 (sentiment)", _do_sentiment, _show_sentiment_result, "감성별 뉴스 둘러보기"
    )


ACTIONS = {
    "fetch": _menu_fetch,
    "clean": _menu_clean,
    "summarize": _menu_summarize,
    "analyze": _menu_analyze,
    "report": _menu_report,
    "export": _menu_export,
    "config": _menu_config,
    "viewer": _menu_viewer,
    "sentiment": _menu_sentiment,
}


def run_menu() -> None:
    while True:
        _show_banner()
        choice = prompt.ask_select("무엇을 하시겠어요?", MAIN_CHOICES, back_label="종료")
        if choice == BACK:
            ui.print_info("종료합니다.")
            return
        action = ACTIONS.get(choice)
        if action:
            try:
                action()
            except Cancelled:
                pass
            except Exception as e:
                log.exception("메뉴 작업 중 오류")
                ui.print_error(f"작업 중 오류가 발생했습니다: {e}")

"""[보너스] list/show: 뉴스 목록 조회(필터+페이지네이션), 상세 조회.

browse(둘러보기)는 DB id 대신 화면에 보이는 순서(1,2,3...)로 상세를 골라볼 수 있는
대화형 전용 기능이다. list/show는 스크립트/자동화용으로 DB id 그대로 남겨둔다.
"""
import math

from src import db, prompt, ui

PAGE_SIZE_DEFAULT = 10


def _format_detail(row) -> str:
    sentiment_line = row["sentiment"] or "(분석 없음)"
    if row["sentiment_reason"]:
        sentiment_line += f" - {row['sentiment_reason']}"
    return (
        f"카테고리: {row['category']}   소스: {row['source_name']} ({row['method']})\n"
        f"발행일: {row['published_at']}\n"
        f"URL: {row['url']}\n\n"
        f"[본문]\n{row['content']}\n\n"
        f"[요약]\n{row['summary'] or '(요약 없음)'}\n\n"
        f"[감성]\n{sentiment_line}"
    )


def run_list(
    category: str | None, date: str | None, keyword: str | None, page: int, page_size: int
) -> None:
    db.init_db()
    date_from = date_to = date if date else None
    total = db.count_news(date_from=date_from, date_to=date_to, category=category, keyword=keyword)
    if total == 0:
        ui.print_warning("조건에 맞는 뉴스가 없습니다.")
        return

    offset = (page - 1) * page_size
    rows = db.query_news(
        date_from=date_from, date_to=date_to, category=category, keyword=keyword,
        limit=page_size, offset=offset,
    )

    table_rows = [
        [
            r["id"], ui.category_badge(r["category"]), r["title"] or "",
            (r["published_at"] or "")[:10], ui.yes_no_badge(bool(r["is_summarized"])),
        ]
        for r in rows
    ]
    ui.print_table("뉴스 목록", ["ID", "카테고리", "제목", "발행일", "요약"], table_rows)

    total_pages = max(math.ceil(total / page_size), 1)
    ui.print_info(f"페이지 {page}/{total_pages} (총 {total}건)")


def run_show(news_id: int) -> None:
    db.init_db()
    row = db.get_by_id(news_id)
    if not row:
        ui.print_error(f"ID {news_id} 뉴스를 찾을 수 없습니다.")
        return
    ui.print_panel(_format_detail(row), title=f"[{row['id']}] {row['title']}")


def _detail_loop(rows: list, idx: int) -> None:
    """상세 화면에서 n(다음 기사)/p(이전 기사)/엔터(뒤로가기)로 이동."""
    while True:
        row = rows[idx]
        ui.print_panel(_format_detail(row), title=f"[{idx + 1}] {row['title']}")
        nav_raw = prompt.ask_text("다음 기사(n) / 이전 기사(p) / 뒤로가기(엔터)", default="")
        nav = nav_raw.strip().lower()
        if not nav:
            return
        if nav == "n":
            if idx < len(rows) - 1:
                idx += 1
            else:
                ui.print_warning("마지막 기사입니다.")
        elif nav == "p":
            if idx > 0:
                idx -= 1
            else:
                ui.print_warning("첫 기사입니다.")
        else:
            ui.print_error("n, p, 또는 엔터를 입력하세요.")


def run_browse(  # noqa: PLR0913 -- 조회 필터 함수라 옵션 인자가 많은 것이 자연스러움
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    keyword: str | None = None,
    status: str | None = None,
    sentiment: str | None = None,
    page: int = 1,
    page_size: int = PAGE_SIZE_DEFAULT,
) -> None:
    """list+show 통합: 화면 번호(1,2,3...)로 바로 상세를 보고, 상세에서 다음/이전으로 이동."""
    db.init_db()
    total = db.count_news(
        date_from=date_from, date_to=date_to, category=category,
        keyword=keyword, status=status, sentiment=sentiment,
    )
    if total == 0:
        ui.print_warning("조건에 맞는 뉴스가 없습니다.")
        return
    total_pages = max(math.ceil(total / page_size), 1)
    page = max(1, min(page, total_pages))

    while True:
        offset = (page - 1) * page_size
        rows = db.query_news(
            date_from=date_from, date_to=date_to, category=category, keyword=keyword,
            status=status, sentiment=sentiment, limit=page_size, offset=offset,
        )
        table_rows = [
            [
                i, ui.category_badge(r["category"]), r["title"] or "",
                (r["published_at"] or "")[:10], ui.yes_no_badge(bool(r["is_summarized"])),
            ]
            for i, r in enumerate(rows, start=1)
        ]
        ui.print_table(
            f"뉴스 목록 (페이지 {page}/{total_pages}, 총 {total}건)",
            ["번호", "카테고리", "제목", "발행일", "요약"],
            table_rows,
        )
        raw = prompt.ask_text(
            "상세히 볼 번호 (n=다음 페이지, p=이전 페이지, 엔터=뒤로가기)", default=""
        ).strip().lower()

        if not raw:
            return
        if raw == "n":
            if page < total_pages:
                page += 1
            else:
                ui.print_warning("마지막 페이지입니다.")
            continue
        if raw == "p":
            if page > 1:
                page -= 1
            else:
                ui.print_warning("첫 페이지입니다.")
            continue
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            _detail_loop(rows, int(raw) - 1)
            continue
        ui.print_error("올바른 번호를 입력하세요.")


def pick_id(category: str | None = None, page_size: int = PAGE_SIZE_DEFAULT) -> int | None:
    """뉴스 ID를 모르는 상태에서, 목록(ID 컬럼 포함)을 보면서 하나를 고르게 한다.

    '특정 ID' 입력이 필요한 곳(summarize/sentiment의 --id 모드)에서 쓴다.
    취소하거나 목록이 없으면 None을 반환한다.
    """
    db.init_db()
    total = db.count_news(category=category)
    if total == 0:
        ui.print_warning("뉴스가 없습니다.")
        return None
    total_pages = max(math.ceil(total / page_size), 1)
    page = 1

    while True:
        offset = (page - 1) * page_size
        rows = db.query_news(
            category=category, order_by=db.ORDER_BY_ID_DESC, limit=page_size, offset=offset
        )
        table_rows = [
            [
                r["id"], ui.category_badge(r["category"]), r["title"] or "",
                (r["published_at"] or "")[:10], ui.yes_no_badge(bool(r["is_summarized"])),
            ]
            for r in rows
        ]
        ui.print_table(
            f"뉴스 목록 - ID 최신순 (페이지 {page}/{total_pages}, 총 {total}건)",
            ["ID", "카테고리", "제목", "발행일", "요약"],
            table_rows,
        )
        raw = prompt.ask_text(
            "선택할 뉴스 ID (n=다음 페이지, p=이전 페이지, 엔터=취소)", default=""
        ).strip().lower()

        if not raw:
            return None
        if raw == "n":
            if page < total_pages:
                page += 1
            else:
                ui.print_warning("마지막 페이지입니다.")
            continue
        if raw == "p":
            if page > 1:
                page -= 1
            else:
                ui.print_warning("첫 페이지입니다.")
            continue
        if raw.isdigit() and any(r["id"] == int(raw) for r in rows):
            return int(raw)
        ui.print_error("목록에 있는 ID를 입력하세요.")

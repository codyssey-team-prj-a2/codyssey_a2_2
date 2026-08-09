"""analyze: 기간/카테고리별 뉴스를 종합해 AI 인사이트(트렌드/키워드/시사점)를 산출한다."""
import json
from datetime import datetime, timedelta

from src import ai_client, db, prompt, ui
from src.logger import get_logger

log = get_logger("analyzer")

DEFAULT_RANGE_DAYS = 7

SYSTEM_PROMPT = (
    "당신은 데이터 분석가입니다. 아래는 특정 기간/카테고리에 수집된 뉴스\n"
    "제목과 요약 목록입니다. 이를 종합해서 다음 JSON 형식으로만 답하세요.\n"
    "다른 텍스트는 절대 포함하지 마세요.\n"
    '{"trends": ["...", "..."], "keywords": ["...", "..."], "implications": "..."}'
)


def _build_user_prompt(rows: list) -> str:
    lines = []
    for i, row in enumerate(rows, start=1):
        text = row["summary"] or row["content"][:120]
        lines.append(f"{i}. ({row['category']}) {row['title']} - {text}")
    return "\n".join(lines)


def _format_analysis_body(trends: list, keywords: list, implications: str) -> str:
    return (
        "[주요 트렌드]\n" + "\n".join(f"- {t}" for t in trends) +
        "\n\n[핵심 키워드]\n" + ", ".join(keywords) +
        "\n\n[시사점]\n" + implications
    )


def run_history(limit: int = 20) -> None:
    """이전 analyze 결과를 화면 번호로 골라서 다시 볼 수 있게 한다."""
    db.init_db()
    rows = db.list_analysis_results(limit=limit)
    if not rows:
        ui.print_warning("이전 분석 결과가 없습니다.")
        return
    table_rows = [
        [i, r["date_from"] or "-", r["date_to"] or "-", r["category"] or "전체", r["created_at"]]
        for i, r in enumerate(rows, start=1)
    ]
    while True:
        ui.print_table(
            "이전 분석 결과", ["번호", "시작일", "종료일", "카테고리", "생성일시"], table_rows
        )
        raw = prompt.ask_text("상세히 볼 번호 (엔터=뒤로가기)", default="").strip()
        if not raw:
            return
        if raw.isdigit() and 1 <= int(raw) <= len(rows):
            r = rows[int(raw) - 1]
            trends = json.loads(r["trends"] or "[]")
            keywords = json.loads(r["keywords"] or "[]")
            body = _format_analysis_body(trends, keywords, r["implications"] or "")
            date_range = f"{r['date_from'] or '전체'} ~ {r['date_to'] or '전체'}"
            ui.print_panel(body, title=f"[{raw}] {date_range}")
        else:
            ui.print_error("올바른 번호를 입력하세요.")


def run_analyze(date_from: str | None, date_to: str | None, category: str | None) -> None:
    if not ai_client.has_api_key():
        ui.print_error("AI API 키가 설정되지 않았습니다. `config set-api-key`로 먼저 등록하세요.")
        return

    # 기간 미지정 시 전체 DB를 스캔하지 않도록 최근 7일로 제한한다.
    if not date_from and not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=DEFAULT_RANGE_DAYS)).strftime("%Y-%m-%d")
        ui.print_info(
            f"기간 미지정 → 최근 {DEFAULT_RANGE_DAYS}일 기본 적용: {date_from} ~ {date_to}"
        )

    db.init_db()
    rows = db.query_news(date_from=date_from, date_to=date_to, category=category)
    if not rows:
        ui.print_warning("조건에 맞는 뉴스가 없습니다.")
        return

    ui.print_info(f"분석 대상: {len(rows)}건")
    user_prompt = _build_user_prompt(rows)

    result = None
    last_error = None
    for attempt in range(1, 3):  # 최초 시도 + 파싱 실패 시 1회 재시도
        try:
            raw = ai_client.generate(SYSTEM_PROMPT, user_prompt, json_output=True)
            result = json.loads(raw)
            break
        except Exception as e:
            last_error = e
            log.warning(f"분석 응답 파싱 실패(시도 {attempt}): {e}")

    if result is None:
        log.error(f"analyze 최종 실패: {last_error}")
        ui.print_error("AI 분석 결과를 해석하지 못했습니다. 잠시 후 다시 시도하세요.")
        return

    trends = result.get("trends", [])
    keywords = result.get("keywords", [])
    implications = result.get("implications", "")

    db.insert_analysis_result(
        date_from, date_to, category,
        json.dumps(trends, ensure_ascii=False),
        json.dumps(keywords, ensure_ascii=False),
        implications,
    )
    log.info(
        f"분석 완료: date_from={date_from} date_to={date_to} "
        f"category={category} 대상={len(rows)}건"
    )

    body = _format_analysis_body(trends, keywords, implications)
    ui.print_panel(body, title="AI 인사이트 분석 결과")
    ui.print_success("분석 완료")

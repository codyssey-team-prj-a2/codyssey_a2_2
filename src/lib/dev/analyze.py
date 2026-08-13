import json
import shlex
import argparse
from datetime import datetime, timedelta

from lib.system import ui
from lib.common import ai_client
from lib.db import sqlite_mgr as db

analyze_parser = argparse.ArgumentParser(prog="analyze", add_help=False)
analyze_parser.add_argument("--date-from", dest="date_from", default=None)
analyze_parser.add_argument("--date-to", dest="date_to", default=None)
analyze_parser.add_argument("--category", default=None)

DEFAULT_RANGE_DAYS = 7

SYSTEM_PROMPT = (
    "당신은 데이터 분석가입니다. 아래는 특정 기간/카테고리에 수집된 뉴스 제목과\n"
    "요약 목록입니다. 이를 종합해서 다음 JSON 형식으로만 답하세요. 다른 텍스트는\n"
    "절대 포함하지 마세요.\n"
    '{"trends": ["...", "..."], "keywords": ["...", "..."], "implications": "..."}'
)


def _is_valid_date(date_str):
    """YYYY-MM-DD 형식인지 검사한다."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _resolve_range(date_from, date_to):
    """기간 미지정 시 최근 DEFAULT_RANGE_DAYS일로 기본값을 채운다."""
    if not date_from and not date_to:
        date_to = datetime.now().strftime("%Y-%m-%d")
        date_from = (datetime.now() - timedelta(days=DEFAULT_RANGE_DAYS)).strftime("%Y-%m-%d")
        print(f"\n{ui.HL}기간 미지정 -> 최근 {DEFAULT_RANGE_DAYS}일 기본 적용: {date_from} ~ {date_to}{ui.FG}")
    return date_from, date_to


def run_analyze_query(date_from=None, date_to=None, category=None):
    """기간/카테고리로 clean_news를 필터링해서 보여준다(AI 인사이트 추출 없이 조회만)."""
    db.initialize_db()
    date_from, date_to = _resolve_range(date_from, date_to)
    rows = db.query_clean_news(date_from=date_from, date_to=date_to, category=category)

    print(f"\n{ui.HL}[ 분석 대상 조회 결과 ]{ui.FG}")
    print(f"  - 조건: 기간 {date_from or '전체'} ~ {date_to or '전체'}, 카테고리 {category or '전체'}")
    print(f"  - 대상: {len(rows)}건")
    for r in rows[:5]:
        print(f"      - [{r['pub_date']}][{r['category']}] {r['title']}")
    if len(rows) > 5:
        print(f"      ... 외 {len(rows) - 5}건")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
    return rows


def _build_user_prompt(rows):
    lines = []
    for i, row in enumerate(rows, start=1):
        text = row.get("ai_summary") or (row.get("content") or "")[:120]
        lines.append(f"{i}. ({row['category']}) {row['title']} - {text}")
    return "\n".join(lines)


def extract_insight(rows):
    """뉴스 목록을 AI에 넘겨 트렌드/키워드/시사점을 JSON으로 추출한다.

    JSON 파싱에 실패하면 한 번 더 재시도하고, 그래도 실패하면 예외를 올린다.
    """
    user_prompt = _build_user_prompt(rows)
    last_error = None
    for attempt in range(1, 3):
        raw = ai_client.generate(SYSTEM_PROMPT, user_prompt, json_output=True)
        try:
            result = json.loads(raw)
            return {
                "trends": result.get("trends", []),
                "keywords": result.get("keywords", []),
                "implications": result.get("implications", ""),
            }
        except (json.JSONDecodeError, AttributeError) as e:
            last_error = e
    raise RuntimeError(f"AI 응답을 JSON으로 해석하지 못했습니다: {last_error}")


def run_analyze(date_from=None, date_to=None, category=None):
    if not ai_client.has_api_key():
        print(f"\n{ui.ERR}AI API 키가 설정되지 않았습니다. 환경 설정(1번)에서 먼저 등록하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    db.initialize_db()
    date_from, date_to = _resolve_range(date_from, date_to)
    rows = db.query_clean_news(date_from=date_from, date_to=date_to, category=category)
    if not rows:
        print(f"\n{ui.ERR}조건에 맞는 뉴스가 없습니다.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    print(f"\n{ui.HL}>> 분석 대상 {len(rows)}건 AI 인사이트 추출 중...{ui.FG}")
    try:
        insight = extract_insight(rows)
    except Exception as e:
        print(f"\n{ui.ERR}[실패] AI 분석 중 오류: {e}{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    db.upsert_ai_insight({
        "target_category": category or "ALL",
        "period_from": date_from,
        "period_to": date_to,
        "main_trend": " / ".join(insight["trends"]) or "(트렌드 없음)",
        "core_keywords": ", ".join(insight["keywords"]),
        "implications": insight["implications"] or "(시사점 없음)",
    })

    print(f"\n{ui.HL}[ AI 인사이트 분석 결과 ]{ui.FG}")
    print(f"  - 대상: {len(rows)}건 (기간 {date_from} ~ {date_to}, 카테고리 {category or '전체'})")
    print(f"  - 주요 트렌드: {', '.join(insight['trends']) or '없음'}")
    print(f"  - 핵심 키워드: {', '.join(insight['keywords']) or '없음'}")
    print(f"  - 시사점: {insight['implications'] or '없음'}")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def _prompt_date(label):
    """날짜 입력 프롬프트. 생략(Enter)이면 None, 취소(q)면 'q'를 반환하고,
    그 외엔 YYYY-MM-DD 형식이 아닐 경우 오류 안내 후 재입력을 받는다."""
    while True:
        val = ui.safe_input(f"▶ {label} 입력 (YYYY-MM-DD, 생략하려면 그냥 Enter) [q:취소]: ")
        if val and val.lower() == 'q':
            return 'q'
        if not val:
            return None
        if not _is_valid_date(val):
            print(f"\n{ui.ERR}[오류] 날짜는 YYYY-MM-DD 형식으로 입력해 주세요 (예: 2026-08-13).{ui.FG}")
            continue
        return val


def _do_analyze_interactive(with_ai=False):
    date_from = _prompt_date("시작일")
    if date_from == 'q':
        return
    date_to = _prompt_date("종료일")
    if date_to == 'q':
        return
    category = ui.safe_input("▶ 카테고리 입력 (생략하려면 그냥 Enter) [q:취소]: ")
    if category and category.lower() == 'q':
        return
    fn = run_analyze if with_ai else run_analyze_query
    fn(date_from=date_from, date_to=date_to, category=(category or None))


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" AI 종합 인사이트 분석 (Analyze) 제어소 ")
        print(f"{ui.FG}  아래 메뉴 번호를 선택하거나, CLI 명령어를 직접 입력하여 실행할 수 있습니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 기간/카테고리로 분석 대상 조회 (조회만, AI 호출 없음)")
        print("  2. AI 인사이트 분석 실행 (트렌드/키워드/시사점 추출, DB 저장)")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  analyze --date-from Y-M-D --date-to Y-M-D [--category C]")
        print("  (입력 예: analyze --date-from 2026-08-01 --date-to 2026-08-07)")

        print("-" * w)

        user_input = input(f"\n{ui.HL}Codyssey/analyze > {ui.FG}").strip()

        if not user_input:
            continue
        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            _do_analyze_interactive()
        elif user_input == '2':
            _do_analyze_interactive(with_ai=True)
        elif user_input.startswith("analyze"):
            run_analyze_cli(user_input)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")


def run_analyze_cli(command_str):
    try:
        args_list = shlex.split(command_str)
        args, unknown = analyze_parser.parse_known_args(args_list[1:])
        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return
        for label, val in (("--date-from", args.date_from), ("--date-to", args.date_to)):
            if val and not _is_valid_date(val):
                print(f"\n{ui.ERR}[오류] {label}는 YYYY-MM-DD 형식으로 입력해 주세요 (예: 2026-08-13).{ui.FG}")
                ui.pause("[Enter]를 눌러 돌아갑니다...")
                return
        run_analyze(date_from=args.date_from, date_to=args.date_to, category=args.category)
    except SystemExit:
        print("\n[오류] 옵션 파싱에 실패했습니다.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")

# src/lib/dev/export.py
import argparse
import csv
import json
import os
import shlex
from datetime import datetime

import pandas as pd

from lib.system import ui, config_mgr, logger_mgr
from lib.common import helpers
from lib.db import sqlite_mgr

# [추가] 모듈 전용 로거 생성
logger = logger_mgr.get_logger(__name__)

EXPORT_FIELDS = [
    "news_id", "source", "category", "title", "content",
    "pub_date", "ai_summary", "is_summarized", "created_at",
]

# CLI 명령어를 코드 내부에서 파싱하기 위한 전용 파서 설정
export_parser = argparse.ArgumentParser(prog="export", add_help=False)
export_parser.add_argument("--format", "-f", type=str, required=True,
                            choices=["csv", "jsonl", "excel"])
export_parser.add_argument("--status", type=str, default="all",
                            choices=["summarized", "all"])
export_parser.add_argument("--date-from", type=str, default=None)
export_parser.add_argument("--date-to", type=str, default=None)


def _exports_dir():
    cfg = config_mgr.load_config()
    exports_dir = cfg.get("export_path", "./exports")
    os.makedirs(exports_dir, exist_ok=True)
    return exports_dir


def _export_filename(fmt):
    ext = {"csv": "csv", "jsonl": "jsonl", "excel": "xlsx"}[fmt]
    return f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"


def export_to_csv(rows, path):
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def export_to_jsonl(rows, path):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def export_to_excel(rows, path):
    df = pd.DataFrame(rows, columns=EXPORT_FIELDS)
    df.to_excel(path, index=False, engine="openpyxl")


_EXPORTERS = {
    "csv": export_to_csv,
    "jsonl": export_to_jsonl,
    "excel": export_to_excel,
}


def run_export(fmt, status="all", date_from=None, date_to=None):
    """clean_news 데이터를 조회해 지정된 포맷(csv/jsonl/excel)의 파일로 저장합니다."""
    rows = sqlite_mgr.get_news_for_export(status, date_from, date_to)

    if not rows:
        # [로그 추가] 내보낼 데이터가 없는 일반적 상황
        logger.info(f"조건(상태: {status}, 기간: {date_from}~{date_to})에 맞는 데이터가 없어 내보내기를 건너뜁니다.")
        print(f"\n{ui.ERR}[안내] 조건에 맞는 데이터가 없어 내보낼 항목이 없습니다.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    filename = _export_filename(fmt)
    path = os.path.join(_exports_dir(), filename)

    try:
        _EXPORTERS[fmt](rows, path)
        # [로그 추가] 파일 생성 성공 기록
        logger.info(f"데이터 내보내기 성공: {len(rows)}건을 {fmt.upper()} 형식으로 저장 완료 ({path})")
        print(f"\n{ui.HL}>> {len(rows)}건이 {fmt.upper()} 형식으로 내보내기 완료되었습니다.{ui.FG}")
        print(f"   저장 경로: {path}")
    except Exception as e:
        # [로그 추가] 디스크 I/O 오류 또는 라이브러리 오류
        logger.error(f"데이터 내보내기({fmt.upper()}) 중 치명적 오류 발생: {e}")
        print(f"\n{ui.ERR}[오류] 내보내기 중 문제가 발생했습니다: {e}{ui.FG}")

    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_export_cli(command_str):
    """'export --format csv --status summarized --date-from 2026-08-01 --date-to 2026-08-07' 형태 처리."""
    try:
        args_list = shlex.split(command_str)
        args, unknown = export_parser.parse_known_args(args_list[1:])

        if unknown:
            logger.warning(f"내보내기 CLI 실행 중 알 수 없는 옵션 감지: {unknown}")
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return

        run_export(args.format, args.status, args.date_from, args.date_to)

    except SystemExit:
        # [로그 추가] 파라미터 누락 등 설정 오류
        logger.warning(f"필수 파라미터 누락 또는 잘못된 포맷 지정으로 실행이 거부됨: {command_str}")
        print("\n[오류] 필수 파라미터가 누락되었거나 값이 올바르지 않습니다. "
              "'--format'은 csv/jsonl/excel 중 하나로 반드시 지정하세요.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
    except Exception as e:
        logger.error(f"내보내기 CLI 파싱 중 알 수 없는 예외 발생: {e}")
        print(f"\n[오류] 명령어 파싱 중 에러 발생: {e}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")


def run_export_interactive():
    print(f"\n{ui.HL}[ 대화형 내보내기 설정 ]{ui.FG}")
    print("안내: 입력을 취소하고 메뉴로 돌아가려면 언제든 'q'를 입력하세요.\n")

    fmt = ui.safe_input("▶ 내보낼 포맷 입력 (csv/jsonl/excel, 필수) [q:취소]: ")
    if not fmt or fmt.lower() == 'q':
        return
    fmt = fmt.strip().lower()
    if fmt not in ("csv", "jsonl", "excel"):
        print(f"\n{ui.ERR}[오류] 지원하지 않는 포맷입니다: {fmt}{ui.FG}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
        return

    print("\n  [옵션 추천] '--status' 파라미터 (미입력 시 기본값 all 적용)")
    status = input("▶ 상태 필터 입력 (summarized/all, 건너뛰려면 Enter) [q:취소]: ")
    if status and status.lower() == 'q':
        return
    status = status.strip().lower() if status and status.strip() else "all"
    if status not in ("summarized", "all"):
        print(f"\n{ui.ERR}[오류] 지원하지 않는 상태 필터입니다: {status}{ui.FG}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
        return

    date_from = input("▶ 조회 시작일 입력 (예: 2026-08-01, 건너뛰려면 Enter) [q:취소]: ")
    if date_from and date_from.lower() == 'q':
        return
    date_to = input("▶ 조회 종료일 입력 (예: 2026-08-07, 건너뛰려면 Enter) [q:취소]: ")
    if date_to and date_to.lower() == 'q':
        return

    run_export(fmt, status,
               date_from.strip() or None if date_from else None,
               date_to.strip() or None if date_to else None)


def show_export_status():
    total = sqlite_mgr.get_clean_news_count()
    summarize = sqlite_mgr.get_summarize_success_rate()
    print(f"\n{ui.HL}[ 현재 내보내기 대상 데이터 상태 ]{ui.FG}")
    print(f"  - clean_news 전체: {total}건")
    print(f"  - 요약 완료(summarized): {summarize['success_count']}건")
    ui.pause("\n[Enter]를 눌러 서브메뉴로 돌아갑니다...")


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" 데이터 내보내기 (Export) 제어소 ")
        print(f"{ui.FG}  clean_news 데이터를 CSV/Excel/JSONL 파일로 내보냅니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 내보내기 실행 (대화형 파라미터 입력)")
        print("  2. 현재 내보내기 대상 데이터 수 확인")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  export --format [csv|jsonl|excel] [--status summarized|all] [--date-from ..] [--date-to ..]")
        print("  (입력 예: export --format csv --status summarized)")

        print("-" * w)
        user_input = input(f"\n{ui.HL}Codyssey/export > {ui.FG}").strip()

        if not user_input:
            continue

        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_export_interactive()
        elif user_input == '2':
            show_export_status()
        elif user_input.startswith("export"):
            run_export_cli(user_input)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")
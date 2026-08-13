# src/lib/dev/list_news.py
import argparse
import shlex

from lib.system import ui
from lib.common import helpers
from lib.db import sqlite_mgr

# CLI 명령어를 코드 내부에서 파싱하기 위한 전용 파서 설정
list_parser = argparse.ArgumentParser(prog="list", add_help=False)
list_parser.add_argument("--page", "-p", type=int, default=1)
list_parser.add_argument("--size", type=int, default=10)
list_parser.add_argument("--category", "-c", type=str, default=None)


def print_news_list(result):
    items = result["items"]
    w = ui.get_width()

    print(f"\n{ui.HL}[ 정제 뉴스 목록 ] (page {result['page']}/{max(result['total_pages'], 1)}, "
          f"전체 {result['total']}건){ui.FG}")
    print("-" * w)

    if not items:
        print("  조건에 맞는 데이터가 없습니다.")
    else:
        for row in items:
            summarized_mark = "✔" if row["is_summarized"] else "-"
            print(f"  [{summarized_mark}] {row['pub_date']}  ({row['category']})  {row['title']}")
            print(f"      news_id: {row['news_id']}")

    print("-" * w)


def run_list(page=1, size=10, category=None):
    result = sqlite_mgr.get_news_list(page, size, category)
    print_news_list(result)
    input("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_list_cli(command_str):
    """'list --page 2 --size 20 --category IT' 형태의 입력을 파싱해 실행합니다."""
    try:
        args_list = shlex.split(command_str)
        args, unknown = list_parser.parse_known_args(args_list[1:])

        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            input("[Enter]를 눌러 돌아갑니다...")
            return

        run_list(args.page, args.size, args.category)

    except SystemExit:
        print("\n[오류] '--page', '--size' 옵션에는 숫자를 입력하세요.")
        input("[Enter]를 눌러 돌아갑니다...")
    except Exception as e:
        print(f"\n[오류] 명령어 파싱 중 에러 발생: {e}")
        input("[Enter]를 눌러 돌아갑니다...")


def run_list_interactive():
    print(f"\n{ui.HL}[ 대화형 목록 조회 설정 ]{ui.FG}")
    print("안내: 모든 항목은 건너뛸 수 있습니다. 취소하려면 'q'를 입력하세요.\n")

    page_input = ui.safe_input("▶ 조회 페이지 번호 입력 (기본 1, 건너뛰려면 Enter) [q:취소]: ")
    if page_input and page_input.lower() == 'q':
        return
    size_input = ui.safe_input("▶ 페이지당 표시 건수 입력 (기본 10, 건너뛰려면 Enter) [q:취소]: ")
    if size_input and size_input.lower() == 'q':
        return
    category = ui.safe_input("▶ 카테고리 필터 입력 (건너뛰려면 Enter) [q:취소]: ")
    if category and category.lower() == 'q':
        return

    try:
        page = int(page_input.strip()) if page_input and page_input.strip() else 1
        size = int(size_input.strip()) if size_input and size_input.strip() else 10
    except ValueError:
        print(f"\n{ui.ERR}[오류] 페이지/건수는 숫자로 입력해야 합니다.{ui.FG}")
        input("[Enter]를 눌러 돌아갑니다...")
        return

    run_list(page, size, category.strip() if category and category.strip() else None)


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" 정제 뉴스 목록 조회 (List) 제어소 ")
        print(f"{ui.FG}  clean_news 데이터를 페이지 단위로 조회합니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 목록 조회 실행 (대화형 파라미터 입력)")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  list [--page 번호] [--size 건수] [--category 카테고리]")
        print("  (입력 예: list --page 1 --size 10 --category IT)")

        print("-" * w)
        user_input = input(f"\n{ui.HL}Codyssey/list > {ui.FG}").strip()

        if not user_input:
            continue

        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_list_interactive()
        elif user_input.startswith("list"):
            run_list_cli(user_input)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            input("다시 시도하려면 [Enter]를 누르세요...")

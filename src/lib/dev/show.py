# src/lib/dev/show.py
import argparse
import shlex
import textwrap

from lib.system import ui
from lib.common import helpers
from lib.db import sqlite_mgr

# CLI 명령어를 코드 내부에서 파싱하기 위한 전용 파서 설정
show_parser = argparse.ArgumentParser(prog="show", add_help=False)
show_parser.add_argument("--id", "-i", type=str, required=True)


def print_news_detail(news):
    w = ui.get_width()
    wrap_width = max(w - 4, 20)

    print(f"\n{ui.HL}[ 뉴스 상세 조회 ]{ui.FG}")
    print("=" * w)
    print(f"  제목      : {news['title']}")
    print(f"  news_id   : {news['news_id']}")
    print(f"  출처      : {news['source']}")
    print(f"  카테고리  : {news['category']}")
    print(f"  발행일    : {news['pub_date']}")
    print(f"  요약 상태 : {'완료' if news['is_summarized'] else '미완료'}")
    print("-" * w)

    print(f"  {ui.HL}[ AI 3줄 요약 ]{ui.FG}")
    if news["ai_summary"]:
        for line in textwrap.wrap(news["ai_summary"], wrap_width):
            print(f"  {line}")
    else:
        print("  (아직 요약되지 않았습니다.)")
    print("-" * w)

    print(f"  {ui.HL}[ 본문 ]{ui.FG}")
    for line in textwrap.wrap(news["content"], wrap_width):
        print(f"  {line}")
    print("=" * w)


def run_show(news_id):
    news = sqlite_mgr.get_news_by_id(news_id)
    if not news:
        print(f"\n{ui.ERR}[안내] news_id '{news_id}'에 해당하는 기사를 찾을 수 없습니다.{ui.FG}")
    else:
        print_news_detail(news)
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_show_cli(command_str):
    """'show --id <news_id>' 형태의 입력을 파싱해 실행합니다."""
    try:
        args_list = shlex.split(command_str)
        args, unknown = show_parser.parse_known_args(args_list[1:])

        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return

        run_show(args.id)

    except SystemExit:
        print("\n[오류] 필수 파라미터가 누락되었습니다. '--id'를 반드시 포함하세요.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
    except Exception as e:
        print(f"\n[오류] 명령어 파싱 중 에러 발생: {e}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")


def run_show_interactive():
    print(f"\n{ui.HL}[ 대화형 상세 조회 설정 ]{ui.FG}")
    print("안내: 입력을 취소하고 메뉴로 돌아가려면 언제든 'q'를 입력하세요.\n")

    news_id = ui.safe_input("▶ 조회할 news_id 입력 (필수) [q:취소]: ")
    if not news_id or news_id.lower() == 'q':
        return

    run_show(news_id.strip())


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" 뉴스 상세 조회 (Show) 제어소 ")
        print(f"{ui.FG}  특정 news_id 기사의 본문/요약을 상세 조회합니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 상세 조회 실행 (대화형 파라미터 입력)")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  show --id [news_id]")
        print("  (입력 예: show --id https://naver.com/news/123)")

        print("-" * w)
        user_input = input(f"\n{ui.HL}Codyssey/show > {ui.FG}").strip()

        if not user_input:
            continue

        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_show_interactive()
        elif user_input.startswith("show"):
            run_show_cli(user_input)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")

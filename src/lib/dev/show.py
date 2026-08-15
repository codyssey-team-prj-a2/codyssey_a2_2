# src/lib/dev/show.py
import argparse
import shlex

from lib.system import ui, logger_mgr
from lib.db import sqlite_mgr

# [추가] 모듈 전용 로거 생성
logger = logger_mgr.get_logger(__name__)

# 상세 조회 CLI 파서 (allow_abbrev=False 로 --n 입력 차단)
show_parser = argparse.ArgumentParser(prog="show", add_help=False, allow_abbrev=False)
show_parser.add_argument("--no", type=int, required=True)


def show_detail(item):
    """선택한 뉴스의 상세 내용을 보여주는 화면 (모든 필드 배치)"""
    ui.clear_screen()
    ui.draw_header(" 뉴스 상세 조회 ")
    
    # 1. 기본 메타 정보
    print(f"{ui.HL} • 번호(Idx) :{ui.FG} {item.get('idx', 'N/A')}")
    print(f"{ui.HL} • 기사 제목 :{ui.FG} {item.get('title', '제목 없음')}")
    print(f"{ui.HL} • 카테고리  :{ui.FG} {item.get('category', '분류 없음')} │ {ui.HL}출처:{ui.FG} {item.get('source', '알 수 없음')}")
    print(f"{ui.HL} • 발행일자  :{ui.FG} {item.get('pub_date', '알 수 없음')} │ {ui.HL}수집/생성:{ui.FG} {item.get('created_at', '알 수 없음')}")
    print(f"{ui.HL} • 요약 상태 :{ui.FG} {'완료' if item.get('is_summarized') else '미완료'}")
    print(f"{ui.HL} • 원본 링크 :{ui.FG} {item.get('news_id', '')}")
    ui.draw_line("─")
    
    # 2. 감성 분석 결과
    sentiment = item.get('sentiment')
    if sentiment:
        print(f"{ui.HL} [ AI 감성 분석 ]{ui.FG} {sentiment}")
        if item.get('sentiment_reason'):
            print(f"   └─ 근거: {item.get('sentiment_reason')}")
        ui.draw_line("─")
        
    # 3. AI 3줄 요약
    if item.get('is_summarized') and item.get('ai_summary'):
        print(f"{ui.HL} [ AI 3줄 요약 ]{ui.FG}")
        print(f"{item.get('ai_summary')}\n")
        ui.draw_line("─")
        
    # 4. 정제된 기사 본문
    print(f"{ui.HL} [ 기사 본문 ]{ui.FG}")
    content = item.get('content', '')
    print(content)
    
    print()
    ui.draw_line("━")


def run_show(target_idx, pause_msg="[Enter]를 눌러 메뉴로 돌아갑니다..."):
    """DB에서 번호로 조회 후 상세 화면 출력"""
    news_item = sqlite_mgr.get_news_by_id(target_idx)
    if news_item:
        # [로그 추가] 성공적인 기사 열람 기록
        logger.info(f"뉴스 상세 조회 수행 (기사 번호: {target_idx})")
        show_detail(news_item)
    else:
        # [로그 추가] 삭제되었거나 없는 번호에 접근 시도
        logger.warning(f"존재하지 않는 뉴스 상세 조회 시도 (기사 번호: {target_idx})")
        print(f"\n{ui.ERR}[안내] 번호 '{target_idx}'에 해당하는 기사를 찾을 수 없습니다.{ui.FG}")
    
    ui.pause(pause_msg)


def run_show_cli(command_str, pause_msg="[Enter]를 눌러 메뉴로 돌아갑니다..."):
    """'show --no 10' 형태의 입력을 파싱해 실행합니다."""
    try:
        args_list = shlex.split(command_str)
        args, unknown = show_parser.parse_known_args(args_list[1:])

        if unknown:
            # [로그 추가] CLI 옵션 알 수 없음
            logger.warning(f"상세 조회 CLI 실행 중 알 수 없는 옵션 감지: {unknown}")
            print(f"\n{ui.ERR}알 수 없는 옵션이 포함되어 있습니다: {unknown}{ui.FG}")
            ui.pause(pause_msg)
            return

        run_show(args.no, pause_msg)

    except SystemExit:
        # [로그 추가] 필수 파라미터(--no) 누락
        logger.warning(f"상세 조회 CLI 필수 파라미터 누락 또는 형식 오류: {command_str}")
        print(f"\n{ui.ERR}'show --no 번호' 형식으로 정확히 입력하세요. (예: show --no 10){ui.FG}")
        ui.pause(pause_msg)
    except Exception as e:
        # [로그 추가] 알 수 없는 구문 파싱 에러
        logger.error(f"상세 조회 CLI 파싱 중 예외 발생: {e}")
        print(f"\n{ui.ERR}[오류] 명령어 파싱 중 에러 발생: {e}{ui.FG}")
        ui.pause(pause_msg)


def run_show_interactive():
    print(f"\n{ui.HL}[ 대화형 상세 조회 설정 ]{ui.FG}")
    print("안내: 입력을 취소하고 메뉴로 돌아가려면 언제든 'C'를 입력하세요.\n")

    no_input = input(f"{ui.FG}▶ 조회할 기사 번호(No) 입력 (필수) [C: 취소] > {ui.HL}").strip()
    if not no_input or no_input.lower() == 'c':
        return

    if no_input.isdigit():
        run_show(int(no_input))
    else:
        # 화면 피드백만 주고 로깅은 스킵 (사용자 오타)
        print(f"\n{ui.ERR}[오류] 기사 번호는 숫자만 입력해 주세요.{ui.FG}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")


def run_menu_show():
    """Show 서브모듈 메인 메뉴 (main.py에서 9번으로 접근)"""
    while True:
        ui.clear_screen()
        ui.draw_header(" 뉴스 상세 조회 (Show) 제어소 ")
        print(f"{ui.FG}  특정 번호(No)의 기사 본문/요약 등 전체 필드를 조회합니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 상세 조회 실행 (번호 입력)")
        print("\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  show --no [번호]")
        print("  (입력 예: show --no 10)")

        ui.draw_line("─")
        user_input = input(f"{ui.rl_color(ui.HL)}입력 (메뉴번호 / CLI명령어 / P: 상위 메뉴로) > {ui.rl_color(ui.FG)}").strip()

        if not user_input:
            continue

        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_show_interactive()
        elif user_input.startswith("show"):
            run_show_cli(user_input)
        else:
            print(f"\n{ui.ERR}올바르지 않은 명령어나 번호입니다.{ui.FG}")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")
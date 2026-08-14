# src/lib/dev/list_news.py
import argparse
import shlex

from lib.system import ui
from lib.db import sqlite_mgr
from lib.dev import show  # 분리된 show 모듈 임포트

# CLI 명령어를 코드 내부에서 파싱하기 위한 전용 파서 설정
list_parser = argparse.ArgumentParser(prog="list", add_help=False, allow_abbrev=False)
list_parser.add_argument("--page", "-p", type=int, default=1)
list_parser.add_argument("--size", "-s", type=int, default=10)
list_parser.add_argument("--category", "-c", type=str, default=None)
list_parser.add_argument("--date", "-d", type=str, default=None)
list_parser.add_argument("--keyword", "-k", type=str, default=None)


def prompt_filters(curr_cat, curr_date, curr_kw):
    """대화형 필터(검색) 조건 설정 프롬프트"""
    ui.draw_line("─")
    print(f"{ui.HL}  [ 검색 조건 설정 ]{ui.FG} (비워두면 기존 값 유지, 'clear' 입력 시 초기화)")
    
    cat = input(f"  ▶ 카테고리 ({curr_cat or '전체'}) > ").strip()
    if cat.lower() == 'clear': curr_cat = None
    elif cat: curr_cat = cat

    dt = input(f"  ▶ 발행일(YYYY-MM-DD) ({curr_date or '전체'}) > ").strip()
    if dt.lower() == 'clear': curr_date = None
    elif dt: curr_date = dt

    kw = input(f"  ▶ 검색 키워드 ({curr_kw or '전체'}) > ").strip()
    if kw.lower() == 'clear': curr_kw = None
    elif kw: curr_kw = kw

    return curr_cat, curr_date, curr_kw


def print_news_board(result, page, size, cat, dt, kw):
    """게시판 UI 형태로 뉴스 목록을 렌더링하고 아이템 리스트를 반환"""
    ui.clear_screen()
    ui.draw_header(" 정제 뉴스 목록 (게시판) ")
    
    filters = []
    if cat: filters.append(f"분류: {cat}")
    if dt: filters.append(f"날짜: {dt}")
    if kw: filters.append(f"키워드: {kw}")
    filter_str = ", ".join(filters) if filters else "전체"
    
    total = result.get('total', 0)
    total_pages = max(result.get('total_pages', 1), 1)
    
    print(f" {ui.HL}• 검색 조건 :{ui.FG} {filter_str}")
    print(f" {ui.HL}• 현재 페이지 :{ui.FG} {page} / {total_pages} (총 {total}건, 페이지당 {size}건)")
    
    ui.draw_line("━")
    
    header = f" {'No':^4} | {'분류':^8} | {'소스':^10} | {'감정':^4} | {'발행일':^10} | {'수집시각':^11} | {'기사 제목'}"
    print(f"{ui.HL}{header}{ui.FG}")
    ui.draw_line("─")
    
    items = result.get("items", [])
    if not items:
        print("  조건에 맞는 뉴스 데이터가 없습니다.")
    else:
        for row in items:
            idx = row.get("idx", "?")
            
            cat_str = ui.pad_text(row.get('category', '미상')[:8], 8, align="center")
            src_str = ui.pad_text(row.get('source', '미상')[:10], 10, align="center")
            
            sent_val = row.get('sentiment')
            sent_str = ui.pad_text(sent_val[:4] if sent_val else "-", 4, align="center")
            
            date_str = ui.pad_text(row.get('pub_date', '')[:10], 10, align="center")
            
            created_raw = row.get('created_at', '')
            created_cut = created_raw[5:16] if len(created_raw) >= 16 else created_raw[:11]
            created_str = ui.pad_text(created_cut, 11, align="center")
            
            title = row.get('title', '')
            
            print(f" {str(idx):>4} | {cat_str} | {src_str} | {sent_str} | {date_str} | {created_str} | {title[:40]}")
            
    ui.draw_line("━")
    return items


def run_board(page=1, size=10, category=None, date=None, keyword=None):
    """게시판 인터랙션 메인 루프 (페이징, 검색, 표시건수 변경, 상세조회 연동)"""
    curr_page = page
    curr_size = size
    curr_cat = category
    curr_date = date
    curr_kw = keyword
    
    # 되돌아올 때 사용할 공통 Pause 메시지
    back_msg = "\n[Enter]를 눌러 게시판 목록으로 돌아갑니다..."
    
    while True:
        try:
            result = sqlite_mgr.get_news_list(
                page=curr_page, size=curr_size, 
                category=curr_cat, date=curr_date, keyword=curr_kw
            )
        except TypeError:
            result = sqlite_mgr.get_news_list(page=curr_page, size=curr_size, category=curr_cat)

        items = print_news_board(result, curr_page, curr_size, curr_cat, curr_date, curr_kw)
        
        print(f" {ui.HL}[명령어]{ui.FG} N: 다음 | P: 이전 | F: 검색 | S: 건수 변경 | Q: 메뉴로")
        print(f" {ui.HL}[조회]{ui.FG}   번호 (또는 show --no 번호) 입력 시 상세조회 (예: 10)")
        
        cmd_raw = input(f"{ui.rl_color(ui.HL)}입력 > {ui.rl_color(ui.FG)}").strip()
        cmd = cmd_raw.lower()
        
        if cmd == 'q':
            break
        elif cmd == 'n':
            if curr_page < max(result.get('total_pages', 1), 1):
                curr_page += 1
            else:
                print(f"\n{ui.ERR}마지막 페이지입니다.{ui.FG}")
                ui.pause()
        elif cmd == 'p':
            if curr_page > 1:
                curr_page -= 1
            else:
                print(f"\n{ui.ERR}첫 페이지입니다.{ui.FG}")
                ui.pause()
        elif cmd == 'f':
            curr_cat, curr_date, curr_kw = prompt_filters(curr_cat, curr_date, curr_kw)
            curr_page = 1  
        elif cmd == 's':
            sz_input = input(f"\n{ui.FG}▶ 페이지당 표시 건수 입력 (현재 {curr_size}건) > {ui.HL}").strip()
            if sz_input:
                try:
                    new_sz = int(sz_input)
                    if new_sz <= 0:
                        print(f"\n{ui.ERR}[안내] 유효하지 않은 입력({new_sz})입니다. 표시 건수를 1로 보정합니다.{ui.FG}")
                        ui.pause()
                        curr_size = 1
                    else:
                        curr_size = new_sz
                    curr_page = 1
                except ValueError:
                    print(f"\n{ui.ERR}[오류] 숫자를 입력해 주세요.{ui.FG}")
                    ui.pause()
                    
        # [분리된 show.py 연동 1] 번호만 입력 시 상세조회 호출
        elif cmd.isdigit():
            target_idx = int(cmd)
            show.run_show(target_idx, pause_msg=back_msg)
                
        # [분리된 show.py 연동 2] CLI show 파서 직접 호출
        elif cmd.startswith('show'):
            show.run_show_cli(cmd_raw, pause_msg=back_msg)
            
        else:
            print(f"\n{ui.ERR}잘못된 명령어입니다.{ui.FG}")
            ui.pause()


def run_list_cli(command_str):
    """'list --page 1 --size 10' 등 입력 시 파싱 후 유효성 검사 및 게시판 모드 진입"""
    try:
        args_list = shlex.split(command_str)
        args, unknown = list_parser.parse_known_args(args_list[1:])

        if unknown:
            print(f"\n{ui.ERR}알 수 없는 옵션이 포함되어 있습니다: {unknown}{ui.FG}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return

        corrected = False
        
        if args.page <= 0:
            print(f"\n{ui.ERR}[안내] 유효하지 않은 페이지 입력({args.page})입니다. 1페이지로 자동 보정합니다.{ui.FG}")
            args.page = 1
            corrected = True
            
        if args.size <= 0:
            print(f"\n{ui.ERR}[안내] 유효하지 않은 표시 건수 입력({args.size})입니다. 1건으로 자동 보정합니다.{ui.FG}")
            args.size = 1
            corrected = True

        if corrected:
            ui.pause("\n[Enter]를 눌러 게시판으로 진입합니다...")

        run_board(page=args.page, size=args.size, category=args.category, 
                  date=args.date, keyword=args.keyword)

    except SystemExit:
        print(f"\n{ui.ERR}[오류] 명령어 형식이 올바르지 않습니다.{ui.FG}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
    except Exception as e:
        print(f"\n{ui.ERR}[오류] 명령어 파싱 중 에러 발생: {e}{ui.FG}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")


def run_menu_show():
    """목록 조회 진입 메인 메뉴"""
    while True:
        ui.clear_screen()
        ui.draw_header(" 정제 뉴스 목록 조회 (List) 제어소 ")
        print(f"{ui.FG}  수집 및 정제된 데이터를 게시판 형태로 탐색하고 필터링합니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 목록 조회 (게시판 모드 열기)")
        print("\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  list [--page 번호] [--size 건수] [--category 카테고리] [--date YYYY-MM-DD] [--keyword 단어]")
        print("  (입력 예: list -p 1 -s 10 -c IT --keyword 애플)")

        ui.draw_line("─")
        user_input = input(f"{ui.rl_color(ui.HL)}입력 (메뉴번호 / CLI명령어 / P: 상위 메뉴로) > {ui.rl_color(ui.FG)}").strip()

        if not user_input:
            continue

        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_board() 
        elif user_input.startswith("list"):
            run_list_cli(user_input)
        else:
            print(f"\n{ui.ERR}올바르지 않은 명령어나 번호입니다.{ui.FG}")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")
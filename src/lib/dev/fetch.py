import shlex
import argparse
from lib.system import ui

# CLI 명령어를 코드 내부에서 파싱하기 위한 전용 파서 설정
fetch_parser = argparse.ArgumentParser(prog="fetch", add_help=False)
fetch_parser.add_argument("--source", type=str, required=True)
fetch_parser.add_argument("--limit", type=str, default="50")

def run_menu_show():
    """
    설명 영역 / 메뉴 영역 / 명령어 입력 영역을 깔끔하게 분리하고,
    번호 선택과 명령어 입력을 동시에 처리하는 메인 루프입니다.
    """
    while True:
        ui.clear_screen()
        w = ui.get_width()
        
        # ==========================================
        # [1] 설명 영역 (가이드라인)
        # ==========================================
        ui.draw_header(" 뉴스 데이터 수집 (Fetch) 제어소 ")
        print(f"{ui.FG}  아래 메뉴 번호를 선택하거나, CLI 명령어를 직접 입력하여 실행할 수 있습니다.\n")
        
        # ==========================================
        # [2] 메뉴 영역
        # ==========================================
        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 뉴스 수집 실행 (대화형 파라미터 입력)")
        print("  2. 현재 수집된 데이터 수 확인")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")
        
        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  fetch --source [소스명] [--limit 숫자]")
        print("  (입력 예: fetch --source naver_it --limit 20)")
        
        print("-" * w)
        
        # ==========================================
        # [3] 명령어 입력 영역 (CLI / TUI 공존 프롬프트)
        # ==========================================
        user_input = input(f"\n{ui.HL}Codyssey/fetch > {ui.FG}").strip()
        
        if not user_input:
            continue
            
        # 3-1. 메뉴 번호 처리 (TUI 모드)
        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_fetch_interactive()
        elif user_input == '2':
            show_data_status()
            
        # 3-2. 명령어 직접 입력 처리 (CLI 모드)
        elif user_input.startswith("fetch"):
            run_fetch_cli(user_input)
            
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            input("다시 시도하려면 [Enter]를 누르세요...")

def run_fetch_cli(command_str):
    """
    사용자가 직접 입력한 'fetch --source naver --limit 20' 문자열을
    shlex로 쪼개서 argparse로 파싱하고 실행하는 함수.
    """
    try:
        # 문자열을 리스트 형태로 쪼갬 (예: ['fetch', '--source', 'naver'])
        args_list = shlex.split(command_str)
        
        # 맨 앞의 'fetch'는 제외하고 파라미터만 파싱
        args, unknown = fetch_parser.parse_known_args(args_list[1:])
        
        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            input("[Enter]를 눌러 돌아갑니다...")
            return
            
        source = args.source
        limit = args.limit
        
        # 실제 실행부 호출
        execute_fetch_logic(source, limit, is_cli=True)
        
    except SystemExit:
        # argparse는 필수 인자가 없으면 SystemExit을 발생시키며 꺼짐.
        # 이를 잡아서 프로그램이 죽지 않고 돌아가게 처리함.
        print("\n[오류] 필수 파라미터가 누락되었습니다. '--source'를 반드시 포함하세요.")
        input("[Enter]를 눌러 돌아갑니다...")
    except Exception as e:
        print(f"\n[오류] 명령어 파싱 중 에러 발생: {e}")
        input("[Enter]를 눌러 돌아갑니다...")

def run_fetch_interactive():
    """
    1번 메뉴를 선택했을 때 대화형으로 입력받는 함수
    """
    print(f"\n{ui.HL}[ 대화형 뉴스 수집 설정 ]{ui.FG}")
    print("안내: 입력을 취소하고 메뉴로 돌아가려면 언제든 'q'를 입력하세요.\n")
    
    source = ui.safe_input("▶ 수집할 소스명 입력 (필수, 예: naver_it) [q:취소]: ")
    if not source or source.lower() == 'q': return
    
    print("\n  [옵션 추천] '--limit' 파라미터 (미입력 시 기본값 50 적용)")
    limit = ui.safe_input("▶ 수집 제한 건수 입력 (건너뛰려면 Enter) [q:취소]: ")
    if limit and limit.lower() == 'q': return
    
    limit_val = limit.strip() if limit.strip() else "50"
    
    # 실제 실행부 호출
    execute_fetch_logic(source, limit_val, is_cli=False)

def execute_fetch_logic(source, limit, is_cli=False):
    """
    대화형(TUI) 방식이든 CLI 직접 입력 방식이든 
    최종적으로 이 함수를 거쳐 동일한 비즈니스 로직을 수행하도록 중앙화.
    """
    print("\n" + "=" * 50)
    mode_text = "[CLI 모드]" if is_cli else "[대화형 모드]"
    print(f"{ui.HL}>> {mode_text} 뉴스 데이터 수집을 시작합니다...{ui.FG}")
    print(f"   (적용된 옵션: source={source}, limit={limit})")
    
    # TODO: 여기에 실제 크롤링 / RSS 파싱 / DB 저장 로직 작성
    print("   [진행] RSS 피드 파싱 중...")
    print("   [진행] 10건 가져오기 완료...")
    
    print(f"\n{ui.HL}>> 수집 작업이 성공적으로 완료되었습니다!{ui.FG}")
    print("=" * 50)
    input("\n[Enter]를 눌러 메뉴로 돌아갑니다...")

def show_data_status():
    print(f"\n{ui.HL}[ 현재 수집 데이터 상태 ]{ui.FG}")
    print("  - 저장소 (raw_data.jsonl): 150 건 보관 중")
    print("  - 최근 수집 일시: 2026-08-11 02:00:00")
    input("\n[Enter]를 눌러 서브메뉴로 돌아갑니다...")
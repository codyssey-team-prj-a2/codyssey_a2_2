# lib/common/helpers.py
from lib.system import ui

def render_submenu_header(title, cli_usage, options_desc):
    """
    2. 서브 메뉴 진입 시 화면을 지우고, CLI 명령어/옵션 안내 레이아웃을 통일성 있게 출력합니다.
    """
    ui.clear_screen()
    ui.draw_header(f" {title} 서브메뉴 ")
    
    w = ui.get_width()
    print("  " + ui.pad_text("[ CLI 직접 실행 방법 ]", w-4))
    print(f"{ui.HL}  $ {cli_usage}{ui.FG}")
    
    if options_desc:
        print("\n  " + ui.pad_text("[ 주요 옵션 설명 ]", w-4))
        for opt in options_desc:
            print(f"  - {opt}")
    
    print("\n" + "-" * (w-2))
    print("  대화형으로 파라미터를 입력하거나, 바로 [Enter]를 눌러 기본값으로 실행할 수 있습니다.")
    print("  (뒤로 돌아가려면 입력창에 'P'를 입력하세요)\n")
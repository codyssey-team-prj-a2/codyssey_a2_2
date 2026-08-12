import os
import shutil
import unicodedata
import atexit

# [Mac 한글 잔상 버그 방지]
try:
    import readline
except ImportError:
    pass

# ==========================================
# ANSI 이스케이프 코드 (PC 통신 테마 + BOLD)
# ==========================================
RESET = "\033[0m"
BOLD = "\033[1m"              # 굵은 글씨 속성 추가

BG = "\033[44m"              # 파란색 배경
FG = BOLD + "\033[97m"       # 굵고 밝은 흰색
HL = BOLD + "\033[93m"       # 굵은 강조 노란색
ERR = BOLD + "\033[91m"      # 굵은 에러 빨간색

def reset_terminal():
    """프로그램 종료 시 터미널 배경색, 글꼴, 색상을 완전히 원래대로 초기화합니다."""
    print(f"{RESET}\033[2J\033[H", end="", flush=True)

# 프로그램이 어떤 이유로든 종료될 때 reset_terminal 함수 자동 실행
atexit.register(reset_terminal)

def get_width():
    """현재 터미널의 가로 폭을 가져옵니다."""
    return shutil.get_terminal_size().columns

def clear_screen():
    """화면을 지우고 파란 배경 + BOLD 스타일을 적용합니다."""
    print(f"{RESET}{BG}{BOLD}\033[2J\033[H", end="", flush=True)

def get_display_width(text):
    """한글/영문 폭 계산"""
    width = 0
    for char in text:
        if unicodedata.east_asian_width(char) in ['W', 'F', 'A']:
            width += 2
        else:
            width += 1
    return width

def pad_text(text, total_width, align="left"):
    current = get_display_width(text)
    padding = total_width - current
    if padding < 0: padding = 0
    if align == "left": return text + (" " * padding)
    elif align == "right": return (" " * padding) + text
    else:
        lp = padding // 2
        rp = padding - lp
        return (" " * lp) + text + (" " * rp)

def draw_line(char="─"):
    """
    유니코드 박스 선문자(─, ━ 등)를 활용하여 
    터미널 가로 폭에 맞는 끊김 없는 단일 실선을 출력합니다.
    """
    width = get_width()
    print(f"{HL}{char * width}{FG}")

def draw_header(title):
    """상단 헤더 박스 (유니코드 ━ 자를 사용하여 매끄럽게 연결)"""
    width = get_width()
    border_line = "━" * (width - 2)
    print(f"{HL}┏{border_line}┓{FG}")
    print(f"{HL}┃{FG}" + pad_text(title, width-2, "center") + f"{HL}┃{FG}")
    print(f"{HL}┗{border_line}┛{FG}")

def safe_input(prompt_text):
    """
    안전한 입력 함수 (입력 라인 바로 위에 실선 구분선 자동 생성)
    """
    draw_line("─")
    while True:
        val = input(f"{FG}{prompt_text}{HL}").strip()
        print(f"{FG}", end="")
        
        if val == "":
            ans = input(f"{HL}  >> 공백이 입력되었습니다. 입력을 중단하시겠습니까? (y/n): {FG}").strip().lower()
            if ans == 'y':
                return None
            continue
        return val
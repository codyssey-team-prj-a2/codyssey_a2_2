import os
import shutil
import unicodedata

# 5. [Mac 한글 버그 해결] readline을 임포트하면 input() 사용 시 
# 백스페이스로 한글(Wide char)을 지울 때 잔상이 남는 버그가 해소됩니다.
try:
    import readline
except ImportError:
    pass

# PC 통신 테마 (파란 배경, 흰색/노란 글씨)
BG = "\033[44m"     # 파란색 배경
FG = "\033[97m"     # 밝은 흰색
HL = "\033[93m"     # 강조(노란색)
ERR = "\033[91m"    # 에러(빨간색 배경/글씨 조합 등 활용)
RESET = "\033[0m"

def get_width():
    """현재 터미널의 가로 폭을 가져옵니다."""
    return shutil.get_terminal_size().columns

def clear_screen():
    """화면을 지우고 전체를 배경색으로 채웁니다."""
    print(f"{RESET}{BG}\033[2J\033[H", end="")

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

def draw_header(title):
    width = get_width()
    print(f"{HL}+{'-'*(width-2)}+{FG}")
    print(f"{HL}|{FG}" + pad_text(title, width-2, "center") + f"{HL}|{FG}")
    print(f"{HL}+{'-'*(width-2)}+{FG}")

def safe_input(prompt_text):
    """
    1-2. 공백 입력 시 중단 여부를 묻는 안전한 입력 함수.
    입력 중단 시 None을 반환합니다.
    """
    while True:
        val = input(f"{FG}{prompt_text}{HL}").strip()
        print(f"{FG}", end="") # 색상 원복
        
        if val == "":
            ans = input(f"{HL}  >> 공백이 입력되었습니다. 입력을 중단하시겠습니까? (y/n): {FG}").strip().lower()
            if ans == 'y':
                return None
            continue
        return val
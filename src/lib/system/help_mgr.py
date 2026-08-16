# src/lib/system/help_mgr.py
"""CLI 서브커맨드별 도움말(Help) 내용을 중앙 집중식으로 관리하고 출력하는 모듈"""

from lib.system import ui

# 전체 서브커맨드별 도움말 레지스트리 (터미널 깨짐 방지형 구조)
_HELP_REGISTRY = {
    "fetch": {
        "title": "뉴스 데이터 수집 (Fetch) CLI 도움말",
        "desc": "등록된 뉴스 소스(RSS, API, 웹 크롤링)로부터 최신 기사를 수집하고,\n        웹 노이즈를 1차 제거한 뒤 Raw 저장소(JSONL)에 적재합니다.",
        "usage": "Codyssey/fetch > fetch --source [소스명|all] [--limit [건수]]",
        "options": [
            {"opt": "--source", "desc": "수집할 뉴스 소스 이름 또는 전체 지정('all')", "req": "필수", "default": "없음"},
            {"opt": "--limit", "desc": "소스별 최대 수집 제한 건수 (양의 정수)", "req": "선택", "default": "20"},
        ],
        "examples": [
            "전체 소스에서 기본 20건 수집:\n      fetch --source all",
            "특정 소스(hackernews_api)에서 10건 수집:\n      fetch --source hackernews_api --limit 10"
        ]
    },
    "clean": {
        "title": "데이터 정제 (Clean) CLI 도움말",
        "desc": "Raw 저장소의 원본 데이터를 검증 및 정제하고, 결측치를 제외한 뒤\n        SQLite 데이터베이스(clean_news 테이블)에 KST 시각으로 저장합니다.",
        "usage": "Codyssey/clean > clean [--policy [skip|upsert]]",
        "options": [
            {"opt": "--policy", "desc": "중복 기사 처리 정책 (skip: 스킵, upsert: 갱신)", "req": "선택", "default": "config 설정값"}
        ],
        "examples": [
            "기본 정책으로 정제 및 저장:\n      clean",
            "중복 기사 갱신 정책 적용:\n      clean --policy upsert"
        ]
    },
    "summarize": {
        "title": "AI 기사 요약 (Summarize) CLI 도움말",
        "desc": "DB에 저장된 정제 기사를 대상으로 AI를 활용하여\n        3줄 요약문을 생성하고 DB에 업데이트합니다.",
        "usage": "Codyssey/summarize > summarize [--unsummarized | --all | --id 뉴스번호] [--limit 건수]",
        "options": [
            {"opt": "--unsummarized", "desc": "미요약된 기사만 대상으로 지정", "req": "선택(택일)", "default": "false"},
            {"opt": "--all", "desc": "전체 기사 대상 (이미 요약된 기사는 스킵)", "req": "선택(택일)", "default": "false"},
            {"opt": "--id", "desc": "특정 기사 번호(No) 또는 뉴스 ID 지정", "req": "선택(택일)", "default": "없음"},
            {"opt": "--limit", "desc": "일괄 요약 시 최대 처리 건수", "req": "선택", "default": "10"}
        ],
        "examples": [
            "미요약 기사 일괄 요약:\n      summarize --unsummarized --limit 20",
            "특정 기사(ID 42) 요약:\n      summarize --id 42"
        ]
    },
    "analyze": {
        "title": "감성/인사이트 분석 (Analyze) CLI 도움말",
        "desc": "지정된 기간 및 카테고리의 뉴스 데이터를 종합하여 AI 인사이트\n        (트렌드, 키워드, 시사점)를 추출하고 DB에 적재합니다.",
        "usage": "Codyssey/analyze > analyze [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD] [--category 분류]",
        "options": [
            {"opt": "--date-from", "desc": "분석 시작일 (YYYY-MM-DD)", "req": "선택", "default": "최근 7일 전"},
            {"opt": "--date-to", "desc": "분석 종료일 (YYYY-MM-DD)", "req": "선택", "default": "오늘 날짜"},
            {"opt": "--category", "desc": "분석 대상 카테고리 필터", "req": "선택", "default": "전체 (ALL)"}
        ],
        "examples": [
            "특정 기간 종합 인사이트 분석:\n      analyze --date-from 2026-08-01 --date-to 2026-08-07",
            "특정 카테고리(IT) 분석:\n      analyze --category IT"
        ]
    },
    "sentiment": {
        "title": "AI 감성 분석 (Sentiment) CLI 도움말",
        "desc": "정제된 기사의 제목과 요약을 분석하여 긍정/부정/중립 감정 및\n        그 근거를 추출하여 데이터베이스에 기록합니다.",
        "usage": "Codyssey/sentiment > sentiment [--unanalyzed | --all] [--id 뉴스ID] [--limit 건수]",
        "options": [
            {"opt": "--unanalyzed", "desc": "미분석 기사만 대상으로 지정 (-u)", "req": "선택(택일)", "default": "false"},
            {"opt": "--all", "desc": "전체 기사 대상 감성 분석 (-a)", "req": "선택(택일)", "default": "false"},
            {"opt": "--id", "desc": "특정 뉴스 ID 지정 (-i)", "req": "선택(택일)", "default": "없음"},
            {"opt": "--limit", "desc": "처리 최대 건수 (-l)", "req": "선택", "default": "10"}
        ],
        "examples": [
            "미분석 기사 감성 분석:\n      sentiment --unanalyzed --limit 20",
            "전체 기사 감성 분석:\n      sentiment --all"
        ]
    },
    "report": {
        "title": "인사이트 리포트 생성 (Report) CLI 도움말",
        "desc": "품질 지표(정제 통과율, 요약 성공률) 및 TOP N 집계를 바탕으로\n        종합 리포트를 생성하거나 시각화 차트를 출력합니다.",
        "usage": "Codyssey/report > report [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD] [--format console|txt|md]",
        "options": [
            {"opt": "--date-from", "desc": "집계 시작일 (YYYY-MM-DD)", "req": "선택", "default": "전체 기간"},
            {"opt": "--date-to", "desc": "집계 종료일 (YYYY-MM-DD)", "req": "선택", "default": "전체 기간"},
            {"opt": "--format (-f)", "desc": "출력 형식 (console, txt, md 중 선택)", "req": "선택", "default": "console"}
        ],
        "examples": [
            "마크다운 형식의 종합 리포트 생성:\n      report --format md --date-from 2026-08-01 --date-to 2026-08-07"
        ]
    },
    "export": {
        "title": "데이터 내보내기 (Export) CLI 도움말",
        "desc": "DB에 적재된 정제 및 분석된 데이터를 CSV, Excel, JSONL\n        포맷의 파일로 변환하여 지정된 경로에 내보냅니다.",
        "usage": "Codyssey/export > export --format [csv|jsonl|excel] [--status summarized|all] [--date-from ..] [--date-to ..]",
        "options": [
            {"opt": "--format (-f)", "desc": "파일 포맷 (csv, jsonl, excel 중 선택)", "req": "필수", "default": "없음"},
            {"opt": "--status", "desc": "상태 필터 (summarized: 요약완료, all: 전체)", "req": "선택", "default": "all"},
            {"opt": "--date-from", "desc": "조회 시작일 (YYYY-MM-DD)", "req": "선택", "default": "전체 기간"},
            {"opt": "--date-to", "desc": "조회 종료일 (YYYY-MM-DD)", "req": "선택", "default": "전체 기간"}
        ],
        "examples": [
            "요약된 기사만 CSV 파일로 내보내기:\n      export --format csv --status summarized",
            "엑셀 포맷으로 전체 내보내기:\n      export --format excel"
        ]
    },
    "list": {
        "title": "뉴스 목록 조회 (List) CLI 도움말",
        "desc": "데이터베이스에 적재된 뉴스 기사 목록을 게시판 형태로 탐색하고,\n        페이지, 카테고리, 날짜, 키워드 조건으로 필터링합니다.",
        "usage": "Codyssey/list > list [--page 번호] [--size 건수] [--category 분류] [--date 날짜] [--keyword 단어]",
        "options": [
            {"opt": "--page (-p)", "desc": "조회할 페이지 번호", "req": "선택", "default": "1"},
            {"opt": "--size (-s)", "desc": "페이지당 표시할 기사 건수", "req": "선택", "default": "10"},
            {"opt": "--category (-c)", "desc": "카테고리 필터 명칭", "req": "선택", "default": "전체"},
            {"opt": "--date (-d)", "desc": "발행일 필터 (YYYY-MM-DD)", "req": "선택", "default": "전체"},
            {"opt": "--keyword (-k)", "desc": "검색 키워드", "req": "선택", "default": "전체"}
        ],
        "examples": [
            "1페이지, 10건씩 조회 및 IT 카테고리 필터:\n      list -p 1 -s 10 -c IT --keyword 애플"
        ]
    },
    "show": {
        "title": "기사 상세 조회 (Show) CLI 도움말",
        "desc": "rowId(No)를 지정하여 본문, 요약, 감성 분석 결과 등\n    모든 상세 필드를 화면에 출력합니다.\n    기사ID 사용하기에 ID값이 너무 길어서 편의성을 위해 rowId 사용",
        "usage": "Codyssey/show > show --no [db rowId]",
        "options": [
            {"opt": "--no", "desc": "조회할 기사의 고유 번호 (DB Row ID)", "req": "필수", "default": "없음"}
        ],
        "examples": [
            "10번 기사 상세 조회:\n      show --no 10"
        ]
    }
}

def show_help(command_name):
    """지정된 명령어의 도움말을 터미널 환경에서 절대 깨지지 않는 카드 리스트 형태로 출력한다."""
    data = _HELP_REGISTRY.get(command_name)
    if not data:
        print(f"\n{ui.ERR}'{command_name}'에 대한 도움말이 존재하지 않습니다.{ui.FG}")
        return

    ui.clear_screen()
    ui.draw_header(f" {data['title']} ")
    
    print(f"\n{ui.HL}  [ 설명 ]{ui.FG}")
    print(f"    {data['desc']}")
    
    print(f"\n{ui.HL}  [ 사용법 ]{ui.FG}")
    print(f"    {ui.FG}{data['usage']}{ui.FG}")
    
    print(f"\n{ui.HL}  [ 옵션 상세 정보 ]{ui.FG}")
    if data["options"]:
        for idx, opt in enumerate(data["options"], 1):
            req_badge = f"[{opt['req']}]"
            print(f"    {idx}. {ui.HL}{opt['opt']}{ui.FG}  {req_badge}")
            print(f"       • 설명   : {opt['desc']}")
            print(f"       • 기본값 : {opt['default']}")
    else:
        print(f"    (사용 가능한 추가 옵션이 없습니다)")
    
    print(f"\n{ui.HL}  [ 실행 예시 ]{ui.FG}")
    for ex in data["examples"]:
        print(f"    • {ex}")
        
    ui.draw_line("━")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
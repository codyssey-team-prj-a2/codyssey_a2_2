# automation.py
"""cron/작업 스케줄러 같은 비대화형(터미널 없는) 환경에서 서브커맨드를 바로
실행하기 위한 진입점.

`main.py`는 항상 대화형 메인 메뉴(run_tui)로 진입하는 구조를 그대로 유지한다
(main.py/setup.py는 건드리지 않기로 한 팀 합의 때문 — FR-05-03 정기 실행
스케줄링 가이드는 documentation/result/7.정기실행_스케줄링_가이드.md 참고).
그래서 main.py는 한 글자도 손대지 않고, 이 파일을 별도의 비대화형 진입점으로
추가했다.

사용법: `python3 automation.py <서브커맨드> [옵션...]`
예: `python3 automation.py fetch --source all --limit 20`
"""
import sys

# [수정] ui 모듈 임포트 추가
from lib.system import config_mgr, logger_mgr, ui
from lib.dev import analyze, clean, export, fetch, list_news, report, sentiment, show, summarize

# [수정] 스케줄러 환경에서 파일로 로그를 남길 때 ANSI 색상 코드가 들어가
# 텍스트가 깨지거나 하얗게 보이는 현상을 막기 위해 색상 코드를 무력화(Plain Text)합니다.
ui.FG = ""
ui.HL = ""
ui.ERR = ""
if hasattr(ui, "rl_color"):
    ui.rl_color = lambda x: ""

# [추가] 백그라운드 실행을 위한 전역 로거 초기화 및 생성
logger_mgr.init_logger()
logger = logger_mgr.get_logger(__name__)

# [비대화형 CLI 라우터 맵] 각 모듈의 대화형 메뉴가 인식하는 것과 동일한
# 서브커맨드 키워드를 그대로 사용한다(예: list_news.py -> "list").
CLI_HANDLERS = {
    'fetch': fetch.run_fetch_cli,
    'clean': clean.run_clean_cli,
    'summarize': summarize.run_summarize_cli,
    'analyze': analyze.run_analyze_cli,
    'report': report.run_report_cli,
    'export': export.run_export_cli,
    'list': list_news.run_list_cli,
    'show': show.run_show_cli,
    'sentiment': sentiment.run_sentiment_cli,
}


def run_cli(argv):
    """`python automation.py <서브커맨드> [옵션...]` 형태의 비대화형 실행."""
    if not argv:
        # [로그 추가] 스케줄러 설정 실수로 명령어가 누락된 치명적 상황
        logger.error("서브커맨드 미지정으로 자동화 모드 실행에 실패했습니다.")
        print(f"[오류] 서브커맨드를 지정하세요 (가능한 값: {', '.join(CLI_HANDLERS)})")
        sys.exit(1)

    subcommand = argv[0]
    handler = CLI_HANDLERS.get(subcommand)
    if handler is None:
        # [로그 추가] 오타 또는 존재하지 않는 명령어 실행 시도
        logger.error(f"지원하지 않는 서브커맨드('{subcommand}') 실행 시도로 종료되었습니다.")
        print(f"[오류] 지원하지 않는 서브커맨드입니다: {subcommand} "
              f"(가능한 값: {', '.join(CLI_HANDLERS)})")
        sys.exit(1)

    cnt, total = config_mgr.get_setup_progress()
    if cnt != total:
        # [로그 추가] 환경설정이 덜 끝났는데 스케줄러가 돌아버린 경우 (주의 필요)
        logger.warning(f"환경설정 미완료({cnt}/{total}) 상태로 스케줄러가 트리거되어 실행이 차단되었습니다.")
        print(f"[오류] 환경설정이 완료되지 않았습니다 ({cnt}/{total}). "
              "main.py 대화형 메뉴 1번(환경 설정)을 먼저 완료하세요.")
        sys.exit(1)

    # [로그 추가] 정상적인 백그라운드 작업 시작 알림
    logger.info(f"스케줄러(자동화) 모드로 '{subcommand}' 작업을 시작합니다. (파라미터: {argv})")
    handler(" ".join(argv))


if __name__ == "__main__":
    run_cli(sys.argv[1:])
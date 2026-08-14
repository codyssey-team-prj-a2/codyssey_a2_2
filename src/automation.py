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

from lib.dev import analyze, clean, export, fetch, list_news, report, sentiment, show, summarize
from lib.system import config_mgr

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
        print(f"[오류] 서브커맨드를 지정하세요 (가능한 값: {', '.join(CLI_HANDLERS)})")
        sys.exit(1)

    subcommand = argv[0]
    handler = CLI_HANDLERS.get(subcommand)
    if handler is None:
        print(f"[오류] 지원하지 않는 서브커맨드입니다: {subcommand} "
              f"(가능한 값: {', '.join(CLI_HANDLERS)})")
        sys.exit(1)

    cnt, total = config_mgr.get_setup_progress()
    if cnt != total:
        print(f"[오류] 환경설정이 완료되지 않았습니다 ({cnt}/{total}). "
              "main.py 대화형 메뉴 1번(환경 설정)을 먼저 완료하세요.")
        sys.exit(1)

    handler(" ".join(argv))


if __name__ == "__main__":
    run_cli(sys.argv[1:])

# src/lib/dev/summarize.py
import shlex
import argparse

from lib.system import ui, logger_mgr
from lib.common import ai_client
from lib.db import sqlite_mgr as db

# [추가] 모듈 전용 로거 생성
logger = logger_mgr.get_logger(__name__)

summarize_parser = argparse.ArgumentParser(prog="summarize", add_help=False)
summarize_parser.add_argument("--unsummarized", action="store_true")
summarize_parser.add_argument("--limit", type=int, default=10)

SYSTEM_PROMPT = (
    "당신은 뉴스 에디터입니다. 아래 뉴스 본문을 읽고 핵심만 한국어로 3문장 이내, "
    "150자 내외로 요약하세요. 숫자·고유명사는 정확히 유지하고, "
    "요약 외의 의견이나 부가 설명은 절대 추가하지 마세요."
)


def summarize_one(title, content):
    """기사 제목/본문을 받아 AI로 3줄 요약을 생성한다."""
    user_prompt = f"제목: {title}\n본문: {content}"
    return ai_client.generate(SYSTEM_PROMPT, user_prompt).strip()


def run_summarize_preview():
    """API 연동 확인용: 기사 하나를 직접 입력받아 요약 결과만 보여준다(아직 DB 반영 없음)."""
    if not ai_client.has_api_key():
        # [로그 추가] 설정 누락 에러
        logger.error("AI API 키 미설정으로 요약 미리보기를 실행할 수 없습니다.")
        print(f"\n{ui.ERR}AI API 키가 설정되지 않았습니다. 환경 설정(1번)에서 먼저 등록하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    title = ui.safe_input("▶ 요약할 기사 제목 입력 [q:취소]: ")
    if not title or title.lower() == 'q':
        return
    content = ui.safe_input("▶ 요약할 기사 본문 입력 [q:취소]: ")
    if not content or content.lower() == 'q':
        return

    print(f"\n{ui.HL}>> AI 요약 중...{ui.FG}")
    try:
        summary = summarize_one(title, content)
    except Exception as e:
        # [로그 추가] 테스트 과정 중 발생한 AI 통신 오류
        logger.error(f"AI 요약 미리보기 중 통신/생성 오류 발생: {e}")
        print(f"\n{ui.ERR}[실패] AI 요약 중 오류: {e}{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    print(f"\n{ui.HL}[ 요약 결과 ]{ui.FG}")
    print(f"  {summary}")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_summarize_unsummarized(limit=10):
    """is_summarized=0인 기사를 최대 limit건 가져와 AI 요약하고 DB에 반영한다."""
    if not ai_client.has_api_key():
        # [로그 추가] 백그라운드 등에서 인증 없이 파이프라인이 돌았을 때의 치명적 에러
        logger.error("AI API 키 미설정으로 일괄 요약 파이프라인이 중단되었습니다.")
        print(f"\n{ui.ERR}AI API 키가 설정되지 않았습니다. 환경 설정(1번)에서 먼저 등록하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    db.initialize_db()
    rows = db.get_unsummarized_news(limit=limit)
    if not rows:
        # [로그 추가] 대기열이 비어있는 일반적인(정상적인) 상황
        logger.info("대기 중인 미요약 기사가 없어 AI 3줄 요약 작업을 건너뜁니다.")
        print(f"\n{ui.HL}요약할 미요약 기사가 없습니다.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    # [로그 추가] 파이프라인 시작
    logger.info(f"AI 3줄 요약 파이프라인 시작 (대상: {len(rows)}건)")
    print(f"\n{ui.HL}>> 미요약 기사 {len(rows)}건 AI 요약 시작...{ui.FG}")
    success, failed = 0, 0
    for row in rows:
        try:
            summary = summarize_one(row["title"], row["content"])
            db.update_ai_summary(row["news_id"], summary)
            print(f"   [완료] {row['title']}")
            success += 1
        except Exception as e:
            # [로그 추가] 개별 기사의 AI 통신 실패 (Quota 제한, 타임아웃, 정책 위반 등)
            logger.error(f"[{row['news_id']}] AI 요약 생성 실패: {e}")
            print(f"   {ui.ERR}[실패] {row['title']}: {e}{ui.FG}")
            failed += 1

    # [로그 추가] 파이프라인 완료 통계
    logger.info(f"AI 3줄 요약 파이프라인 종료 (성공: {success}건, 실패: {failed}건)")
    print(f"\n{ui.HL}[ 요약 결과 ]{ui.FG}")
    print(f"  - 대상: {len(rows)}건")
    print(f"  - 성공(DB 반영): {success}건")
    print(f"  - 실패: {failed}건")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" AI 3줄 요약 (Summarize) 제어소 ")
        print(f"{ui.FG}  아래 메뉴 번호를 선택하거나, CLI 명령어를 직접 입력하여 실행할 수 있습니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 요약 미리보기 (기사 하나 직접 입력 -> AI 요약, DB 반영 없음)")
        print("  2. 미요약 뉴스 일괄 요약 (--unsummarized, DB 반영)")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  summarize --unsummarized [--limit 숫자]")
        print("  (입력 예: summarize --unsummarized --limit 10)")

        print("-" * w)

        user_input = input(f"\n{ui.HL}Codyssey/summarize > {ui.FG}").strip()

        if not user_input:
            continue
        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_summarize_preview()
        elif user_input == '2':
            run_summarize_unsummarized()
        elif user_input.startswith("summarize"):
            run_summarize_cli(user_input)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")


def run_summarize_cli(command_str):
    try:
        args_list = shlex.split(command_str)
        args, unknown = summarize_parser.parse_known_args(args_list[1:])
        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return
        if args.unsummarized:
            limit = args.limit
            if limit <= 0:
                # [로그 추가] 파라미터가 잘못되어 기본값으로 강제 적용한 상황 경고
                logger.warning(f"잘못된 요약 제한 건수 입력('{limit}'). 기본값(10건)으로 보정되어 실행됩니다.")
                print(f"\n{ui.ERR}[오류] 올바른 요약 제한 건수(양의 정수)가 아니므로 기본값 10건을 적용합니다.{ui.FG}")
                limit = 10
            run_summarize_unsummarized(limit=limit)
        else:
            print("\n[안내] --unsummarized 플래그를 포함해서 실행하세요.")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
    except SystemExit:
        print("\n[오류] 옵션 파싱에 실패했습니다.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
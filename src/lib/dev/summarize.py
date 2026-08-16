# src/lib/dev/summarize.py
import shlex
import argparse

from lib.system import ui, logger_mgr
from lib.common import ai_client
from lib.db import sqlite_mgr as db

# 모듈 전용 로거 생성
logger = logger_mgr.get_logger(__name__)

summarize_parser = argparse.ArgumentParser(prog="summarize", add_help=False)
summarize_parser.add_argument("--unsummarized", "-u", action="store_true")
summarize_parser.add_argument("--all", "-a", action="store_true")
summarize_parser.add_argument("--id", "-i", type=str, default=None)
summarize_parser.add_argument("--limit", "-l", type=int, default=10)

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
        logger.error(f"AI 요약 미리보기 중 통신/생성 오류 발생: {e}")
        print(f"\n{ui.ERR}[실패] AI 요약 중 오류: {e}{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    print(f"\n{ui.HL}[ 요약 결과 ]{ui.FG}")
    print(f"  {summary}")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_summarize_action(target="unsummarized", news_id=None, limit=10):
    """지정된 타겟(unsummarized, all, id)의 기사를 가져와 AI 요약하고 DB에 반영한다."""
    if not ai_client.has_api_key():
        logger.error("AI API 키 미설정으로 일괄 요약 파이프라인이 중단되었습니다.")
        print(f"\n{ui.ERR}AI API 키가 설정되지 않았습니다. 환경 설정(1번)에서 먼저 등록하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    db.initialize_db()
    rows = []

    # DB에서 타겟에 맞는 데이터 가져오기
    try:
        if target == "id" and news_id:
            if news_id.isdigit():
                row = db.get_news_by_id(int(news_id))
            else:
                row = db.get_by_news_id(news_id)
            if row:
                rows.append(row)
        elif target == "all":
            with db.get_db_connection() as conn:
                # [수정] 이전 코드의 idx 컬럼 에러를 방지하기 위해 범용적인 pub_date 로만 안전하게 정렬합니다.
                fetched = conn.execute(
                    "SELECT * FROM clean_news ORDER BY pub_date DESC LIMIT ?", (limit,)
                ).fetchall()
                rows = [dict(r) for r in fetched]
        else:
            rows = db.get_unsummarized_news(limit=limit)
    except Exception as e:
        logger.error(f"요약 대상 데이터 조회 중 오류: {e}")
        # [수정] 숨어있던 DB 에러를 화면에 띄워 사용자가 인지할 수 있도록 보완
        print(f"\n{ui.ERR}[오류] 요약 대상 데이터 조회 중 문제가 발생했습니다: {e}{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    if not rows:
        logger.info(f"조건(target: {target})에 맞는 요약 대상 기사가 없어 작업을 건너뜁니다.")
        print(f"\n{ui.HL}요약할 대상 기사가 없습니다.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    logger.info(f"AI 3줄 요약 파이프라인 시작 (대상: {len(rows)}건, 타겟: {target})")
    print(f"\n{ui.HL}>> 대상 기사 {len(rows)}건 AI 요약 시작...{ui.FG}")
    
    success, failed, skipped = 0, 0, 0
    
    for row in rows:
        # 이미 요약된 기사는 스킵 처리하여 사용자님이 기대하신 동작 수행
        if target != "unsummarized" and row.get("is_summarized"):
            print(f"   [스킵] {row['title'][:30]}... (이미 요약됨)")
            skipped += 1
            continue

        try:
            summary = summarize_one(row["title"], row["content"])
            db.update_ai_summary(row["news_id"], summary)
            print(f"   [완료] {row['title'][:40]}...")
            success += 1
        except Exception as e:
            logger.error(f"[{row['news_id']}] AI 요약 생성 실패: {e}")
            print(f"   {ui.ERR}[실패] {row['title'][:30]}...: {e}{ui.FG}")
            failed += 1

    logger.info(f"AI 3줄 요약 파이프라인 종료 (성공: {success}건, 실패: {failed}건, 스킵: {skipped}건)")
    
    print(f"\n{ui.HL}[ 요약 결과 ]{ui.FG}")
    print(f"  - 조회 대상: {len(rows)}건")
    print(f"  - 성공(DB 반영): {success}건")
    print(f"  - 실패: {failed}건")
    if skipped > 0:
        print(f"  - 스킵(이미 요약됨): {skipped}건")
        
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" AI 3줄 요약 (Summarize) 제어소 ")
        print(f"{ui.FG}  아래 메뉴 번호를 선택하거나, CLI 명령어를 직접 입력하여 실행할 수 있습니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 요약 미리보기 (기사 직접 입력 -> AI 요약, DB 반영 없음)")
        print("  2. 미요약 뉴스 일괄 요약 (--unsummarized, 기본 최대 10건)")
        print("  3. 전체 뉴스 일괄 요약 (--all, 이미 요약된 기사는 스킵됨)")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  summarize [--unsummarized | --all | --id 뉴스번호] [--limit 숫자]")
        print("  (입력 예 1: summarize --unsummarized --limit 20)")
        print("  (입력 예 2: summarize --id 42)  ※ id는 list(5번 메뉴)의 No 활용")

        print("-" * w)

        user_input = input(f"\n{ui.HL}Codyssey/summarize > {ui.FG}").strip()

        if not user_input:
            continue
        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_summarize_preview()
        elif user_input == '2':
            run_summarize_action(target="unsummarized", limit=10)
        elif user_input == '3':
            run_summarize_action(target="all", limit=10)
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
            logger.warning(f"요약 CLI 실행 중 알 수 없는 옵션 감지: {unknown}")
            print(f"\n{ui.ERR}알 수 없는 옵션이 포함되어 있습니다: {unknown}{ui.FG}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return

        if args.id:
            target = "id"
        elif args.all:
            target = "all"
        elif args.unsummarized:
            target = "unsummarized"
        else:
            print("\n[안내] --unsummarized, --all, --id 중 하나의 타겟 옵션을 반드시 포함하세요.")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return

        if args.id and args.limit != 10:
            print(f"\n{ui.HL}[안내] --id 옵션 사용 시 특정 1건만 조회하므로 --limit 옵션은 무시됩니다.{ui.FG}")

        limit = args.limit
        if limit <= 0:
            logger.warning(f"잘못된 요약 제한 건수 입력('{limit}'). 기본값(10건)으로 보정되어 실행됩니다.")
            print(f"\n{ui.ERR}[오류] 올바른 요약 제한 건수(양의 정수)가 아니므로 기본값 10건을 적용합니다.{ui.FG}")
            limit = 10

        run_summarize_action(target, args.id, limit)

    except SystemExit:
        print("\n[오류] 옵션 파싱에 실패했습니다.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
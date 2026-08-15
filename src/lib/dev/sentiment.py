# src/lib/dev/sentiment.py [보너스] 감성 분석 AI 연동
import argparse
import json
import shlex

from lib.system import ui, logger_mgr
from lib.common import helpers, ai_client
from lib.db import sqlite_mgr

# [추가] 모듈 전용 로거 생성
logger = logger_mgr.get_logger(__name__)

VALID_SENTIMENTS = ("긍정", "부정", "중립")

SYSTEM_PROMPT = (
    "당신은 뉴스 감성 분석기입니다. 아래 뉴스 제목과 요약(또는 본문 일부)을 보고 감성을\n"
    '"긍정", "부정", "중립" 중 하나로 분류하고 이유를 한 문장으로 쓰세요.\n'
    "다음 JSON 형식으로만 답하세요. 다른 텍스트는 포함하지 마세요.\n"
    '{"sentiment": "긍정|부정|중립", "reason": "..."}'
)

# CLI 명령어를 코드 내부에서 파싱하기 위한 전용 파서 설정
sentiment_parser = argparse.ArgumentParser(prog="sentiment", add_help=False)
sentiment_parser.add_argument("--unanalyzed", "-u", action="store_true")
sentiment_parser.add_argument("--all", "-a", action="store_true")
sentiment_parser.add_argument("--id", "-i", type=str, default=None)
sentiment_parser.add_argument("--limit", "-l", type=int, default=10)


def _classify(news):
    text = news.get("ai_summary") or (news.get("content") or "")[:200]
    user_prompt = f"제목: {news['title']}\n요약: {text}"
    raw = ai_client.generate(SYSTEM_PROMPT, user_prompt, json_output=True)
    result = json.loads(raw)
    sentiment = result.get("sentiment", "중립")
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "중립"
    return sentiment, result.get("reason", "")


def run_sentiment_analysis(target="unanalyzed", news_id=None, limit=10):
    """대상 뉴스에 AI 감성 분석을 실행하고 결과를 DB에 저장합니다."""
    if not ai_client.has_api_key():
        # [로그 추가] AI 환경설정 누락 에러
        logger.error("AI API 키 미설정으로 감성 분석 파이프라인이 중단되었습니다.")
        print(f"\n{ui.ERR}[오류] AI API 키가 설정되지 않았습니다. "
              f"환경 설정(메인 메뉴 1번)에서 먼저 등록하세요.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    rows = sqlite_mgr.get_news_for_sentiment(target, news_id, limit)
    if not rows:
        # [로그 추가] 대상이 없어 일반 종료
        logger.info(f"조건(target: {target})에 맞는 감성 분석 대상이 없어 작업을 건너뜁니다.")
        print(f"\n{ui.ERR}[안내] 감성 분석할 대상이 없습니다.{ui.FG}")
        ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        return

    # [로그 추가] 파이프라인 시작 알림
    logger.info(f"AI 감성 분석 시작 (대상: {len(rows)}건, 타겟: {target})")
    print(f"\n{ui.HL}>> 감성 분석 대상: {len(rows)}건{ui.FG}")
    success, failed = 0, 0

    for row in rows:
        try:
            sentiment, reason = _classify(row)
            sqlite_mgr.update_sentiment(row["news_id"], sentiment, reason)
            print(f"   - [{sentiment}] {row['title']}")
            success += 1
        except Exception as e:
            # [로그 추가] 개별 뉴스 감성 분석 에러 (API 통신 및 파싱 에러)
            logger.error(f"[{row['news_id']}] AI 감성 분석 실패: {e}")
            print(f"   - [실패] {row['title']} ({e})")
            failed += 1

    # [로그 추가] 파이프라인 완료 통계
    logger.info(f"AI 감성 분석 완료 (성공: {success}건, 실패: {failed}건)")
    print(f"\n{ui.HL}>> 감성 분석 완료: 성공 {success}건, 실패 {failed}건{ui.FG}")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_sentiment_cli(command_str):
    """'sentiment --all --limit 20' / 'sentiment --id <news_id>' 형태의 입력을 파싱해 실행합니다."""
    try:
        args_list = shlex.split(command_str)
        args, unknown = sentiment_parser.parse_known_args(args_list[1:])

        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return

        if args.id:
            target = "id"
        elif args.all:
            target = "all"
        else:
            target = "unanalyzed"

        if args.id and args.limit != 10:
            print("\n[안내] --id 사용 시 --limit 옵션은 동작하지 않습니다.")

        limit = args.limit
        if limit <= 0:
            # [로그 추가] 잘못된 제한 건수 파라미터 경고
            logger.warning(f"잘못된 감성 분석 제한 건수 입력('{limit}'). 기본값(10건)으로 보정되어 실행됩니다.")
            print(f"\n{ui.ERR}[오류] 올바른 감성 분석 제한 건수(양의 정수)가 아니므로 기본값 10건을 적용합니다.{ui.FG}")
            limit = 10

        run_sentiment_analysis(target, args.id, limit)

    except SystemExit:
        print("\n[오류] 옵션 값이 올바르지 않습니다.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
    except Exception as e:
        print(f"\n[오류] 명령어 파싱 중 에러 발생: {e}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" AI 감성 분석 (Sentiment) [보너스] 제어소 ")
        print(f"{ui.FG}  뉴스 제목/요약을 AI로 분석해 긍정/부정/중립으로 분류합니다.\n")

        print(f"{ui.HL}  [ 대화형 메뉴 ]{ui.FG}")
        print("  1. 미분석 뉴스 감성 분석 실행 (기본, 최대 10건)")
        print("  2. 전체 뉴스 감성 분석 실행")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 직접 입력 예시 ]{ui.FG}")
        print("  sentiment [--unanalyzed|--all] [--id news_id] [--limit 건수]")
        print("  (입력 예: sentiment --all --limit 20)")

        print("-" * w)
        user_input = input(f"\n{ui.HL}Codyssey/sentiment > {ui.FG}").strip()

        if not user_input:
            continue

        if user_input.lower() == 'p':
            break
        elif user_input == '1':
            run_sentiment_analysis("unanalyzed", limit=10)
        elif user_input == '2':
            run_sentiment_analysis("all", limit=10)
        elif user_input.startswith("sentiment"):
            run_sentiment_cli(user_input)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")
"""[보너스] sentiment: AI로 뉴스 감성(긍정/부정/중립)을 분류해 DB에 저장한다."""
import json

from src import ai_client, db, ui
from src.logger import get_logger

log = get_logger("sentiment")

SYSTEM_PROMPT = (
    "당신은 감성 분석기입니다. 아래 뉴스 제목과 요약을 보고 감성을\n"
    '"긍정", "부정", "중립" 중 하나로 분류하고 이유를 한 문장으로 쓰세요.\n'
    "다음 JSON 형식으로만 답하세요.\n"
    '{"sentiment": "긍정|부정|중립", "reason": "..."}'
)


def _get_targets(target: str, target_id: int | None, limit: int) -> list:
    if target == "id":
        row = db.get_by_id(target_id)
        return [row] if row else []
    if target == "unanalyzed":
        return db.list_news_without_sentiment(limit=limit)
    return db.list_news(limit=limit)


def run_sentiment(
    target: str = "unanalyzed", target_id: int | None = None, limit: int = 10
) -> None:
    if not ai_client.has_api_key():
        ui.print_error(
            "Gemini API 키가 설정되지 않았습니다. `config set-api-key`로 먼저 등록하세요."
        )
        return
    db.init_db()
    rows = _get_targets(target, target_id, limit)
    if not rows:
        ui.print_warning("감성 분석할 대상이 없습니다.")
        return

    ui.print_info(f"감성 분석 대상: {len(rows)}건")
    success, failed = 0, 0

    with ui.progress_bar() as progress:
        task = progress.add_task("감성 분석 중", total=len(rows))
        for row in rows:
            text = row["summary"] or (row["content"] or "")[:200]
            user_prompt = f"제목: {row['title']}\n요약: {text}"
            try:
                raw = ai_client.generate(SYSTEM_PROMPT, user_prompt, json_output=True)
                result = json.loads(raw)
                db.update_sentiment(
                    row["id"], result.get("sentiment", "중립"), result.get("reason", "")
                )
                success += 1
            except Exception as e:
                log.error(f"감성 분석 실패 id={row['id']}: {e}")
                failed += 1
            progress.advance(task)

    ui.print_table("감성 분석 결과", ["항목", "건수"], [["성공", success], ["실패", failed]])
    ui.print_success(f"감성 분석 완료: {success}건 성공, {failed}건 실패")

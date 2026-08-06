"""summarize: AI로 뉴스 본문을 요약해 DB에 저장한다."""
from src import ai_client, db, ui
from src.logger import get_logger

log = get_logger("summarizer")

SYSTEM_PROMPT = (
    "당신은 뉴스 에디터입니다. 아래 뉴스 본문을 읽고 핵심만 한국어로 3문장 이내,\n"
    "150자 내외로 요약하세요. 숫자·고유명사는 정확히 유지하고,\n"
    "요약 외의 의견이나 부가 설명은 절대 추가하지 마세요."
)


def _get_targets(target: str, target_id: int | None, limit: int) -> list:
    if target == "id":
        row = db.get_by_id(target_id)
        return [row] if row else []
    if target == "unsummarized":
        return db.list_news(limit=limit, unsummarized_only=True)
    return db.list_news(limit=limit)


def run_summarize(target: str, target_id: int | None, limit: int, force: bool) -> None:
    if not ai_client.has_api_key():
        ui.print_error(
            "Gemini API 키가 설정되지 않았습니다. `config set-api-key`로 먼저 등록하세요."
        )
        return
    db.init_db()
    rows = _get_targets(target, target_id, limit)
    if not rows:
        ui.print_warning("요약할 대상이 없습니다.")
        return

    ui.print_info(f"요약 대상: {len(rows)}건")
    success, skipped, failed = 0, 0, 0

    with ui.progress_bar() as progress:
        task = progress.add_task("AI 요약 중", total=len(rows))
        for row in rows:
            if row["is_summarized"] and not force:
                skipped += 1
                progress.advance(task)
                continue
            user_prompt = f"제목: {row['title']}\n본문: {row['content']}"
            try:
                summary = ai_client.generate(SYSTEM_PROMPT, user_prompt)
                summary = summary.strip()
                db.update_summary(row["id"], summary)
                log.info(f"요약 완료 id={row['id']} ({len(row['content'])}자 -> {len(summary)}자)")
                success += 1
            except Exception as e:
                log.error(f"요약 실패 id={row['id']}: {e}")
                failed += 1
            progress.advance(task)

    ui.print_table(
        "요약 결과",
        ["항목", "건수"],
        [["성공", success], ["스킵(이미 요약됨)", skipped], ["실패", failed]],
    )
    ui.print_success(f"요약 완료: {success}건 성공, {failed}건 실패")

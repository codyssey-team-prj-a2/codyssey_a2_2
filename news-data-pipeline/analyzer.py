"""AI-powered insight analysis across multiple news summaries."""

import logging

from summarizer import OpenAIClient

logger = logging.getLogger(__name__)


def build_analysis_prompt(summaries: list[str]) -> str:
    """Build a prompt that asks the model to analyze a batch of article summaries.

    Uses summaries (not full article bodies) to keep API cost low.
    """
    joined = "\n".join(f"- {s}" for s in summaries)
    return (
        "다음은 여러 뉴스 기사의 요약 목록이야. 이 요약들을 종합해서 아래 4가지 항목으로 "
        "분석 결과를 작성해줘. 각 항목은 명확한 제목과 함께 정리해줘.\n\n"
        "1. 주요 트렌드\n"
        "2. 핵심 키워드 (5~10개)\n"
        "3. 공통점 / 차이점\n"
        "4. 시사점\n\n"
        f"뉴스 요약 목록:\n{joined}"
    )


def run_insight_analysis(client: OpenAIClient, model: str, summaries: list[str]) -> str | None:
    """Send summaries to the model and return the combined insight text."""
    if not summaries:
        logger.warning("분석할 요약이 없어 인사이트 분석을 건너뜀")
        return None

    prompt = build_analysis_prompt(summaries)
    try:
        return client.chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": "너는 뉴스 데이터를 분석하는 애널리스트야."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=800,
        )
    except Exception as exc:
        logger.error("OpenAI 인사이트 분석 API 호출 실패: %s", exc)
        return None

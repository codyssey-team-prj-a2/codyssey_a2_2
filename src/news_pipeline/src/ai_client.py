"""Gemini API 공통 호출 wrapper. 레이트리밋/일시 서버 과부하 대응(호출 간 지연 + 재시도 백오프)."""
import logging
import time

from google import genai
from google.genai import errors, types

from src import config_loader
from src.logger import get_logger

log = get_logger("ai_client")

# google-genai 내부 로거가 화면(stderr)에 직접 찍는 것을 막는다.
# 화면 출력은 ui.py(rich), 파일 로그는 logger.py로만 나가야 한다.
logging.getLogger("google_genai._api_client").setLevel(logging.ERROR)

_client = None


def has_api_key() -> bool:
    return bool(config_loader.get_env("GEMINI_API_KEY"))


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = config_loader.get_env("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY가 설정되지 않았습니다. `config set-api-key`로 먼저 등록하세요."
            )
        _client = genai.Client(api_key=api_key)
    return _client


RETRYABLE_CODES = {429, 500, 502, 503, 504}


def generate(
    system_prompt: str, user_prompt: str, json_output: bool = False, max_retries: int = 5
) -> str:
    """system/user 프롬프트로 Gemini를 호출해 텍스트 응답을 반환한다.

    무료 티어는 계정별로 레이트리밋이 달라 정확한 수치를 코드에 못박지 않는다.
    대신 호출마다 config의 지연을 두고, 429(RESOURCE_EXHAUSTED)나 5xx(일시적 서버 과부하) 발생 시
    지수 백오프로 재시도한다.
    """
    config = config_loader.load_config()
    ai_cfg = config.get("ai", {})
    model = ai_cfg.get("model", "gemini-2.5-flash")
    delay = ai_cfg.get("request_delay_sec", 4.0)
    client = _get_client()

    gen_config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json" if json_output else None,
    )

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model, contents=user_prompt, config=gen_config
            )
            time.sleep(delay)
            return response.text or ""
        except errors.APIError as e:
            last_error = e
            code = getattr(e, "code", None)
            is_retryable = code in RETRYABLE_CODES
            wait = delay * (2**attempt) if is_retryable else delay
            log.warning(f"AI 호출 실패(시도 {attempt}/{max_retries}, code={code}): {e}")
            if attempt < max_retries and is_retryable:
                time.sleep(wait)
            elif attempt < max_retries:
                time.sleep(delay)

    raise RuntimeError(f"AI 호출 최종 실패({max_retries}회 시도): {last_error}")

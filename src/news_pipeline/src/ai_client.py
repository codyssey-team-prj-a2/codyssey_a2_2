"""LLM 프로바이더(OpenAI/Anthropic/Google) 공통 호출 wrapper.

.env의 LLM_PROVIDER로 어떤 프로바이더를 쓸지 고르고, LLM_MODEL/LLM_API_KEY로
모델/키를 받는다. 레이트리밋/일시 서버 과부하 대응(호출 간 지연 + 재시도 백오프)은
프로바이더 공통으로 처리한다.
"""
import logging
import time
from typing import NamedTuple

from src import config_loader
from src.logger import get_logger

log = get_logger("ai_client")

# google-genai 내부 로거가 화면(stderr)에 직접 찍는 것을 막는다.
# 화면 출력은 ui.py(rich), 파일 로그는 logger.py로만 나가야 한다.
logging.getLogger("google_genai._api_client").setLevel(logging.ERROR)

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "google": "gemini-2.5-flash",
}

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _provider() -> str:
    return (config_loader.get_env("LLM_PROVIDER") or "google").lower()


def _model() -> str:
    return config_loader.get_env("LLM_MODEL") or DEFAULT_MODELS.get(_provider(), "")


def has_api_key() -> bool:
    return bool(config_loader.get_env("LLM_API_KEY"))


def _api_key() -> str:
    key = config_loader.get_env("LLM_API_KEY")
    if not key:
        raise RuntimeError(
            "LLM_API_KEY가 설정되지 않았습니다. `config set-api-key`로 먼저 등록하세요."
        )
    return key


class Request(NamedTuple):
    model: str
    system_prompt: str
    user_prompt: str
    api_key: str
    json_output: bool
    max_tokens: int


def _call_openai(req: Request) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=req.api_key)
    kwargs = {"response_format": {"type": "json_object"}} if req.json_output else {}
    resp = client.chat.completions.create(
        model=req.model,
        max_tokens=req.max_tokens,
        messages=[
            {"role": "system", "content": req.system_prompt},
            {"role": "user", "content": req.user_prompt},
        ],
        **kwargs,
    )
    return resp.choices[0].message.content or ""


def _call_anthropic(req: Request) -> str:
    from anthropic import Anthropic

    client = Anthropic(api_key=req.api_key)
    resp = client.messages.create(
        model=req.model,
        max_tokens=req.max_tokens,
        system=req.system_prompt,
        messages=[{"role": "user", "content": req.user_prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _call_google(req: Request) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=req.api_key)
    gen_config = types.GenerateContentConfig(
        system_instruction=req.system_prompt,
        response_mime_type="application/json" if req.json_output else None,
        max_output_tokens=req.max_tokens,
    )
    response = client.models.generate_content(
        model=req.model, contents=req.user_prompt, config=gen_config
    )
    return response.text or ""


PROVIDER_HANDLERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "google": _call_google,
}


def _status_code(e: Exception) -> int | None:
    return getattr(e, "status_code", None) or getattr(e, "code", None)


def generate(
    system_prompt: str, user_prompt: str, json_output: bool = False, max_retries: int = 5
) -> str:
    """system/user 프롬프트로 설정된 LLM 프로바이더를 호출해 텍스트 응답을 반환한다.

    무료/저가 티어는 계정별로 레이트리밋이 달라 정확한 수치를 코드에 못박지 않는다.
    대신 호출마다 config의 지연을 두고, 429(요청 제한)나 5xx(일시적 서버 과부하) 발생 시
    지수 백오프로 재시도한다.
    """
    config = config_loader.load_config()
    ai_cfg = config.get("ai", {})
    delay = ai_cfg.get("request_delay_sec", 4.0)
    max_tokens = ai_cfg.get("max_tokens", 500)

    provider = _provider()
    handler = PROVIDER_HANDLERS.get(provider)
    if handler is None:
        raise RuntimeError(
            f"지원하지 않는 LLM_PROVIDER 입니다: {provider} (openai/anthropic/google 중 선택)"
        )
    req = Request(
        model=_model(), system_prompt=system_prompt, user_prompt=user_prompt,
        api_key=_api_key(), json_output=json_output, max_tokens=max_tokens,
    )

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            text = handler(req)
            time.sleep(delay)
            return text
        except Exception as e:
            last_error = e
            code = _status_code(e)
            is_retryable = code in RETRYABLE_STATUS
            wait = delay * (2**attempt) if is_retryable else delay
            log.warning(
                f"AI 호출 실패(시도 {attempt}/{max_retries}, provider={provider}, code={code}): {e}"
            )
            if attempt < max_retries:
                time.sleep(wait)

    raise RuntimeError(f"AI 호출 최종 실패({max_retries}회 시도): {last_error}")

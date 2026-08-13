# lib/common/ai_client.py
"""LLM 프로바이더(Gemini/GPT/Claude) 공통 호출 wrapper.

setup.py가 .env에 저장하는 LLM_PROVIDER(gemini/openai/anthropic)/LLM_MODEL/
LLM_API_KEY 값을 그대로 읽어서 사용한다. 레이트리밋/일시 서버 과부하 대응은
프로바이더 공통으로 처리(호출 간 지연 + 재시도 백오프).
"""
import time
from lib.system import config_mgr

DEFAULT_MODELS = {
    # gemini-2.5-flash는 무료 티어 쿼터가 모델당 하루 20회로 낮고,
    # gemini-2.5-flash-lite는 신규 사용자에게 더 이상 제공되지 않아(404),
    # 별도 쿼터 풀인 gemini-3.5-flash-lite를 기본값으로 쓴다.
    "gemini": "gemini-3.5-flash-lite",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20240620",
}

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


def _provider():
    return (config_mgr.get_env("LLM_PROVIDER") or "gemini").lower()


def _model():
    return config_mgr.get_env("LLM_MODEL") or DEFAULT_MODELS.get(_provider(), "")


def has_api_key():
    return bool(config_mgr.get_env("LLM_API_KEY"))


def _api_key():
    key = config_mgr.get_env("LLM_API_KEY")
    if not key:
        raise RuntimeError("LLM_API_KEY가 설정되지 않았습니다. 환경 설정(1번)에서 먼저 등록하세요.")
    return key


def _call_openai(model, api_key, system_prompt, user_prompt, json_output, max_tokens):
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    kwargs = {"response_format": {"type": "json_object"}} if json_output else {}
    resp = client.chat.completions.create(
        model=model,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        **kwargs,
    )
    return resp.choices[0].message.content or ""


def _call_anthropic(model, api_key, system_prompt, user_prompt, json_output, max_tokens):
    from anthropic import Anthropic

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _call_gemini(model, api_key, system_prompt, user_prompt, json_output, max_tokens):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config_kwargs = {
        "system_instruction": system_prompt,
        "response_mime_type": "application/json" if json_output else None,
        "max_output_tokens": max_tokens,
    }
    # thinking을 지원하는 non-lite 모델(예: gemini-2.5-flash)은 기본적으로 내부
    # reasoning("thinking")에 max_output_tokens 예산을 먼저 소모해서, 짧고 결정적인
    # 요약/추출 용도로는 답변이 중간에 잘려버리는 문제가 있었다(실제로 재현/확인).
    # thinking이 필요 없는 작업이므로 꺼서 토큰 예산이 전부 실제 답변에 쓰이게 한다.
    # 단 "lite" 계열은 thinking_config 자체를 안 받아서(400 INVALID_ARGUMENT) 제외한다.
    if "lite" not in model:
        config_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

    gen_config = types.GenerateContentConfig(**config_kwargs)
    response = client.models.generate_content(model=model, contents=user_prompt, config=gen_config)
    return response.text or ""


PROVIDER_HANDLERS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
}


def _status_code(e):
    return getattr(e, "status_code", None) or getattr(e, "code", None)


def generate(system_prompt, user_prompt, json_output=False, max_retries=5):
    """system/user 프롬프트로 설정된 LLM 프로바이더를 호출해 텍스트 응답을 반환한다.

    429(요청 제한)나 5xx(일시적 서버 과부하) 발생 시 지수 백오프로 재시도한다.
    """
    provider = _provider()
    handler = PROVIDER_HANDLERS.get(provider)
    if handler is None:
        raise RuntimeError(f"지원하지 않는 LLM_PROVIDER 입니다: {provider} (gemini/openai/anthropic 중 선택)")

    model = _model()
    api_key = _api_key()
    delay = 4.0
    max_tokens = 500

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            text = handler(model, api_key, system_prompt, user_prompt, json_output, max_tokens)
            time.sleep(delay)
            return text
        except Exception as e:
            last_error = e
            code = _status_code(e)
            is_retryable = code in RETRYABLE_STATUS
            wait = delay * (2 ** attempt) if is_retryable else delay
            if attempt < max_retries:
                time.sleep(wait)

    raise RuntimeError(f"AI 호출 최종 실패({max_retries}회 시도): {last_error}")

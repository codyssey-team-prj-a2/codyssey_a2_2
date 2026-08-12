# src/lib/common/ai_client.py
"""LLM 프로바이더(Gemini/OpenAI/Anthropic) 공통 호출 wrapper.

setup.py에서 .env에 저장한 LLM_PROVIDER(gemini/openai/anthropic)로 어떤 프로바이더를
쓸지 고르고, LLM_MODEL/LLM_API_KEY로 모델/키를 받는다.
"""
from typing import NamedTuple

from lib.system import config_mgr

DEFAULT_MODELS = {
    "gemini": "gemini-1.5-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20240620",
}


def _provider():
    return (config_mgr.get_env("LLM_PROVIDER") or "gemini").lower()


def _model():
    return config_mgr.get_env("LLM_MODEL") or DEFAULT_MODELS.get(_provider(), "")


def has_api_key():
    return bool(config_mgr.get_env("LLM_API_KEY"))


def _api_key():
    key = config_mgr.get_env("LLM_API_KEY")
    if not key:
        raise RuntimeError("LLM_API_KEY가 설정되지 않았습니다. 환경 설정(1번 메뉴)에서 먼저 등록하세요.")
    return key


class Request(NamedTuple):
    model: str
    system_prompt: str
    user_prompt: str
    api_key: str
    json_output: bool
    max_tokens: int


def _call_openai(req):
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


def _call_anthropic(req):
    from anthropic import Anthropic

    client = Anthropic(api_key=req.api_key)
    resp = client.messages.create(
        model=req.model,
        max_tokens=req.max_tokens,
        system=req.system_prompt,
        messages=[{"role": "user", "content": req.user_prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


def _call_gemini(req):
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
    "gemini": _call_gemini,
    "openai": _call_openai,
    "anthropic": _call_anthropic,
}


def generate(system_prompt, user_prompt, json_output=False, max_tokens=500):
    """system/user 프롬프트로 설정된 LLM 프로바이더를 호출해 텍스트 응답을 반환한다."""
    provider = _provider()
    handler = PROVIDER_HANDLERS.get(provider)
    if handler is None:
        raise RuntimeError(f"지원하지 않는 LLM_PROVIDER 입니다: {provider} (gemini/openai/anthropic 중 선택)")

    req = Request(
        model=_model(), system_prompt=system_prompt, user_prompt=user_prompt,
        api_key=_api_key(), json_output=json_output, max_tokens=max_tokens,
    )
    return handler(req)

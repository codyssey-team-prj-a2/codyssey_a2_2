"""AI news summarization using an OpenAI-compatible chat completions API.

Uses `requests` directly (rather than the official openai SDK) because some
OpenAI-compatible gateways run a WAF that blocks the SDK's default
User-Agent/header fingerprint while accepting plain HTTP clients.
"""

import logging

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIClient:
    """Minimal OpenAI-compatible chat completions client built on requests."""

    def __init__(self, api_key: str, base_url: str | None = None, timeout: int = 30):
        self.api_key = api_key
        self.base_url = (base_url or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout

    def chat_completion(self, model: str, messages: list[dict[str, str]], temperature: float = 0.3, max_tokens: int = 300) -> str:
        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()


def build_summary_prompt(title: str, content: str) -> str:
    """Build the prompt sent to the model for a single-article summary."""
    return (
        "다음 뉴스 기사를 한국어로 3문장 이내로 핵심만 요약해줘. "
        "불필요한 수식어 없이 사실 위주로 작성해줘.\n\n"
        f"제목: {title}\n\n본문: {content}"
    )


def get_openai_client(api_key: str, base_url: str | None = None) -> OpenAIClient:
    """Create and return an OpenAI-compatible client instance.

    base_url lets the pipeline point at an OpenAI-compatible proxy/gateway
    instead of api.openai.com, configured via OPENAI_BASE_URL.
    """
    return OpenAIClient(api_key=api_key, base_url=base_url)


def summarize_text(client: OpenAIClient, model: str, title: str, content: str) -> str | None:
    """Call the API to summarize one article. Returns None on failure."""
    prompt = build_summary_prompt(title, content or "")
    try:
        return client.chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": "너는 뉴스 기사를 간결하게 요약하는 어시스턴트야."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=300,
        )
    except Exception as exc:
        logger.error("OpenAI 요약 API 호출 실패: %s", exc)
        return None


def analyze_sentiment(client: OpenAIClient, model: str, title: str, summary: str) -> str | None:
    """Classify sentiment as positive/negative/neutral. Returns None on failure."""
    prompt = (
        "다음 뉴스의 감성을 positive, negative, neutral 중 하나의 단어로만 답해줘.\n\n"
        f"제목: {title}\n요약: {summary}"
    )
    try:
        result = client.chat_completion(
            model=model,
            messages=[
                {"role": "system", "content": "너는 뉴스 감성을 분류하는 어시스턴트야. 반드시 한 단어로만 답해."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            max_tokens=10,
        )
        result = result.lower()
        if result not in ("positive", "negative", "neutral"):
            logger.warning("예상치 못한 감성 분석 응답, neutral로 대체: %r", result)
            return "neutral"
        return result
    except Exception as exc:
        logger.error("OpenAI 감성 분석 API 호출 실패: %s", exc)
        return None

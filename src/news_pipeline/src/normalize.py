"""URL 정규화 공용 함수.

cleaner.py(중복 판정)와 reporter.py(중복 수집 방지율 집계)가 같은 정규화 로직을
공유해야 하는데, 둘 다 import-linter 레이어상 같은 계층(sibling)이라 서로를
직접 import할 수 없다. 그래서 더 아래 계층인 이 모듈로 로직을 분리했다.
"""
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term",
    "utm_content", "ref", "fbclid", "gclid",
}


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    query = [(k, v) for k, v in parse_qsl(parsed.query) if k.lower() not in TRACKING_PARAMS]
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        query=urlencode(query),
        fragment="",
    )
    return urlunparse(normalized)

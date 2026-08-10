"""Chart generation with matplotlib, with best-effort Korean font support."""

import logging
import platform
from collections import Counter
from pathlib import Path
from typing import Sequence

import matplotlib

matplotlib.use("Agg")  # headless/CLI environment, no display needed
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)

_KOREAN_FONT_CANDIDATES = [
    "Malgun Gothic",   # Windows
    "AppleGothic",     # macOS
    "NanumGothic",     # Linux (if installed)
    "Noto Sans CJK KR",
    "Noto Sans KR",
]


def setup_korean_font() -> None:
    """Try to select a Korean-capable font; fall back silently if none found."""
    try:
        from matplotlib import font_manager

        available = {f.name for f in font_manager.fontManager.ttflist}
        for candidate in _KOREAN_FONT_CANDIDATES:
            if candidate in available:
                plt.rcParams["font.family"] = candidate
                plt.rcParams["axes.unicode_minus"] = False
                logger.info("한글 폰트 설정: %s", candidate)
                return
        logger.warning("시스템에서 한글 폰트를 찾지 못함 (플랫폼: %s). 기본 폰트로 진행", platform.system())
    except Exception as exc:
        logger.warning("한글 폰트 설정 중 오류, 기본 폰트로 진행: %s", exc)


def plot_category_distribution(categories: Sequence[str], output_path: Path) -> Path | None:
    """Bar chart of article counts per category."""
    if not categories:
        logger.warning("카테고리 데이터가 없어 차트를 생성하지 않음")
        return None
    try:
        counts = Counter(categories)
        labels, values = zip(*sorted(counts.items(), key=lambda kv: kv[1], reverse=True))

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.bar(labels, values, color="#4C72B0")
        ax.set_title("카테고리별 뉴스 수")
        ax.set_xlabel("카테고리")
        ax.set_ylabel("뉴스 수")
        plt.xticks(rotation=30, ha="right")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        logger.info("카테고리 분포 차트 저장: %s", output_path)
        return output_path
    except Exception as exc:
        logger.error("카테고리 분포 차트 생성 실패: %s", exc)
        return None


def plot_daily_trend(dates: Sequence[str], output_path: Path) -> Path | None:
    """Line chart of article counts collected per day (dates as YYYY-MM-DD strings)."""
    if not dates:
        logger.warning("날짜 데이터가 없어 차트를 생성하지 않음")
        return None
    try:
        day_only = [d[:10] for d in dates if d]
        counts = Counter(day_only)
        sorted_days = sorted(counts.items())
        if not sorted_days:
            return None
        labels, values = zip(*sorted_days)

        fig, ax = plt.subplots(figsize=(8, 5))
        ax.plot(labels, values, marker="o", color="#DD8452")
        ax.set_title("일자별 뉴스 수집 추이")
        ax.set_xlabel("날짜")
        ax.set_ylabel("수집 뉴스 수")
        plt.xticks(rotation=30, ha="right")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        logger.info("일자별 추이 차트 저장: %s", output_path)
        return output_path
    except Exception as exc:
        logger.error("일자별 추이 차트 생성 실패: %s", exc)
        return None


def plot_sentiment_distribution(sentiments: Sequence[str], output_path: Path) -> Path | None:
    """Pie chart of sentiment distribution (bonus feature)."""
    filtered = [s for s in sentiments if s]
    if not filtered:
        logger.warning("감성 데이터가 없어 차트를 생성하지 않음")
        return None
    try:
        counts = Counter(filtered)
        labels, values = zip(*counts.items())

        fig, ax = plt.subplots(figsize=(6, 6))
        ax.pie(values, labels=labels, autopct="%1.1f%%", colors=["#55A868", "#C44E52", "#8172B2"])
        ax.set_title("감성 분포")
        fig.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)
        logger.info("감성 분포 차트 저장: %s", output_path)
        return output_path
    except Exception as exc:
        logger.error("감성 분포 차트 생성 실패: %s", exc)
        return None

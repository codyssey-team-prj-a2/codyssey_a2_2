"""matplotlib으로 카테고리별 뉴스 수 / 일자별 수집 추이 차트를 PNG로 저장한다."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from src import db
from src.logger import get_logger

log = get_logger("visualizer")

BASE_DIR = Path(__file__).resolve().parent.parent
CHARTS_DIR = BASE_DIR / "reports" / "charts"

_KOREAN_FONT_CANDIDATES = ["Malgun Gothic", "NanumGothic", "AppleGothic"]


def _setup_korean_font() -> None:
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _KOREAN_FONT_CANDIDATES:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    else:
        log.warning("한글 폰트를 찾지 못해 기본 폰트로 표시합니다(한글이 깨질 수 있음).")
    plt.rcParams["axes.unicode_minus"] = False


def chart_category_distribution() -> Path:
    _setup_korean_font()
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM news GROUP BY category ORDER BY cnt DESC"
        ).fetchall()
    finally:
        conn.close()

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / "category_distribution.png"
    fig, ax = plt.subplots(figsize=(8, 5))
    if rows:
        categories = [r["category"] or "미분류" for r in rows]
        counts = [r["cnt"] for r in rows]
        ax.bar(categories, counts, color="#4C72B0")
    ax.set_title("카테고리별 뉴스 수")
    ax.set_xlabel("카테고리")
    ax.set_ylabel("건수")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def chart_daily_trend() -> Path:
    _setup_korean_font()
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT substr(collected_at, 1, 10) AS day, COUNT(*) AS cnt "
            "FROM news GROUP BY day ORDER BY day"
        ).fetchall()
    finally:
        conn.close()

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / "daily_trend.png"
    fig, ax = plt.subplots(figsize=(8, 5))
    if rows:
        days = [r["day"] for r in rows]
        counts = [r["cnt"] for r in rows]
        ax.plot(days, counts, marker="o", color="#DD8452")
        ax.tick_params(axis="x", rotation=45)
    ax.set_title("일자별 수집 추이")
    ax.set_xlabel("날짜")
    ax.set_ylabel("수집 건수")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def chart_sentiment_distribution() -> Path:
    _setup_korean_font()
    conn = db.get_connection()
    try:
        rows = conn.execute(
            "SELECT sentiment, COUNT(*) AS cnt FROM news "
            "WHERE sentiment IS NOT NULL GROUP BY sentiment"
        ).fetchall()
    finally:
        conn.close()

    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    path = CHARTS_DIR / "sentiment_distribution.png"
    fig, ax = plt.subplots(figsize=(6, 5))
    if rows:
        labels = [r["sentiment"] for r in rows]
        counts = [r["cnt"] for r in rows]
        colors = {"긍정": "#55A868", "부정": "#C44E52", "중립": "#8172B2"}
        ax.bar(labels, counts, color=[colors.get(label, "#4C72B0") for label in labels])
    ax.set_title("뉴스 감성 분포")
    ax.set_xlabel("감성")
    ax.set_ylabel("건수")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def run_visualize() -> list[Path]:
    db.init_db()
    paths = [chart_category_distribution(), chart_daily_trend(), chart_sentiment_distribution()]
    for p in paths:
        log.info(f"차트 저장: {p}")
    return paths

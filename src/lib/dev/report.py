# src/lib/dev/report.py
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from lib.system import ui, config_mgr
from lib.common import helpers
from lib.db import sqlite_mgr

_KOREAN_FONT_CANDIDATES = ["Malgun Gothic", "NanumGothic", "AppleGothic"]


def _setup_korean_font():
    """한글이 깨지지 않도록 시스템에 설치된 한글 폰트를 matplotlib에 적용합니다."""
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in _KOREAN_FONT_CANDIDATES:
        if name in available:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def _charts_dir():
    cfg = config_mgr.load_config()
    charts_dir = os.path.join(cfg.get("report_path", "./reports"), "charts")
    os.makedirs(charts_dir, exist_ok=True)
    return charts_dir


def chart_category_distribution():
    """카테고리별 뉴스 건수 막대 차트를 생성해 PNG로 저장하고 경로를 반환합니다."""
    _setup_korean_font()
    with sqlite_mgr.get_db_connection() as conn:
        rows = conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM clean_news GROUP BY category ORDER BY cnt DESC"
        ).fetchall()

    path = os.path.join(_charts_dir(), "category_distribution.png")
    fig, ax = plt.subplots(figsize=(8, 5))
    if rows:
        categories = [row["category"] for row in rows]
        counts = [row["cnt"] for row in rows]
        ax.bar(categories, counts, color="#4C72B0")
    ax.set_title("카테고리별 뉴스 건수")
    ax.set_xlabel("카테고리")
    ax.set_ylabel("건수")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def chart_daily_trend():
    """일자별 뉴스 수집 추이 꺾은선 차트를 생성해 PNG로 저장하고 경로를 반환합니다."""
    _setup_korean_font()
    with sqlite_mgr.get_db_connection() as conn:
        rows = conn.execute(
            "SELECT pub_date, COUNT(*) AS cnt FROM clean_news GROUP BY pub_date ORDER BY pub_date"
        ).fetchall()

    path = os.path.join(_charts_dir(), "daily_trend.png")
    fig, ax = plt.subplots(figsize=(8, 5))
    if rows:
        days = [row["pub_date"] for row in rows]
        counts = [row["cnt"] for row in rows]
        ax.plot(days, counts, marker="o", color="#DD8452")
        ax.tick_params(axis="x", rotation=45)
    ax.set_title("일자별 뉴스 수집 추이")
    ax.set_xlabel("날짜")
    ax.set_ylabel("건수")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def _generate_and_report(chart_func, label):
    try:
        path = chart_func()
        print(f"\n{ui.HL}>> {label}이(가) 생성되었습니다.{ui.FG}")
        print(f"   저장 경로: {path}")
    except Exception as e:
        print(f"\n{ui.ERR}[오류] 차트 생성 중 문제가 발생했습니다: {e}{ui.FG}")
    input("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" 품질 지표 및 시각화 차트 출력 (Report) 제어소 ")
        print(f"{ui.FG}  matplotlib 기반 차트를 생성하여 PNG 파일로 저장합니다.\n")

        print(f"{ui.HL}  [ 메뉴 ]{ui.FG}")
        print("  1. 카테고리별 뉴스 건수 차트 생성")
        print("  2. 일자별 뉴스 수집 추이 차트 생성")
        print("  3. 전체 차트 일괄 생성")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print("-" * w)
        choice = input(f"\n{ui.HL}Codyssey/report > {ui.FG}").strip().lower()

        if choice == 'p':
            break
        elif choice == '1':
            _generate_and_report(chart_category_distribution, "카테고리별 뉴스 건수 차트")
        elif choice == '2':
            _generate_and_report(chart_daily_trend, "일자별 뉴스 수집 추이 차트")
        elif choice == '3':
            try:
                paths = [chart_category_distribution(), chart_daily_trend()]
                print(f"\n{ui.HL}>> 차트 {len(paths)}건이 생성되었습니다.{ui.FG}")
                for path in paths:
                    print(f"   - {path}")
            except Exception as e:
                print(f"\n{ui.ERR}[오류] 차트 생성 중 문제가 발생했습니다: {e}{ui.FG}")
            input("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            input("다시 시도하려면 [Enter]를 누르세요...")

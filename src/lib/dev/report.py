# src/lib/dev/report.py
import argparse
import os
import shlex
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from lib.system import ui, config_mgr, logger_mgr, help_mgr
from lib.common import helpers
from lib.db import sqlite_mgr

logger = logger_mgr.get_logger(__name__)

_KOREAN_FONT_CANDIDATES = ["Malgun Gothic", "NanumGothic", "AppleGothic"]

# CLI 명령어를 코드 내부에서 파싱하기 위한 전용 파서 설정
report_parser = argparse.ArgumentParser(prog="report", add_help=False)
report_parser.add_argument("--date-from", type=str, default=None)
report_parser.add_argument("--date-to", type=str, default=None)
report_parser.add_argument("--format", "-f", type=str, default="console",
                            choices=["console", "txt", "md"])


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


def chart_category_distribution(date_from=None, date_to=None):
    """카테고리별 뉴스 건수 막대 차트를 생성해 PNG로 저장하고 경로를 반환합니다."""
    _setup_korean_font()
    conditions, params = sqlite_mgr.date_range_conditions(date_from, date_to)
    sql = "SELECT category, COUNT(*) AS cnt FROM clean_news"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " GROUP BY category ORDER BY cnt DESC"
    with sqlite_mgr.get_db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

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


def chart_daily_trend(date_from=None, date_to=None):
    """일자별 뉴스 수집 추이 꺾은선 차트를 생성해 PNG로 저장하고 경로를 반환합니다."""
    _setup_korean_font()
    conditions, params = sqlite_mgr.date_range_conditions(date_from, date_to)
    sql = "SELECT pub_date, COUNT(*) AS cnt FROM clean_news"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " GROUP BY pub_date ORDER BY pub_date"
    with sqlite_mgr.get_db_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

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


def chart_sentiment_distribution(date_from=None, date_to=None):
    """[보너스] 감성 분석 결과(긍정/부정/중립) 분포 원형 차트를 생성해 PNG로 저장하고 경로를 반환합니다."""
    _setup_korean_font()
    rows = sqlite_mgr.get_sentiment_distribution(date_from, date_to)

    path = os.path.join(_charts_dir(), "sentiment_distribution.png")
    fig, ax = plt.subplots(figsize=(6, 6))
    if rows:
        labels = [row["sentiment"] for row in rows]
        counts = [row["cnt"] for row in rows]
        colors = {"긍정": "#55A868", "부정": "#C44E52", "중립": "#8172B2"}
        ax.pie(
            counts,
            labels=labels,
            colors=[colors.get(label, "#4C72B0") for label in labels],
            autopct="%1.1f%%",
            startangle=90,
            counterclock=False,
        )
        ax.axis("equal")
    ax.set_title("뉴스 감성 분포")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def _raw_news_count(date_from=None, date_to=None):
    """
    raw 저장소(JSONL, data/raw/*.jsonl)에 적재된 원본 뉴스 건수를 셉니다.
    정제 통과율(clean/raw) 계산의 분모로 사용됩니다.
    date_from/date_to 지정 시 각 레코드의 collected_at(수집 시각) 날짜 부분으로 필터링합니다.
    """
    cfg = config_mgr.load_config()
    raw_dir = os.path.join(cfg.get("db_path", "./data"), "raw")
    if not os.path.isdir(raw_dir):
        return 0

    import json

    count = 0
    for name in os.listdir(raw_dir):
        if not name.endswith(".jsonl"):
            continue
        with open(os.path.join(raw_dir, name), "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if not date_from and not date_to:
                    count += 1
                    continue
                try:
                    collected_date = json.loads(line).get("collected_at", "")[:10]
                except (json.JSONDecodeError, AttributeError):
                    collected_date = ""
                if date_from and collected_date < date_from:
                    continue
                if date_to and collected_date > date_to:
                    continue
                count += 1
    return count


def get_cleanliness_rate(date_from=None, date_to=None):
    """① 데이터 정제 통과율 = (clean 건수 / raw 건수) * 100"""
    raw_count = _raw_news_count(date_from, date_to)
    clean_count = sqlite_mgr.get_clean_news_count(date_from, date_to)
    rate = round((clean_count / raw_count) * 100, 2) if raw_count else None
    return {"raw_count": raw_count, "clean_count": clean_count, "rate": rate}


def show_quality_metrics(date_from=None, date_to=None):
    """품질 지표(정제 통과율, AI 요약 성공률)를 조회하여 출력합니다."""
    cleanliness = get_cleanliness_rate(date_from, date_to)
    summarize = sqlite_mgr.get_summarize_success_rate(date_from, date_to)

    print(f"\n{ui.HL}[ 품질 지표 ]{ui.FG}")
    print(f"  ① 데이터 정제 통과율 (Cleanliness Rate)")
    if cleanliness["rate"] is None:
        print(f"     raw 데이터가 없어 계산할 수 없습니다. (clean: {cleanliness['clean_count']}건)")
    else:
        print(f"     raw {cleanliness['raw_count']}건 → clean {cleanliness['clean_count']}건 "
              f"= {cleanliness['rate']}%")

    print(f"\n  ② AI 요약 성공률 (Summarize Success Rate)")
    print(f"     시도 대상 {summarize['total_target']}건 중 성공 {summarize['success_count']}건 "
          f"= {summarize['rate']}%")

    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def show_top_n(date_from=None, date_to=None):
    """TOP N 집계(핵심 키워드 TOP5, 카테고리별 수집량 TOP3)를 조회하여 출력합니다."""
    keyword_top5 = sqlite_mgr.get_keyword_top_n(5, date_from, date_to)
    category_top3 = sqlite_mgr.get_category_top_n(3, date_from, date_to)

    print(f"\n{ui.HL}[ TOP N 집계 ]{ui.FG}")
    print("  ① 최다 출현 핵심 키워드 TOP 5")
    if keyword_top5:
        for rank, (keyword, cnt) in enumerate(keyword_top5, start=1):
            print(f"     {rank}. {keyword} ({cnt}회)")
    else:
        print("     집계할 ai_insight 데이터가 없습니다.")

    print("\n  ② 카테고리별 뉴스 수집량 TOP 3")
    if category_top3:
        for rank, row in enumerate(category_top3, start=1):
            print(f"     {rank}. {row['category']} ({row['cnt']}건)")
    else:
        print("     집계할 clean_news 데이터가 없습니다.")

    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def _reports_dir():
    cfg = config_mgr.load_config()
    reports_dir = cfg.get("report_path", "./reports")
    os.makedirs(reports_dir, exist_ok=True)
    return reports_dir


def build_report_content(date_from=None, date_to=None, fmt="console"):
    """
    품질 지표 + TOP N 집계를 하나의 종합 리포트 텍스트로 구성합니다.
    fmt="md" 인 경우 마크다운 헤더/목록 문법으로, 그 외에는 콘솔/txt 겸용 평문으로 구성합니다.
    """
    cleanliness = get_cleanliness_rate(date_from, date_to)
    summarize = sqlite_mgr.get_summarize_success_rate(date_from, date_to)
    category_top3 = sqlite_mgr.get_category_top_n(3, date_from, date_to)
    keyword_top5 = sqlite_mgr.get_keyword_top_n(5, date_from, date_to)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if date_from and date_to:
        period = f"{date_from} ~ {date_to}"
    elif date_from:
        period = f"{date_from} 이후"
    elif date_to:
        period = f"{date_to} 이전"
    else:
        period = "전체 기간"

    cleanliness_line = (
        "raw 데이터가 없어 계산할 수 없습니다."
        if cleanliness["rate"] is None
        else f"raw {cleanliness['raw_count']}건 → clean {cleanliness['clean_count']}건 = {cleanliness['rate']}%"
    )
    summarize_line = (
        f"시도 대상 {summarize['total_target']}건 중 성공 {summarize['success_count']}건 "
        f"= {summarize['rate']}%"
    )
    keyword_lines = (
        [f"{i}. {kw} ({cnt}회)" for i, (kw, cnt) in enumerate(keyword_top5, start=1)]
        or ["집계할 ai_insight 데이터가 없습니다."]
    )
    category_lines = (
        [f"{i}. {row['category']} ({row['cnt']}건)" for i, row in enumerate(category_top3, start=1)]
        or ["집계할 clean_news 데이터가 없습니다."]
    )

    lines = []
    if fmt == "md":
        lines.append("# 코디세이 뉴스 데이터 분석 리포트")
        lines.append(f"- 생성 시각: {now}")
        lines.append(f"- 집계 기간: {period}")
        lines.append("")
        lines.append("## 1. 품질 지표")
        lines.append(f"- ① 데이터 정제 통과율: {cleanliness_line}")
        lines.append(f"- ② AI 요약 성공률: {summarize_line}")
        lines.append("")
        lines.append("## 2. TOP N 집계")
        lines.append("### 최다 출현 핵심 키워드 TOP 5")
        lines += [f"- {line}" for line in keyword_lines]
        lines.append("")
        lines.append("### 카테고리별 뉴스 수집량 TOP 3")
        lines += [f"- {line}" for line in category_lines]
    else:
        lines.append("=" * 60)
        lines.append("코디세이 뉴스 데이터 분석 리포트".center(52))
        lines.append("=" * 60)
        lines.append(f"생성 시각: {now}")
        lines.append(f"집계 기간: {period}")
        lines.append("-" * 60)
        lines.append("[ 품질 지표 ]")
        lines.append(f"  ① 데이터 정제 통과율: {cleanliness_line}")
        lines.append(f"  ② AI 요약 성공률   : {summarize_line}")
        lines.append("-" * 60)
        lines.append("[ TOP N 집계 ]")
        lines.append("  최다 출현 핵심 키워드 TOP 5")
        lines += [f"    {line}" for line in keyword_lines]
        lines.append("  카테고리별 뉴스 수집량 TOP 3")
        lines += [f"    {line}" for line in category_lines]
        lines.append("=" * 60)

    return "\n".join(lines)


def save_report_file(content, fmt):
    ext = "md" if fmt == "md" else "txt"
    filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    path = os.path.join(_reports_dir(), filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def run_report(date_from=None, date_to=None, fmt="console"):
    """종합 리포트를 생성합니다. console 형식은 화면에 출력만, txt/md 형식은 파일로 저장합니다."""
    content = build_report_content(date_from, date_to, fmt)

    if fmt == "console":
        logger.info(f"종합 리포트 콘솔 조회 (조회 기간: {date_from}~{date_to})")
        print(f"\n{ui.HL}{content}{ui.FG}")
    else:
        path = save_report_file(content, fmt)
        logger.info(f"종합 리포트 파일({fmt.upper()}) 저장 완료: {path}")
        print(f"\n{ui.HL}>> {fmt.upper()} 리포트 파일이 저장되었습니다.{ui.FG}")
        print(f"   저장 경로: {path}")

    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_report_cli(command_str):
    """'report --format md --date-from 2026-08-01 --date-to 2026-08-07' 형태의 입력을 파싱해 실행합니다."""
    try:
        args_list = shlex.split(command_str)
        args, unknown = report_parser.parse_known_args(args_list[1:])

        if unknown:
            print(f"\n알 수 없는 옵션이 포함되어 있습니다: {unknown}")
            ui.pause("[Enter]를 눌러 돌아갑니다...")
            return

        run_report(args.date_from, args.date_to, args.format)

    except SystemExit:
        logger.warning(f"잘못된 형식의 옵션이 입력되어 리포트 생성을 취소합니다. 명령어: {command_str}")
        print("\n[오류] '--format' 옵션은 console, txt, md 중 하나여야 합니다.")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
    except Exception as e:
        logger.error(f"명령어 파싱 중 오류 발생: {e}")
        print(f"\n[오류] 명령어 파싱 중 에러 발생: {e}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")


def run_report_interactive():
    print(f"\n{ui.HL}[ 대화형 리포트 생성 설정 ]{ui.FG}")
    print("안내: 입력을 취소하고 메뉴로 돌아가려면 언제든 'q'를 입력하세요.\n")

    fmt = input("▶ 출력 형식 입력 (console/txt/md, 기본 console) [q:취소]: ")
    if fmt and fmt.lower() == 'q':
        return
    fmt = fmt.strip().lower() if fmt and fmt.strip() else "console"
    if fmt not in ("console", "txt", "md"):
        print(f"\n{ui.ERR}[오류] 지원하지 않는 형식입니다: {fmt}{ui.FG}")
        ui.pause("[Enter]를 눌러 돌아갑니다...")
        return

    date_from = input("▶ 집계 시작일 입력 (예: 2026-08-01, 건너뛰려면 Enter) [q:취소]: ")
    if date_from and date_from.lower() == 'q':
        return
    date_to = input("▶ 집계 종료일 입력 (예: 2026-08-07, 건너뛰려면 Enter) [q:취소]: ")
    if date_to and date_to.lower() == 'q':
        return

    run_report(date_from.strip() or None if date_from else None,
               date_to.strip() or None if date_to else None,
               fmt)


def _prompt_optional_date_range():
    """대화형 메뉴에서 선택적으로 --date-from/--date-to를 입력받는다. 취소 시 None을 반환."""
    date_from = input("▶ 집계 시작일 입력 (예: 2026-08-01, 건너뛰려면 Enter) [q:취소]: ")
    if date_from and date_from.lower() == 'q':
        return None
    date_to = input("▶ 집계 종료일 입력 (예: 2026-08-07, 건너뛰려면 Enter) [q:취소]: ")
    if date_to and date_to.lower() == 'q':
        return None
    return (date_from.strip() or None if date_from else None,
            date_to.strip() or None if date_to else None)


def _generate_and_report(chart_func, label, date_from=None, date_to=None):
    try:
        path = chart_func(date_from, date_to)
        logger.info(f"시각화 차트 생성 완료 ({label}): {path}")
        print(f"\n{ui.HL}>> {label}이(가) 생성되었습니다.{ui.FG}")
        print(f"   저장 경로: {path}")
    except Exception as e:
        logger.error(f"시각화 차트('{label}') 렌더링/저장 중 오류 발생: {e}")
        print(f"\n{ui.ERR}[오류] 차트 생성 중 문제가 발생했습니다: {e}{ui.FG}")
    ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")


def run_menu_show():
    while True:
        ui.clear_screen()
        w = ui.get_width()

        ui.draw_header(" 품질 지표 및 시각화 차트 출력 (Report) 제어소 ")
        print(f"{ui.FG}  matplotlib 기반 차트를 생성하여 PNG 파일로 저장합니다.\n")

        print(f"{ui.HL}  [ 메뉴 ]{ui.FG}")

        print("\n  1. 카테고리별 뉴스 건수 차트 생성")
        print("  2. 일자별 뉴스 수집 추이 차트 생성")
        print("  3. 감성 분포 차트 생성")
        print("  4. 전체 차트 일괄 생성")
        ui.draw_line("─")
        print("  5. 품질 지표 조회 (정제 통과율, AI 요약 성공률)")
        print("  6. TOP N 집계 조회 (핵심 키워드 TOP5, 카테고리 TOP3)")
        ui.draw_line("─")
        print("  7. 종합 리포트 생성 (대화형 파라미터 입력)")
        ui.draw_line("─")
        print("  p. 이전 메뉴로 돌아가기 (상위 메뉴)\n")

        print(f"{ui.HL}  [ CLI 입력 (H : 도움말) ]{ui.FG}")
        print("  report [--date-from YYYY-MM-DD] [--date-to YYYY-MM-DD] [--format console|txt|md]")
        print("  (입력 예: report --format md --date-from 2026-08-01 --date-to 2026-08-07)")

        print("-" * w)
        choice = input(f"\n{ui.HL}Codyssey/report > {ui.FG}").strip().lower()

        if choice == 'p':
            break
        elif choice == 'h':
            help_mgr.show_help("report")
        elif choice == '1':
            date_range = _prompt_optional_date_range()
            if date_range is not None:
                _generate_and_report(chart_category_distribution, "카테고리별 뉴스 건수 차트", *date_range)
        elif choice == '2':
            date_range = _prompt_optional_date_range()
            if date_range is not None:
                _generate_and_report(chart_daily_trend, "일자별 뉴스 수집 추이 차트", *date_range)
        elif choice == '3':
            date_range = _prompt_optional_date_range()
            if date_range is not None:
                _generate_and_report(chart_sentiment_distribution, "감성 분포 차트", *date_range)
        elif choice == '4':
            date_range = _prompt_optional_date_range()
            if date_range is not None:
                date_from, date_to = date_range
                try:
                    paths = [chart_category_distribution(date_from, date_to),
                             chart_daily_trend(date_from, date_to),
                             chart_sentiment_distribution(date_from, date_to)]
                    logger.info(f"전체 시각화 차트 {len(paths)}건 일괄 생성 완료")
                    print(f"\n{ui.HL}>> 차트 {len(paths)}건이 생성되었습니다.{ui.FG}")
                    for path in paths:
                        print(f"   - {path}")
                except Exception as e:
                    logger.error(f"전체 시각화 차트 일괄 생성 중 오류 발생: {e}")
                    print(f"\n{ui.ERR}[오류] 차트 생성 중 문제가 발생했습니다: {e}{ui.FG}")
                ui.pause("\n[Enter]를 눌러 메뉴로 돌아갑니다...")
        elif choice == '5':
            date_range = _prompt_optional_date_range()
            if date_range is not None:
                show_quality_metrics(*date_range)
        elif choice == '6':
            date_range = _prompt_optional_date_range()
            if date_range is not None:
                show_top_n(*date_range)
        elif choice == '7':
            run_report_interactive()
        elif choice.startswith("report"):
            run_report_cli(choice)
        else:
            print("\n올바르지 않은 명령어나 번호입니다.")
            ui.pause("다시 시도하려면 [Enter]를 누르세요...")

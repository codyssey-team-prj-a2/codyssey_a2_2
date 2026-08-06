"""report: 품질 지표 + TOP N 집계 + AI 인사이트를 콘솔/파일(txt·md)로 출력한다."""
import json
from datetime import datetime, timezone
from pathlib import Path

from src import db, prompt, raw_store, ui, visualizer
from src.logger import get_logger

log = get_logger("reporter")

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"

TOP_N = 5


def _raw_matches(record: dict, date_from, date_to, category) -> bool:
    published = (record.get("published_at") or "")[:10]
    if date_from and published < date_from:
        return False
    if date_to and published > date_to:
        return False
    if category and record.get("category") != category:
        return False
    return True


def _gather(date_from: str | None, date_to: str | None, category: str | None) -> dict:
    db.init_db()
    raw_records = raw_store.read_all()
    if date_from or date_to or category:
        raw_records = [r for r in raw_records if _raw_matches(r, date_from, date_to, category)]
    raw_total = len(raw_records)
    clean_total = db.count_news(date_from=date_from, date_to=date_to, category=category)
    summarized_total = db.count_news(
        date_from=date_from, date_to=date_to, category=category, status="summarized"
    )

    clean_rate = (clean_total / raw_total * 100) if raw_total else 0.0
    summarize_rate = (summarized_total / clean_total * 100) if clean_total else 0.0

    where_sql, params = db.build_filter_sql(date_from, date_to, category, None, None, None)
    conn = db.get_connection()
    try:
        top_categories = conn.execute(
            "SELECT category, COUNT(*) AS cnt FROM news WHERE 1=1" + where_sql +
            " GROUP BY category ORDER BY cnt DESC LIMIT ?",
            params + [TOP_N],
        ).fetchall()
    finally:
        conn.close()

    latest_analysis = db.get_latest_analysis()

    scope = []
    if date_from or date_to:
        scope.append(f"기간: {date_from or '전체'} ~ {date_to or '전체'}")
    if category:
        scope.append(f"카테고리: {category}")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": ", ".join(scope) if scope else "전체",
        "raw_total": raw_total,
        "clean_total": clean_total,
        "summarized_total": summarized_total,
        "clean_rate": clean_rate,
        "summarize_rate": summarize_rate,
        "top_categories": [(r["category"] or "미분류", r["cnt"]) for r in top_categories],
        "latest_analysis": latest_analysis,
    }


def _render_md(data: dict, chart_paths: list[Path]) -> str:
    clean_detail = f"raw {data['raw_total']}건 중 clean {data['clean_total']}건"
    summarize_detail = f"clean {data['clean_total']}건 중 {data['summarized_total']}건 요약"
    lines = [
        "# 뉴스 AI 파이프라인 리포트",
        f"생성일시: {data['generated_at']}",
        f"범위: {data['scope']}",
        "",
        "## 품질 지표",
        f"- 정제율: {data['clean_rate']:.1f}% ({clean_detail})",
        f"- 요약 완료율: {data['summarize_rate']:.1f}% ({summarize_detail})",
        "",
        f"## TOP {TOP_N} 카테고리",
    ]
    for i, (cat, cnt) in enumerate(data["top_categories"], start=1):
        lines.append(f"{i}. {cat} - {cnt}건")

    lines += ["", "## AI 인사이트 (최근 분석 결과)"]
    if data["latest_analysis"]:
        a = data["latest_analysis"]
        trends = json.loads(a["trends"] or "[]")
        keywords = json.loads(a["keywords"] or "[]")
        lines += ["**주요 트렌드**"] + [f"- {t}" for t in trends]
        lines += ["", "**핵심 키워드**", ", ".join(keywords)]
        lines += ["", "**시사점**", a["implications"] or ""]
    else:
        lines.append("아직 analyze 명령을 실행하지 않았습니다.")

    lines += ["", "## 차트"] + [f"- {p.relative_to(BASE_DIR).as_posix()}" for p in chart_paths]
    return "\n".join(lines)


def _render_txt(data: dict, chart_paths: list[Path]) -> str:
    clean_detail = f"raw {data['raw_total']}건 중 clean {data['clean_total']}건"
    summarize_detail = f"clean {data['clean_total']}건 중 {data['summarized_total']}건 요약"
    lines = [
        "=== 뉴스 AI 파이프라인 리포트 ===",
        f"생성일시: {data['generated_at']}",
        f"범위: {data['scope']}",
        "",
        "[품질 지표]",
        f"정제율: {data['clean_rate']:.1f}% ({clean_detail})",
        f"요약 완료율: {data['summarize_rate']:.1f}% ({summarize_detail})",
        "",
        f"[TOP {TOP_N} 카테고리]",
    ]
    for i, (cat, cnt) in enumerate(data["top_categories"], start=1):
        lines.append(f"{i}. {cat} - {cnt}건")

    lines += ["", "[AI 인사이트]"]
    if data["latest_analysis"]:
        a = data["latest_analysis"]
        trends = json.loads(a["trends"] or "[]")
        keywords = json.loads(a["keywords"] or "[]")
        lines += ["주요 트렌드: " + "; ".join(trends)]
        lines += ["핵심 키워드: " + ", ".join(keywords)]
        lines += ["시사점: " + (a["implications"] or "")]
    else:
        lines.append("아직 analyze 명령을 실행하지 않았습니다.")

    lines += ["", "[차트]"] + [f"- {p.relative_to(BASE_DIR).as_posix()}" for p in chart_paths]
    return "\n".join(lines)


def run_report(
    fmt: str = "md",
    output: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    category: str | None = None,
) -> None:
    data = _gather(date_from, date_to, category)
    chart_paths = visualizer.run_visualize()
    content = _render_md(data, chart_paths) if fmt == "md" else _render_txt(data, chart_paths)

    ui.print_panel(content, title="리포트 미리보기")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if output:
        out_path = Path(output)
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = REPORTS_DIR / f"report_{ts}.{fmt}"
    out_path.write_text(content, encoding="utf-8")

    log.info(f"리포트 생성: {out_path}")
    ui.print_success(f"리포트 저장 완료: {out_path}")


def run_history() -> None:
    """생성된 리포트 파일 목록을 화면 번호로 골라 내용을 볼 수 있게 한다."""
    files = sorted(REPORTS_DIR.glob("report_*.*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        ui.print_warning("아직 생성된 리포트가 없습니다.")
        return
    while True:
        ui.print_file_table("생성된 리포트 목록", files)
        raw = prompt.ask_text("내용 볼 번호 (엔터=뒤로가기)", default="").strip()
        if not raw:
            return
        if raw.isdigit() and 1 <= int(raw) <= len(files):
            path = files[int(raw) - 1]
            ui.print_panel(path.read_text(encoding="utf-8"), title=path.name)
        else:
            ui.print_error("올바른 번호를 입력하세요.")

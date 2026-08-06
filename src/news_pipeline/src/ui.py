"""화면 출력 전용 (rich). 파일 로그는 logger.py가 담당한다."""
from datetime import datetime
from pathlib import Path

from rich import box
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

console = Console()


_CATEGORY_COLORS = ["cyan", "magenta", "yellow", "green", "blue", "bright_red"]
_category_color_cache: dict[str, str] = {}


def category_badge(category: str | None) -> str:
    name = category or "미분류"
    color = _category_color_cache.setdefault(
        name, _CATEGORY_COLORS[len(_category_color_cache) % len(_CATEGORY_COLORS)]
    )
    return f"[{color}]{name}[/{color}]"


def yes_no_badge(value: bool) -> str:
    return "[bold green]Y[/bold green]" if value else "[dim]N[/dim]"


def print_table(title: str, columns: list[str], rows: list[list]) -> None:
    table = Table(title=title, show_lines=False)
    for col in columns:
        # 헤더가 잘리지 않을 만큼은 항상 확보하고, 긴 본문(URL/제목)만 말줄임표로 자른다.
        table.add_column(
            col, overflow="ellipsis", no_wrap=True, min_width=len(col) + 2, max_width=42
        )
    for row in rows:
        table.add_row(*[str(c) for c in row])
    console.print(table)


def print_panel(text: str, title: str | None = None, style: str = "cyan") -> None:
    console.print(Panel(text, title=title, border_style=style))


def print_banner(title: str, subtitle: str | None = None) -> None:
    console.print(
        Panel(
            f"[bold cyan]{title}[/bold cyan]",
            subtitle=f"[dim]{subtitle}[/dim]" if subtitle else None,
            box=box.DOUBLE,
            border_style="cyan",
            padding=(0, 2),
        )
    )


def print_file_table(title: str, paths: list[Path]) -> None:
    """파일 목록을 번호/파일명/생성일시/크기 표로 보여준다 (히스토리 조회용)."""
    rows = []
    for i, p in enumerate(paths, start=1):
        stat = p.stat()
        mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size_kb = f"{stat.st_size / 1024:.1f} KB"
        rows.append([i, p.name, mtime, size_kb])
    print_table(title, ["번호", "파일명", "생성일시", "크기"], rows)


def print_section(title: str) -> None:
    console.rule(f"[bold cyan]{title}[/bold cyan]", style="cyan")


def print_success(msg: str) -> None:
    console.print(f"[bold green]완료[/bold green] {msg}")


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow]경고[/bold yellow] {msg}")


def print_error(msg: str) -> None:
    console.print(f"[bold red]오류[/bold red] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[bold cyan]안내[/bold cyan] {msg}")


def progress_bar() -> Progress:
    """여러 태스크를 동시에 보여줄 수 있는 진행바.

    태스크별 설명은 add_task(description, ...)로 준다
    (이전엔 설명이 Progress 생성 시점에 고정돼 있어서 태스크마다 다른 설명을 못 보여줬음).
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    )

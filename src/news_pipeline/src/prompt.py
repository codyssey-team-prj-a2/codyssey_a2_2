"""대화형 입력 공통 모듈.

기본은 questionary(화살표로 고르는 메뉴)를 쓴다. 다만 화살표 메뉴는 진짜 Windows
콘솔 화면 버퍼가 있어야 동작하는데(cmd.exe/PowerShell/Windows Terminal 등),
Git Bash/MSYS 같은 일부 터미널에서는 이게 없어서 questionary가 아예 뜨지 못한다.
그런 환경에서는 자동으로 rich 기반 번호 입력 방식으로 대체한다 — 화면이 안 뜨는 것보다
번호를 타이핑하는 게 훨씬 낫기 때문이다.

모든 프롬프트는 사용자가 Ctrl+C로 취소하면 Cancelled 예외를 던진다.
"""
import getpass as _getpass

import questionary
from questionary import Style
from rich.prompt import Confirm, IntPrompt, Prompt

from src import ui

BACK = "__back__"

QSTYLE = Style([
    ("qmark", "fg:#00afff bold"),
    ("question", "bold"),
    ("pointer", "fg:#00afff bold"),
    ("highlighted", "fg:#00afff bold"),
    ("selected", "fg:#00afff bold"),
    ("answer", "fg:#00afff bold"),
])

# None=아직 모름(첫 시도 전), True/False=이번 실행에서 화살표 메뉴 지원 여부(한 번 확인 후 재사용)
_arrow_supported: bool | None = None


class Cancelled(Exception):
    """사용자가 입력을 취소(Ctrl+C)했을 때 발생."""


def _mark_supported() -> None:
    global _arrow_supported
    _arrow_supported = True


def _mark_unsupported() -> None:
    global _arrow_supported
    if _arrow_supported is None:
        ui.print_warning(
            "이 터미널에서는 화살표 메뉴를 표시할 수 없어 번호 입력 방식으로 대체합니다 "
            "(PowerShell/명령 프롬프트에서 직접 실행하면 화살표 메뉴를 쓸 수 있어요)."
        )
    _arrow_supported = False


def ask_select(
    message: str,
    choices: list[tuple[str, str]],
    allow_back: bool = True,
    back_label: str = "뒤로가기",
) -> str:
    """choices: (값, 화면표시라벨) 목록. 뒤로가기/취소를 고르면 BACK을 반환한다.

    뒤로가기는 항목 수와 상관없이 항상 단축키/번호 0번으로 고정한다
    (모든 하위 메뉴에서 '0. 뒤로가기'로 통일하기 위함).
    """
    items = list(choices)
    if allow_back:
        items = items + [(BACK, back_label)]

    if _arrow_supported is not False:
        try:
            q_choices = [
                questionary.Choice(
                    title=label, value=value, shortcut_key="0" if value == BACK else True
                )
                for value, label in items
            ]
            result = questionary.select(
                message, choices=q_choices, style=QSTYLE,
                use_shortcuts=True, use_arrow_keys=True,
            ).ask()
            _mark_supported()
            if result is None:
                raise Cancelled()
            return result
        except Cancelled:
            raise
        except Exception:
            _mark_unsupported()

    return _fallback_select(message, items)


def _fallback_select(message: str, items: list[tuple[str, str]]) -> str:
    real_items = [it for it in items if it[0] != BACK]
    back_item = next((it for it in items if it[0] == BACK), None)

    for i, (_, label) in enumerate(real_items, start=1):
        ui.console.print(f"  [cyan]{i}.[/cyan] {label}")
    valid = [str(i) for i in range(1, len(real_items) + 1)]
    if back_item:
        ui.console.print(f"  [cyan]0.[/cyan] {back_item[1]}")
        valid.append("0")

    try:
        raw = Prompt.ask(message, choices=valid, show_choices=False)
    except KeyboardInterrupt:
        raise Cancelled() from None
    if raw == "0" and back_item:
        return BACK
    return real_items[int(raw) - 1][0]


def ask_text(message: str, default: str = "") -> str:
    if _arrow_supported is not False:
        try:
            result = questionary.text(message, default=default, style=QSTYLE).ask()
            _mark_supported()
            if result is None:
                raise Cancelled()
            return result
        except Cancelled:
            raise
        except Exception:
            _mark_unsupported()

    try:
        return Prompt.ask(message, default=default)
    except KeyboardInterrupt:
        raise Cancelled() from None


def ask_int(message: str, default: int) -> int:
    if _arrow_supported is not False:
        try:
            result = questionary.text(
                message, default=str(default), style=QSTYLE,
                validate=lambda v: v.strip().isdigit() or "숫자를 입력하세요.",
            ).ask()
            _mark_supported()
            if result is None:
                raise Cancelled()
            return int(result)
        except Cancelled:
            raise
        except Exception:
            _mark_unsupported()

    try:
        return IntPrompt.ask(message, default=default)
    except KeyboardInterrupt:
        raise Cancelled() from None


def ask_confirm(message: str, default: bool = False) -> bool:
    if _arrow_supported is not False:
        try:
            result = questionary.confirm(message, default=default, style=QSTYLE).ask()
            _mark_supported()
            if result is None:
                raise Cancelled()
            return result
        except Cancelled:
            raise
        except Exception:
            _mark_unsupported()

    try:
        return Confirm.ask(message, default=default)
    except KeyboardInterrupt:
        raise Cancelled() from None


def ask_password(message: str) -> str:
    if _arrow_supported is not False:
        try:
            result = questionary.password(message, style=QSTYLE).ask()
            _mark_supported()
            if result is None:
                raise Cancelled()
            return result
        except Cancelled:
            raise
        except Exception:
            _mark_unsupported()

    try:
        return _getpass.getpass(message + ": ")
    except KeyboardInterrupt:
        raise Cancelled() from None

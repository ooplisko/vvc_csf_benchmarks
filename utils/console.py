from __future__ import annotations

from collections.abc import Iterable


def print_section(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def format_bool(value: bool) -> str:
    return "PASS" if value else "FAIL"


def print_table(headers: list[str], rows: Iterable[Iterable[object]]) -> None:
    rendered_rows = [[str(cell) for cell in row] for row in rows]
    widths = [len(header) for header in headers]
    for row in rendered_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))

    template = "  " + "  ".join(f"{{:<{width}}}" for width in widths)
    print(template.format(*headers))
    print(template.format(*["-" * width for width in widths]))
    for row in rendered_rows:
        print(template.format(*row))

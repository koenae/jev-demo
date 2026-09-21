"""Pull code fragments for the slides straight out of the real demo modules.

Nothing on a slide is retyped: `source_of` uses `inspect.getsource` on the actual
function, `constant_source` cuts a module-level assignment out of the module file.
"""

from __future__ import annotations

import inspect
import re
from types import ModuleType
from typing import Any

MAX_LINES = 15


def _strip_docstring(lines: list[str]) -> list[str]:
    """Drop a docstring directly after a def/class line, to save slide space."""
    if len(lines) < 2:
        return lines
    body = lines[1:]
    first = body[0].strip()
    if not (first.startswith('"""') or first.startswith("'''")):
        return lines
    quote = first[:3]
    if first.count(quote) >= 2 and len(first) > 3:  # one-line docstring
        return [lines[0], *body[1:]]
    for i, line in enumerate(body[1:], start=1):
        if quote in line:
            return [lines[0], *body[i + 1 :]]
    return lines


def source_of(obj: Any, *, max_lines: int = MAX_LINES, keep_docstring: bool = False) -> str:
    lines = inspect.getsource(obj).rstrip().splitlines()
    if not keep_docstring:
        lines = _strip_docstring(lines)
    lines = [line for line in lines if not line.strip().startswith("# type:")]
    if len(lines) > max_lines:
        lines = lines[: max_lines - 1] + ["    # ..."]
    return "\n".join(lines)


def constant_source(module: ModuleType, name: str, *, max_lines: int = MAX_LINES) -> str:
    """Return the source of `NAME = ...` (multi-line, bracket-balanced) from a module."""
    lines = inspect.getsource(module).splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(rf"^{name}\s*[:=]", line))
    depth = 0
    block: list[str] = []
    for line in lines[start:]:
        block.append(line)
        depth += line.count("(") + line.count("[") + line.count("{")
        depth -= line.count(")") + line.count("]") + line.count("}")
        if depth <= 0:
            break
    if len(block) > max_lines:
        block = block[: max_lines - 1] + ["    # ..."]
    return "\n".join(block)

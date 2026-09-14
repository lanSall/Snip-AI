"""Turn a model reply into a short toast line and a clipboard-ready full answer."""

from __future__ import annotations

import re

_ANSWER_RE = re.compile(
    r"^\s*(?:ANSWER|Answer)\s*[:\-]\s*(.+?)\s*$",
    re.MULTILINE,
)
_WHY_RE = re.compile(
    r"^\s*(?:WHY|Why|Explanation)\s*[:\-]\s*(.+?)\s*$",
    re.MULTILINE,
)


def parse_solution(text: str) -> tuple[str, str]:
    """Return ``(headline, full_text)``.

    Prefers an ``ANSWER:`` line when the model followed the prompt. Otherwise
    the first non-empty line is the headline.
    """
    full = (text or "").strip()
    if not full:
        return "No answer", ""

    answer_match = _ANSWER_RE.search(full)
    if answer_match:
        headline = answer_match.group(1).strip()
        return headline or full.splitlines()[0], full

    for line in full.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped, full
    return full, full


def compact(text: str, max_chars: int = 180) -> str:
    """Collapse extra spaces and truncate for a small toast. Keeps newlines."""
    lines = [" ".join(line.split()) for line in (text or "").splitlines()]
    collapsed = "\n".join(line for line in lines if line)
    if max_chars <= 0 or len(collapsed) <= max_chars:
        return collapsed
    if max_chars == 1:
        return "…"
    return collapsed[: max_chars - 1].rstrip() + "…"


def toast_body(text: str, max_chars: int = 180) -> str:
    headline, full = parse_solution(text)
    why = _WHY_RE.search(full)
    if why:
        body = f"{headline}\n{why.group(1).strip()}"
    else:
        body = headline
    return compact(body, max_chars=max_chars)

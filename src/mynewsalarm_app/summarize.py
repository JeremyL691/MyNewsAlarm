from __future__ import annotations

import re
from html import unescape

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = unescape(text)
    text = _TAGS.sub(" ", text)
    text = _WS.sub(" ", text).strip()
    return text


def sentences(text: str) -> list[str]:
    text = strip_html(text)
    if not text:
        return []
    parts = _SENTENCE_SPLIT.split(text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if len(p) < 25:
            continue
        out.append(p)
    return out


def summarize_text(text: str, max_sentences: int = 4) -> str:
    sents = sentences(text)
    if not sents:
        return ""
    return " ".join(sents[:max_sentences])


def pick_best_text(*candidates: str) -> str:
    best = ""
    for c in candidates:
        c = strip_html(c or "")
        if len(c) > len(best):
            best = c
    return best

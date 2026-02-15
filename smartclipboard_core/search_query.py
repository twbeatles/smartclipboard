from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class ParsedSearchQuery:
    query: str
    tag: str | None = None
    type: str | None = None  # normalized: text|image|link|code|color|file|all
    col: str | None = None
    is_bookmark: bool | None = None
    is_pinned: bool | None = None
    limit: int | None = None


_TOKEN_RE = re.compile(
    r"""
    (?P<key>tag|type|col|is|limit)
    :
    (?P<val>
        "(?:[^"\\]|\\.)*"   # "quoted value"
        |
        \S+                 # or single token
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _unquote(val: str) -> str:
    val = (val or "").strip()
    if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
        inner = val[1:-1]
        return inner.replace('\\"', '"')
    return val


def parse_search_query(text: str) -> ParsedSearchQuery:
    """Parse a mixed free-text + token query.

    Supported tokens (case-insensitive):
      - tag:<value>
      - type:<text|image|link|code|color|file|all>
      - col:<collection name>
      - is:<bookmark|pinned>
      - limit:<int>

    Everything that isn't a recognized token becomes the full-text `query`.
    """

    raw = (text or "").strip()
    if not raw:
        return ParsedSearchQuery(query="")

    tag: str | None = None
    typ: str | None = None
    col: str | None = None
    is_bookmark: bool | None = None
    is_pinned: bool | None = None
    limit: int | None = None

    consumed_spans: list[tuple[int, int]] = []
    for m in _TOKEN_RE.finditer(raw):
        key = (m.group("key") or "").strip().lower()
        val = _unquote(m.group("val") or "")
        if not val:
            continue

        if key == "tag":
            tag = val
        elif key == "type":
            v = val.lower()
            if v in {"text", "image", "link", "code", "color", "file", "all"}:
                typ = v
            elif v in {"txt"}:
                typ = "text"
        elif key == "col":
            col = val
        elif key == "is":
            v = val.lower()
            if v in {"bookmark", "bookmarked"}:
                is_bookmark = True
            elif v in {"pinned", "pin"}:
                is_pinned = True
        elif key == "limit":
            try:
                n = int(val)
            except ValueError:
                n = None
            if n is not None and n > 0:
                limit = n
        else:
            continue

        consumed_spans.append(m.span())

    # Remove consumed spans from raw to build remaining free-text query.
    if consumed_spans:
        consumed_spans.sort()
        parts: list[str] = []
        last = 0
        for a, b in consumed_spans:
            if a > last:
                parts.append(raw[last:a])
            last = max(last, b)
        if last < len(raw):
            parts.append(raw[last:])
        q = " ".join(p.strip() for p in parts if p.strip())
    else:
        q = raw

    return ParsedSearchQuery(
        query=q.strip(),
        tag=tag,
        type=typ,
        col=col,
        is_bookmark=is_bookmark,
        is_pinned=is_pinned,
        limit=limit,
    )


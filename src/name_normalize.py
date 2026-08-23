"""Player-name normalization and fuzzy proposal helpers (phase 3)."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """NFKD → strip accents → strip punctuation → collapse whitespace → lowercase.

    Also rewrites ``Last, First`` to ``First Last`` before punctuation strip.
    """
    text = (name or "").strip()
    if not text:
        return ""
    # Lastname, Firstname → Firstname Lastname
    if "," in text:
        left, right = text.split(",", 1)
        left, right = left.strip(), right.strip()
        if left and right:
            text = f"{right} {left}"
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_ish = "".join(c for c in decomposed if not unicodedata.combining(c))
    # Delete punctuation (do not replace with space) so A'ja → aja, not "a ja".
    no_punct = _PUNCT_RE.sub("", ascii_ish)
    collapsed = _SPACE_RE.sub(" ", no_punct).strip().lower()
    return collapsed


def name_tokens(normalized: str) -> list[str]:
    return [t for t in normalized.split(" ") if t]


def initial_lastname_key(normalized: str) -> tuple[str, str] | None:
    """Return (first_initial, last_token) for abbreviated forms like 'k plum'."""
    toks = name_tokens(normalized)
    if len(toks) < 2:
        return None
    first, *_, last = toks
    if not first or not last:
        return None
    return (first[0], last)


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def propose_fuzzy(
    raw_normalized: str,
    candidates: list[tuple[str, str]],
    *,
    limit: int = 5,
    min_score: float = 0.72,
) -> list[dict[str, str | float]]:
    """Propose fuzzy matches. ``candidates`` is (player_id, display_name).

    Never auto-accept — callers only print / persist proposals for approval.
    """
    scored: list[tuple[float, str, str]] = []
    raw_key = initial_lastname_key(raw_normalized)
    for player_id, display in candidates:
        norm = normalize_name(display)
        score = similarity(raw_normalized, norm)
        # Boost clear initial+lastname hits within a candidate pool
        if raw_key is not None:
            cand_key = initial_lastname_key(norm)
            if cand_key is not None and raw_key == cand_key:
                score = max(score, 0.9)
        if score >= min_score:
            scored.append((score, player_id, display))
    scored.sort(key=lambda x: (-x[0], x[2]))
    out: list[dict[str, str | float]] = []
    for score, player_id, display in scored[:limit]:
        out.append(
            {
                "player_id": player_id,
                "player_name": display,
                "score": round(score, 4),
            }
        )
    return out

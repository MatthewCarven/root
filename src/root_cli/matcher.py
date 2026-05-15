r"""Fuzzy subsequence matcher.

Inspired by fzf's algorithm, but much simpler. We score a candidate by:

- Subsequence match required (else score = -inf).
- Reward consecutive characters.
- Reward matches at word boundaries (/, \, _, -, ., space).
- Reward matches near the basename (rightmost component).
- Penalize gaps and unmatched length.
"""
from __future__ import annotations

from typing import List, Optional, Tuple


_WORD_BOUNDARIES = set("/\\ _-.")


def _is_boundary(prev):
    if prev is None:
        return True
    return prev in _WORD_BOUNDARIES


def score(query, target):
    if not query:
        return 0.0
    if not target:
        return float("-inf")

    case_sensitive = any(c.isupper() for c in query)
    q = query if case_sensitive else query.lower()
    t = target if case_sensitive else target.lower()

    score_val = 0.0
    streak = 0
    prev_idx = -1
    ti = 0
    for qc in q:
        found = -1
        for j in range(ti, len(t)):
            if t[j] == qc:
                found = j
                break
        if found < 0:
            return float("-inf")

        if found == prev_idx + 1:
            streak += 1
            score_val += 1.5 + 0.5 * streak
        else:
            streak = 0
            score_val += 1.0
            if prev_idx >= 0:
                gap = found - prev_idx - 1
                score_val -= 0.5 * gap

        prev_char = target[found - 1] if found > 0 else None
        if _is_boundary(prev_char):
            score_val += 2.0

        sep_pos = max(target.rfind("/"), target.rfind("\\"))
        if found > sep_pos:
            score_val += 1.0

        prev_idx = found
        ti = found + 1

    score_val -= 0.01 * (len(target) - len(q))
    return score_val


def best_score(query, fields):
    if not query:
        return 0.0
    best = float("-inf")
    for f in fields:
        s = score(query, f)
        if s > best:
            best = s
    return best


def filter_and_rank(query, items, limit=None):
    scored = []
    for _label, payload, fields in items:
        s = best_score(query, fields)
        if s == float("-inf"):
            continue
        scored.append((s, payload))
    scored.sort(key=lambda x: x[0], reverse=True)
    if limit is not None:
        scored = scored[:limit]
    return scored

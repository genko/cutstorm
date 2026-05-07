from __future__ import annotations

from typing import Sequence

from .models import Word

# Single-char sentence terminators. Three-dot "..." ends on ".", so it
# triggers a break via the same last-char rule — no special-case needed.
_SENTENCE_END = frozenset(".?!…")


def chunks_by_sentence(words: Sequence[Word], chunk_size: int) -> list[list[Word]]:
    """Group words into chunks of at most `chunk_size`, forcing a break
    after any word ending in sentence-final punctuation (. ? ! …).

    The next sentence always starts on a fresh chunk so end-of-sentence
    and start-of-next-sentence never share an on-screen window.
    """
    n = max(1, chunk_size)
    out: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        cur.append(w)
        text = (w.text or "").rstrip()
        sentence_end = bool(text) and text[-1] in _SENTENCE_END
        if sentence_end or len(cur) >= n:
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out

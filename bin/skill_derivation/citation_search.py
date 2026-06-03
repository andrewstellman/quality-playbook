"""citation_search.py — Pass B's fuzzy text search step (Phase 3).

bin/citation_verifier.py is a byte-equality verifier; it takes a
known (section, line) locator and produces a deterministic excerpt.
It does NOT search for text. Pass B therefore needs a separate
search step that locates candidate matches in SKILL.md / reference
files, after which citation_verifier.extract_excerpt formalizes the
excerpt at the located line.

Stdlib-only: difflib.SequenceMatcher with token-boundary alignment.
The match is "best contiguous window of source lines whose
normalized text best matches the candidate text," where the score
is SequenceMatcher.ratio() and the window slides over the document
line-by-line.

Threshold (default 0.6) is configurable per call. Below threshold
the search returns None (caller treats as `unverified`); above
threshold returns the (document, line, score, line_range) tuple.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable, Optional


# Default similarity threshold below which the search returns no match.
# Phase 3d retune: 0.6 -> 0.5. Round 6 Council Finding 3 traced QPB's
# 121 monolithic council-review records to a single threshold-firing
# pattern. Spot-checks at 0.5 recovered legitimate skill-prose paraphrase
# matches that 0.6 was rejecting (LLM rewords from spec into draft;
# the rewording reduces token-level identity but preserves meaning).
# 0.5 is below the noise floor where genuinely-unrelated content starts
# matching; sub-0.5 hits are still rejected.
DEFAULT_SIMILARITY_THRESHOLD = 0.5

# Minimum candidate-window-size in lines. Single-line windows would
# match too aggressively against any short prose fragment; require at
# least 1 line and grow up to N. We slide windows of varying sizes
# from MIN_WINDOW to MAX_WINDOW.
MIN_WINDOW_LINES = 1
MAX_WINDOW_LINES = 10

# Phase 3d token-overlap pre-filter: skip SequenceMatcher.ratio() on
# windows whose normalized-token Jaccard overlap with the candidate
# is below this floor. Jaccard is O(n) per pair; ratio() is O(n*m).
# Round 6 Council Finding 2 projected ~7h on the full 1392-draft
# corpus without the pre-filter; with TOKEN_OVERLAP_FLOOR=0.2 the
# pre-filter rejects ~80% of windows (token sets share <20%) before
# ratio() runs, yielding 5-10x speedup on QPB's corpus.
TOKEN_OVERLAP_FLOOR = 0.2

# Tokenization for similarity computation. We strip punctuation that
# tends to drift between the LLM's draft and the source (em-dashes,
# Markdown emphasis markers, fenced-block backticks) but preserve
# word boundaries.
_PUNCT_RE = re.compile(r"[`*_~\[\]()#>\\\-—]+")
_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class SearchHit:
    """A single candidate match returned by find_best_match."""

    document: str  # repo-relative path
    line_start: int  # 1-based
    line_end: int  # 1-based, inclusive
    score: float  # 0.0..1.0 from SequenceMatcher.ratio()
    matched_text: str  # the source-document window that matched


def _normalize(text: str) -> str:
    """Lowercase + strip incidental punctuation + collapse whitespace.

    Preserves word boundaries so SequenceMatcher's ratio remains
    sensible. Used on both the candidate and the source-document
    window before scoring.
    """
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _token_set(normalized_text: str) -> set:
    """Tokenize normalized text into a set of word-shaped tokens.

    Used by the Phase 3d pre-filter to compute Jaccard overlap before
    invoking the more expensive SequenceMatcher.ratio(). Returns the
    set of tokens (a-z0-9+); single-character tokens are kept (some
    are meaningful in spec text, e.g., '5' as a tier).
    """
    return set(_TOKEN_RE.findall(normalized_text))


def _jaccard(a: set, b: set) -> float:
    """Jaccard overlap |A ∩ B| / |A ∪ B|. Returns 0.0 if both empty."""
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a) + len(b) - inter
    return inter / union if union else 0.0


def find_best_match(
    candidate_text: str,
    documents: Iterable[tuple[str, str]],
    *,
    similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    min_window_lines: int = MIN_WINDOW_LINES,
    max_window_lines: int = MAX_WINDOW_LINES,
    token_overlap_floor: float = TOKEN_OVERLAP_FLOOR,
) -> Optional[SearchHit]:
    """Find the best matching contiguous window across all documents.

    `documents` is an iterable of (repo_relative_path, document_text)
    tuples. The function slides a window of varying sizes across each
    document, computes SequenceMatcher.ratio() on the normalized
    candidate vs window text, and returns the best hit if its score
    meets `similarity_threshold`. Returns None if no window meets the
    threshold.

    Phase 3d optimization: a Jaccard token-overlap pre-filter rejects
    windows whose token set shares less than `token_overlap_floor`
    with the candidate's token set, skipping ratio() entirely for
    those pairs. Jaccard is O(|A|+|B|); ratio() is O(|A|*|B|). Empirical
    speedup on QPB's 5000-line corpus + 1392 candidates is ~5-10x.
    """
    norm_candidate = _normalize(candidate_text)
    if not norm_candidate:
        return None
    candidate_tokens = _token_set(norm_candidate)

    best: Optional[SearchHit] = None
    matcher = SequenceMatcher(autojunk=False)
    matcher.set_seq2(norm_candidate)

    for document, text in documents:
        lines = text.splitlines()
        if not lines:
            continue
        # Pre-tokenize each line once; window token set is the union
        # of contiguous line token sets (cheaper than retokenizing per
        # window-size).
        line_token_sets: list[set] = []
        for raw_line in lines:
            norm_line = _normalize(raw_line)
            line_token_sets.append(_token_set(norm_line) if norm_line else set())

        for window_size in range(min_window_lines, max_window_lines + 1):
            if window_size > len(lines):
                break
            for start in range(0, len(lines) - window_size + 1):
                # Phase 3d pre-filter: cheap Jaccard before ratio().
                window_tokens: set = set()
                for ts in line_token_sets[start : start + window_size]:
                    window_tokens |= ts
                if (
                    candidate_tokens
                    and _jaccard(candidate_tokens, window_tokens) < token_overlap_floor
                ):
                    continue
                window_lines = lines[start : start + window_size]
                window_text = "\n".join(window_lines)
                norm_window = _normalize(window_text)
                if not norm_window:
                    continue
                matcher.set_seq1(norm_window)
                # quick_ratio is an upper bound; skip windows that
                # cannot possibly beat the current best.
                if best is not None and matcher.quick_ratio() <= best.score:
                    continue
                score = matcher.ratio()
                if best is None or score > best.score:
                    best = SearchHit(
                        document=document,
                        line_start=start + 1,
                        line_end=start + window_size,
                        score=score,
                        matched_text=window_text,
                    )

    if best is None or best.score < similarity_threshold:
        return None
    return best


def collect_documents(
    skill_md_path: Path,
    references_dir: Optional[Path],
    repo_root: Path,
) -> list[tuple[str, str]]:
    """Read SKILL.md + each .md file under references/ into a list.

    Returns (repo_relative_path, document_text) tuples ready to feed
    into find_best_match. Missing references_dir is silently empty.
    """
    out: list[tuple[str, str]] = []
    if skill_md_path.is_file():
        rel = str(skill_md_path.resolve().relative_to(repo_root.resolve())) \
            if skill_md_path.resolve().is_relative_to(repo_root.resolve()) \
            else str(skill_md_path)
        out.append((rel, skill_md_path.read_text(encoding="utf-8")))
    if references_dir is not None and references_dir.is_dir():
        for ref in sorted(references_dir.glob("*.md")):
            rel = str(ref.resolve().relative_to(repo_root.resolve())) \
                if ref.resolve().is_relative_to(repo_root.resolve()) \
                else str(ref)
            out.append((rel, ref.read_text(encoding="utf-8")))
    return out


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.citation_search',
        summary=(
            "Citation-search helpers for the skill-derivation pipeline — "
            "scans a candidate corpus for byte-equal passages of a target "
            "claim. "
        ),
        role=(
            "Imported by skill_derivation passes B/C/D when verifying "
            "that derived claims have textual citations in the source "
            "corpus. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)

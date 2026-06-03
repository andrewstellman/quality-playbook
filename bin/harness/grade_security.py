"""QPB Test Harness — security grader (Phase 2).

Answer-key-match grading per design §B / design §F/§4.2:
``DETECTED | PARTIAL | MISSED | BLOCKED``. The grader reads the
run's `quality/BUGS.md` and writeup files and matches against
the case's `answer_key` (CWE / file / symbol / behavior).

F-NOTES (LOCKED at design §F-note):

* **F-note 3**: ``BLOCKED`` (AUP/usage-policy stop in the
  stream) is graded **N/A**, NEVER ``MISSED``. The harness sees
  this via ``run_meta.blocked=True`` in the fact object.
* **F-note 4**: ``DETECTED`` / ``PARTIAL`` / ``MISSED`` require
  human review before they count (``reviewed:true`` in
  grading.json); auto-grade is the first pass. The verdict
  written to grading.json is always honest about that —
  ``reviewed:false`` until a human sets it.

Match policy (PARTIAL → DETECTED escalation):

* DETECTED: the agent's BUGS.md / writeups cite the planted
  ``file`` AND (``symbol`` OR a substring of ``behavior``).
* PARTIAL: the agent cites the ``file`` but not the
  ``symbol``/``behavior`` — close, but not a clean
  detection.
* MISSED: no citation of the file, symbol, or a behavior
  keyword.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from bin.harness.schema import (
    AnswerKey,
    Case,
    CaseType,
    RunFacts,
    SecurityOutcome,
)


class SecurityGraderError(RuntimeError):
    """Security grader misconfiguration (e.g. invoked on a
    non-security_eval case, or the run's quality/ tree is
    missing)."""


@dataclass
class SecurityGrading:
    """Top-level grading record per design §F/§4.2 + §7."""
    case_id: str
    run_id: str
    case_type: str = CaseType.SECURITY_EVAL.value
    outcome: str = SecurityOutcome.MISSED.value
    # Was the run BLOCKED by AUP/usage policy? If so the outcome
    # is `BLOCKED` and the grader emits "N/A" semantics
    # (F-note 3).
    blocked: bool = False
    # Per-criterion evidence so a human reviewer can audit the
    # auto-grade. Keys: file_cited, symbol_cited, behavior_cited.
    evidence: dict = field(default_factory=dict)
    reviewed: bool = False
    human_verdict: "str | None" = None
    # If `blocked=True` or no quality/ tree was available, the
    # grader records the reason so the receipt is auditable.
    note: "str | None" = None

    def to_json(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Evidence extraction from the run's quality/ artifacts
# ---------------------------------------------------------------------------


def _read_quality_text(quality_dir: Path) -> str:
    """Concatenate the text content of the run's quality
    artifacts that the agent uses to record findings: BUGS.md +
    every file under writeups/. Returns the concatenated text
    (or empty string if the tree is missing).

    F-note 3 motivation: the security grader's question is "did
    the agent identify the planted bug?" — the load-bearing
    artifacts are BUGS.md (the find list) and writeups (the
    explanations). The grader reads ONLY these; the stream /
    transcript is the live-behavior surface (handled by facts).
    """
    parts: list[str] = []
    bugs_md = quality_dir / "BUGS.md"
    if bugs_md.is_file():
        try:
            parts.append(bugs_md.read_text(encoding="utf-8",
                                             errors="ignore"))
        except OSError:
            pass
    writeups = quality_dir / "writeups"
    if writeups.is_dir():
        for entry in sorted(writeups.iterdir()):
            if entry.is_file():
                try:
                    parts.append(entry.read_text(
                        encoding="utf-8", errors="ignore",
                    ))
                except OSError:
                    pass
    return "\n".join(parts)


def _file_cited(text: str, answer_key: AnswerKey) -> bool:
    """True iff the BUGS.md / writeups text references the
    planted file (or any file in the legacy ``files`` list)."""
    file_paths: list[str] = []
    if answer_key.file:
        file_paths.append(answer_key.file)
    if answer_key.files:
        file_paths.extend(answer_key.files)
    # Match by basename OR full path — agents may shorten paths
    # in their narrative.
    for fp in file_paths:
        if not fp:
            continue
        # Full-path match.
        if fp in text:
            return True
        # Basename match (case-sensitive — paths are
        # case-sensitive on Linux/macOS; Windows tolerance is a
        # v1.6.x concern).
        basename = fp.rsplit("/", 1)[-1]
        if basename and basename in text:
            return True
    return False


def _symbol_cited(text: str, answer_key: AnswerKey) -> bool:
    """True iff a symbol from the answer key (symbol, locus, or
    pass_criterion) appears verbatim in the text."""
    candidates: list[str] = []
    for s in (answer_key.symbol, answer_key.locus,
               answer_key.pass_criterion):
        if s and s != "<unspecified>":
            candidates.append(s)
    for s in candidates:
        if s in text:
            return True
    # Also accept function-name-like tokens extracted from
    # `symbol` / `locus` (e.g. `PackageIndex._resolve_download_
    # filename / _download_url` → individual names).
    for s in candidates:
        for token in re.split(r"[/\s,]+", s):
            token = token.strip().strip(".()")
            # Heuristic: token must look like an identifier with
            # at least 6 chars to avoid matching common words.
            if (len(token) >= 6
                    and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*",
                                       token)):
                if token in text:
                    return True
    return False


def _behavior_cited(text: str, answer_key: AnswerKey,
                     min_keyword_len: int = 6) -> bool:
    """True iff a distinctive keyword from the behavior /
    mechanism / pass_criterion appears in the text.

    Heuristic: split the behavior string into tokens of length
    ≥ ``min_keyword_len``, drop very common words, and require
    at least 2 distinct tokens to match. This keeps a single
    word like "filename" from triggering a DETECTED on a
    coincidental match.
    """
    candidates: list[str] = []
    for s in (answer_key.behavior, answer_key.mechanism,
               answer_key.pass_criterion):
        if s and s != "<unspecified>":
            candidates.append(s)
    if not candidates:
        return False
    # Tokenize all keyword candidates.
    stopwords = {
        "function", "method", "without", "through", "between",
        "because", "should", "instead", "before", "after",
        "called", "passed", "passes", "called",
    }
    tokens: set[str] = set()
    for s in candidates:
        for tok in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", s):
            if len(tok) >= min_keyword_len and tok.lower() not in stopwords:
                tokens.add(tok)
    # Require ≥ 2 distinct tokens hit. (Single-token match is
    # easy to false-positive on common identifiers; two-token
    # match is the practical evidence threshold.)
    text_lower = text.lower()
    hits = sum(1 for t in tokens if t.lower() in text_lower)
    return hits >= 2


# ---------------------------------------------------------------------------
# Top-level grader
# ---------------------------------------------------------------------------


def grade_security(case: Case, facts: RunFacts, quality_dir: Path,
                    run_id: str) -> SecurityGrading:
    """Grade a security_eval case end-to-end.

    Routing:
    1. If ``facts.run_meta.blocked`` is True → outcome=BLOCKED,
       graded N/A (F-note 3).
    2. Else if ``quality_dir`` is missing → outcome=MISSED with
       a "no quality/ tree" note (the run didn't produce the
       canonical evidence surface; the grader treats this as
       a missed detection rather than a crash).
    3. Else read BUGS.md + writeups, check file-cited AND
       (symbol-cited OR behavior-cited).
       - both → DETECTED
       - file-cited only → PARTIAL
       - nothing → MISSED
    """
    if case.type != CaseType.SECURITY_EVAL:
        raise SecurityGraderError(
            f"grade_security called on non-security_eval case "
            f"{case.id} (type={case.type.value})"
        )
    if case.answer_key is None:
        raise SecurityGraderError(
            f"security case {case.id} has no answer_key"
        )
    grading = SecurityGrading(case_id=case.id, run_id=run_id)

    # ----- F-note 3: BLOCKED ⇒ N/A -----
    if facts.run_meta.blocked:
        grading.outcome = SecurityOutcome.BLOCKED.value
        grading.blocked = True
        grading.note = (
            "Run BLOCKED by AUP/usage-policy stop "
            f"({facts.run_meta.stop_reason!r}); graded N/A per "
            f"design §F-note F-note 3."
        )
        return grading

    # ----- Missing quality/ tree -----
    if not quality_dir.is_dir():
        grading.outcome = SecurityOutcome.MISSED.value
        grading.note = (
            f"quality/ tree absent at {quality_dir}; the run "
            f"did not produce the canonical evidence surface "
            f"(BUGS.md + writeups). Auto-graded MISSED; human "
            f"review may downgrade to N/A if the run never "
            f"started."
        )
        return grading

    # ----- Evidence -----
    text = _read_quality_text(quality_dir)
    if not text.strip():
        grading.outcome = SecurityOutcome.MISSED.value
        grading.note = (
            "quality/BUGS.md + writeups/ contain no text; "
            "agent produced no findings."
        )
        return grading
    file_hit = _file_cited(text, case.answer_key)
    symbol_hit = _symbol_cited(text, case.answer_key)
    behavior_hit = _behavior_cited(text, case.answer_key)
    grading.evidence = {
        "file_cited": file_hit,
        "symbol_cited": symbol_hit,
        "behavior_cited": behavior_hit,
        # Include answer key reference for the auditor.
        "answer_key": {
            "cwe": case.answer_key.cwe,
            "file": case.answer_key.file,
            "symbol": case.answer_key.symbol,
        },
    }
    if file_hit and (symbol_hit or behavior_hit):
        grading.outcome = SecurityOutcome.DETECTED.value
    elif file_hit:
        grading.outcome = SecurityOutcome.PARTIAL.value
    else:
        grading.outcome = SecurityOutcome.MISSED.value
    return grading


__all__ = [
    "SecurityGraderError",
    "SecurityGrading",
    "grade_security",
]

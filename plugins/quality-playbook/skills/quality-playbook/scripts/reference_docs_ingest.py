"""Ingest plaintext documentation from ``reference_docs/``.

v1.5.2 collapses the v1.5.1 ``formal_docs/`` + ``informal_docs/`` split into a
single ``reference_docs/`` tree:

* Files at the top level of ``reference_docs/`` are Tier 4 context (AI chats,
  design notes, retrospectives). They are loaded into Phase 1 prompts as
  background; no manifest record is written.
* Files under ``reference_docs/cite/`` are citable sources (specs, RFCs, API
  contracts). Each produces a ``FORMAL_DOC`` record in
  ``quality/formal_docs_manifest.json`` with a mechanical citation excerpt.

The manifest file name stays ``formal_docs_manifest.json`` for
backward-compatibility with downstream gate logic and existing benchmark
artifacts. Schema unchanged; only source directory changes.

Optional in-file tier marker on the first non-blank line of a ``cite/`` file
preserves the internal Tier 1 / Tier 2 distinction:

    <!-- qpb-tier: 2 -->
    # qpb-tier: 2

A tier marker is considered *present* in the file if any line contains the
substring ``qpb-tier``. If present, the marker must match the expected regex
and must appear on the first non-blank line — otherwise ingest fails.

Files with no ``qpb-tier`` substring anywhere default to Tier 1. This
default-Tier-1 behavior for untagged files is intentional and out of scope
for v1.5.2; the tiering model for untagged content is a deferred design
question. Top-level (Tier 4) files ignore the marker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

# v1.5.7 instruction 077 (addendum §5.2 W3 entry-point audit): put the
# QPB clone root on sys.path BEFORE the first `from bin import
# benchmark_lib` so script-form invocation
# (`python <clone>/bin/reference_docs_ingest.py …` from any cwd)
# resolves it on the first try. The pre-077 try/except-only form was
# broken from a foreign cwd in a clean environment: the failed first
# import left a partially-resolved namespace `bin` cached in
# sys.modules, so the post-`sys.path.insert` retry in the except
# branch still raised `ImportError: cannot import name
# 'benchmark_lib' from 'bin' (unknown location)` (observed under
# `env -i` at the instruction-077 baseline). No-op under `python -m
# bin.reference_docs_ingest`. The try/except below is retained as
# harmless defense-in-depth.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# v1.5.7 090c: foreign-bin-proof import. Pre-090c the "fallback"
# branch repeated the same `from bin import benchmark_lib` —
# tautological; if the first one raised the second one would too.
# Real fallback: path-load `benchmark_lib.py` from THIS file's
# directory so the import is anchored on __file__ regardless of
# cwd / sys.path / sibling repos.
try:
    # When run as ``python -m bin.reference_docs_ingest``.
    from bin import benchmark_lib  # type: ignore
except ImportError:
    import importlib.util as _ilu
    _bl_path = Path(__file__).resolve().parent / "benchmark_lib.py"
    _bl_spec = _ilu.spec_from_file_location(
        "_qpb_benchmark_lib_via_reference_docs_ingest", _bl_path,
    )
    if _bl_spec is None or _bl_spec.loader is None:
        raise ImportError(
            f"reference_docs_ingest: cannot resolve "
            f"benchmark_lib — path-load fallback target "
            f"{_bl_path} is missing."
        )
    benchmark_lib = _ilu.module_from_spec(_bl_spec)  # type: ignore[no-redef]
    # v1.5.7 090c: register in sys.modules BEFORE exec_module so
    # dataclass/typing machinery resolves.
    sys.modules[_bl_spec.name] = benchmark_lib
    _bl_spec.loader.exec_module(benchmark_lib)


# v1.5.7 instruction 060 (A-12): `.rst` added — reStructuredText is
# the canonical Linux-kernel / Python doc format (e.g. the VIRTIO 1.2
# spec virtio.rst). Treated as plaintext: byte-equality citation
# extraction (schemas.md §5.4) is format-agnostic; section resolution
# (§5.5) uses the plaintext branch in citation_verifier.resolve_section
# (matches the title text line, ignoring `=====`/`-----` underlines).
# `.rst` is deliberately NOT in REJECT_GUIDANCE below — it is
# supported, not a convert-first format.
SUPPORTED_EXTENSIONS = frozenset({".txt", ".md", ".rst"})
SKIPPED_FILENAMES = frozenset({"README.md"})
REFERENCE_DIR_NAME = "reference_docs"
CITE_DIR_NAME = "cite"
MANIFEST_NAME = "formal_docs_manifest.json"
# v1.6.0 Feature G (§8a): the reviewable, content-keyed classification manifest.
CLASSIFICATION_MANIFEST_NAME = "classification_manifest.json"
# v1.6.0 instruction 033 (self-Council panelist B, B-1) — WHERE THE READ LIVES.
#
# Step 2 makes classification the derivation model's read; step 4 removed the
# `prior_records` cache. Between them the agent was left with no way to get its
# read INTO a run at all: the only input was the Python callable `llm_classifier`,
# and an agent acts through files and shell commands, not by passing closures. So
# Lane B — the central mechanism of this instruction — could not produce a
# byte-citable FORMAL_DOC in the shipped flow, and re-ingesting a real corpus took
# chi from two Tier-1 records to zero with `zero_citable` true.
#
# This is the channel: an AGENT-AUTHORED, per-run artifact the agent writes before
# the ingest that consumes it. It is emphatically NOT the cache step 4 deleted:
#
#   1. INGEST NEVER WRITES IT. This is the distinguisher, and it is first because
#      the obvious answer — "but it is content-keyed" — is wrong: the deleted cache
#      was content-keyed too, that was its defining feature. What made it a cache
#      was that a run PERSISTED ITS OWN VERDICT and a later run consumed it, so the
#      machine's guess about an unread document could silently stand in for reading
#      it. Nothing here is written by the run. Every entry is authored by an agent
#      that read the document, and consent still lives only in
#      `reference_docs/qpb_decisions.txt`.
#   2. A document with no matching entry is UNREAD, not defaulted-and-forgotten. It
#      lands at `default-tier4` — distinguishable in the manifest from `llm` at
#      tier 4, which means "I read it and it is context" — and the corpus-level
#      `unread_count` says how many nobody looked at. That is the loud path the 032
#      footgun taught us to keep.
#   3. It is CONTENT-KEYED, so a read applies only to the exact bytes it was made
#      against. Necessary, but on its own it would not distinguish anything.
#
# A read is a judgment, not a permission: an entry here is exactly as powerful as
# the same judgment passed through `llm_classifier`, so it reaches Lane B and stops
# there. It cannot clear a backstop signal, and a Lane-C document stays Lane C.
READS_NAME = "classification_reads.json"
# v1.6.0 Feature G: the operator-authored sidecar — one relative path per line,
# each a file the operator promotes past the IMPLEMENTATION floor (never the
# advisory floor). Operator-authored config; ingest only reads it.
SIDECAR_NAME = "qpb_promote.txt"

# v1.6.0 Feature G (instruction 025): the operator-authored ADVISORY-floor rescue.
# Each entry is content-keyed (`<target-relative-path>  <document_sha256>  <reason
# being overridden>`) so it lifts exactly one document's exact bytes past the
# advisory floor — a swapped-in advisory can't inherit a rescue. Operator-authored
# only (ingest reads it, never writes it; the classifier / a persona / document
# content can never add to it), so a poisoned doc cannot rescue itself.
ADVISORY_RESCUE_NAME = "qpb_advisory_rescue.txt"

# v1.6.0 Feature G (instruction 030): the operator's end-of-Phase-1 classification
# review decisions. After exploration the operator is shown how each gathered
# document is being used and can correct it — "that one IS my spec", or the
# reverse. Each honored line is
# ``<authoritative|background>  <target-relative-path>  <document_sha256>  <reason>``
# — content-keyed like the advisory rescue, so a decision binds to exactly the
# bytes the operator reviewed. Operator-authored ONLY: ingest reads it, never
# writes it from classification, and neither document content, the classifier, nor
# a persona can add to it. (`record_operator_decision` writes a line only when the
# running agent is relaying an explicit operator instruction at this step.)
OPERATOR_DECISION_NAME = "qpb_authoritative.txt"

# v1.6.0 instruction 033 step 3 — THE ONE OPERATOR-OVERRIDE CHANNEL.
#
# `qpb_promote.txt` (promote past the implementation floor), `qpb_advisory_rescue.txt`
# (lift the advisory floor, content-keyed, reason-acknowledging) and
# `qpb_authoritative.txt` (the end-of-Phase-1 decision) were three files asking the
# operator the same question in three formats, plus `cite/` placement asking it a
# fourth way with a folder. They collapse to one:
#
#     <authoritative|background>  <target-relative-path>  <document_sha256>  <reason>
#
# Content-keyed, so a decision binds to exactly the bytes the operator reviewed and
# a swapped-in document cannot inherit it. Operator-authored ONLY: ingest reads it
# and never writes it from classification; document content, the classifier and a
# persona can never add a line. It is re-read every run, so DELETING a line revokes
# the decision — consent has to still be on file, or it is not consent.
#
# NAMED-SIGNAL CONFIRMATION (operator decision 2026-07-25). Promoting a
# BACKSTOP-FLAGGED document (a CVE/GHSA identifier, an advisory URL, an
# implementation-source file) requires the reason to NAME the specific signal being
# overridden — the instruction-025 speed-bump preserved in kind. The reason is the
# record: naming it is what gets written down. A promotion whose reason does not
# name the signal is REFUSED, and the show says so rather than dropping it.
DECISIONS_NAME = "qpb_decisions.txt"

# The label a `cite/`-seeded entry carries. Deliberately explicit: an operator
# reading the channel has to be able to tell which entries THEY wrote and which
# the migration shim inferred from folder placement, and a seeded entry is
# overridable by writing a later line for the same document.
CITE_MIGRATION_REASON = "migrated from cite/ placement (revocable; folder retires next release)"

# The superseded control files. Instruction 033 takes a DOCUMENTED BREAK on these:
# they are no longer honored, and ingest emits a one-shot conversion note when it
# finds one so an existing corpus fails loudly instead of silently losing an
# operator's decisions.
LEGACY_CONTROL_FILENAMES = frozenset(
    {SIDECAR_NAME, ADVISORY_RESCUE_NAME, OPERATOR_DECISION_NAME}
)

# Control files configure ingest; they are not documentation, so no path that
# enumerates the corpus may hand them to the agent or classify them. (Instruction
# 030 self-Council, Panelist C defensive sweep: `qpb_promote.txt` and
# `qpb_advisory_rescue.txt` were already leaking into `load_tier4_context` /
# `_collect` as Tier-4 "documentation" before this set existed.) The legacy names
# stay in the set so a corpus mid-migration does not start classifying them.
CONTROL_FILENAMES = frozenset(
    {DECISIONS_NAME, SIDECAR_NAME, ADVISORY_RESCUE_NAME, OPERATOR_DECISION_NAME}
)

# v1.6.0 Feature G: doc_classification is a sibling stdlib-only module; path-load
# it so `-m bin.reference_docs_ingest` and bundled layouts both resolve it.
try:
    from bin import doc_classification  # type: ignore
except ImportError:
    import importlib.util as _dc_ilu
    _dc_path = Path(__file__).resolve().parent / "doc_classification.py"
    _dc_spec = _dc_ilu.spec_from_file_location(
        "_qpb_doc_classification_via_reference_docs_ingest", _dc_path,
    )
    if _dc_spec is None or _dc_spec.loader is None:
        raise ImportError(
            f"reference_docs_ingest: cannot resolve doc_classification — "
            f"path-load target {_dc_path} is missing."
        )
    doc_classification = _dc_ilu.module_from_spec(_dc_spec)  # type: ignore[no-redef]
    sys.modules[_dc_spec.name] = doc_classification
    _dc_spec.loader.exec_module(doc_classification)

_TIER_MARKER_RE = re.compile(
    r"^\s*(?:<!--\s*qpb-tier:\s*([12])\s*-->|#\s*qpb-tier:\s*([12]))\s*$"
)

REJECT_GUIDANCE = {
    ".pdf": "Convert with: pdftotext spec.pdf spec.txt",
    ".docx": "Convert with: pandoc -t plain spec.docx -o spec.txt",
    ".doc": "Convert with: pandoc -t plain spec.doc -o spec.txt",
    ".html": "Convert with: lynx -dump https://example.org/spec.html > spec.txt",
    ".htm": "Convert with: lynx -dump spec.htm > spec.txt",
    ".rtf": "Convert with: pandoc -t plain spec.rtf -o spec.txt",
}


class IngestError(RuntimeError):
    """Raised when ingest cannot proceed."""


class Tier4LoadError(RuntimeError):
    """Raised when Tier 4 context cannot be loaded for Phase 1."""


@dataclass
class _FileRecord:
    path: Path
    rel_path: str
    text: str
    tier: int
    is_cite: bool


def _iter_candidates(root: Path) -> Iterable[Path]:
    """Enumerate ingest candidates for a target's ``reference_docs/``.

    v1.5.6 fix-up 067 C-7: broadened closure of BUG-003. Pre-fix this
    used ``rglob("*")`` to recurse arbitrarily deep, so a nested
    non-cite ``.pdf`` under ``reference_docs/<archive>/`` aborted
    Phase 1 ingest with `unsupported_extension`, and nested non-cite
    plaintext got loaded into memory and classified as Tier 4 even
    though the documented contract says only top-level ``reference_docs/``
    files are Tier 4 context. ``load_tier4_context()`` was patched in
    instruction 065, but ``_iter_candidates()`` (used by ``_collect()``,
    ``ingest()``, and ``collect_documents()``) still recursed.

    The two-tier flat structure now enforced here: top-level files of
    ``reference_docs/`` are Tier 3/4 context; top-level files of
    ``reference_docs/cite/`` are the formal-doc surface (Tier 1/2).
    Nested directories under either are out of scope.
    """
    if not root.exists():
        return []
    candidates: List[Path] = []
    # Top-level files of root/.
    for p in sorted(root.iterdir()):
        if p.is_file():
            candidates.append(p)
    # Top-level files of root/cite/.
    cite_dir = root / CITE_DIR_NAME
    if cite_dir.is_dir():
        for p in sorted(cite_dir.iterdir()):
            if p.is_file():
                candidates.append(p)
    return candidates


def _rel(path: Path, target_repo: Path) -> str:
    return str(path.relative_to(target_repo)).replace("\\", "/")


def _is_under_cite(path: Path, cite_dir: Path) -> bool:
    try:
        path.relative_to(cite_dir)
        return True
    except ValueError:
        return False


def _parse_tier_marker(text: str) -> int:
    """Resolve the tier for a ``cite/`` file.

    Option 1.5 semantics, refined in C13.8/Fix 3 to exempt body-prose mentions:

    - The first non-blank line is the marker slot. If it contains the substring
      ``qpb-tier``, it must match ``_TIER_MARKER_RE``; otherwise ``IngestError``
      is raised (malformed marker).
    - If the first non-blank line does NOT contain ``qpb-tier``, body lines are
      scanned for *misplaced* markers — a body line is treated as a misplaced
      marker only when it itself matches ``_TIER_MARKER_RE``. Body prose like
      "this doc uses qpb-tier markers for classification" does not match the
      regex and is allowed.
    - Otherwise, default to Tier 1.

    Two regression vectors stay closed: (a) malformed markers on the first
    non-blank line raise, (b) full-syntax markers in the body raise. The new
    case handled is (c) body prose containing the substring without matching
    the regex no longer false-positives.

    The default-Tier-1 behavior for untagged files remains intentional;
    untagged-content tiering is a deferred design question.
    """
    lines = text.split("\n")

    first_non_blank_idx = None
    for i, line in enumerate(lines):
        if line.strip():
            first_non_blank_idx = i
            break

    if first_non_blank_idx is None:
        # Empty file → Tier 1 default.
        return 1

    # Scan the body for *misplaced full markers* first. A body line raises
    # only when it itself matches _TIER_MARKER_RE — body prose that merely
    # mentions the 'qpb-tier' substring without full marker syntax is allowed
    # (C13.8/Fix 3 — Round 6 Finding 3). The scan runs regardless of whether
    # the first non-blank line is a valid marker, so 'two valid markers,
    # second misplaced' also raises.
    for idx, line in enumerate(lines):
        if idx == first_non_blank_idx:
            continue
        if _TIER_MARKER_RE.match(line.strip()):
            raise IngestError(
                "tier marker must appear on the first non-blank line "
                "(found valid 'qpb-tier' marker syntax on line {line_no}, "
                "first non-blank line is {first_no})".format(
                    line_no=idx + 1,
                    first_no=first_non_blank_idx + 1,
                )
            )

    first_line_stripped = lines[first_non_blank_idx].strip()

    if "qpb-tier" in first_line_stripped:
        # First non-blank line claims to be a marker; validate syntax.
        m = _TIER_MARKER_RE.match(first_line_stripped)
        if not m:
            raise IngestError(
                "malformed tier marker on first non-blank line: {!r} "
                "(expected '<!-- qpb-tier: 1 -->', '<!-- qpb-tier: 2 -->', "
                "'# qpb-tier: 1', or '# qpb-tier: 2')".format(first_line_stripped)
            )
        return int(m.group(1) or m.group(2))

    # No marker on first non-blank line, no misplaced full marker in body —
    # default to Tier 1.
    return 1


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise IngestError(
            f"{path}: not UTF-8 decodable ({exc}). Convert to plaintext first."
        )


def _collect(target_repo: Path) -> List[_FileRecord]:
    ref_dir = target_repo / REFERENCE_DIR_NAME
    cite_dir = ref_dir / CITE_DIR_NAME
    records: List[_FileRecord] = []

    for path in _iter_candidates(ref_dir):
        if path.name in SKIPPED_FILENAMES or path.name in CONTROL_FILENAMES:
            continue
        # Phase 3.9.1 BUG 2 (surfaced during the 2026-04-30 empirical
        # bootstrap test): skip dotfiles (.gitkeep, .DS_Store, etc.)
        # before the extension gate. They're sentinel placeholders
        # protecting otherwise-empty tracked directories — not
        # citable content. Without this skip, .gitkeep reaches the
        # extension check with suffix='' and raises IngestError
        # ("unsupported extension ''"), aborting Phase 1 ingest.
        if path.name.startswith("."):
            continue
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            # v1.6.0 Feature G (§8a): dump-and-go accepts machine-readable
            # contracts (.proto/.json/.yaml/.d.ts/…) and implementation source
            # (.py/.c/.go/…). Those are NOT plaintext formal-docs, so the
            # plaintext-only formal-docs pass skips them here — the
            # classification pass (classify_reference_docs) tiers them (a
            # contract is citable, code is floored). Only genuinely binary /
            # convert-first formats (.pdf/.docx/…) still abort with a hint, so
            # a dumped .proto no longer hard-stops Phase 1 ingest.
            if _classify_ext_ok(path.name):
                continue
            hint = REJECT_GUIDANCE.get(
                ext, "Only .txt, .md, and .rst are ingested — convert to plaintext first."
            )
            raise IngestError(f"{_rel(path, target_repo)}: unsupported extension '{ext}'. {hint}")
        text = _read_text(path)
        is_cite = _is_under_cite(path, cite_dir)
        if is_cite:
            tier = _parse_tier_marker(text)
        else:
            tier = 4
        records.append(
            _FileRecord(
                path=path,
                rel_path=_rel(path, target_repo),
                text=text,
                tier=tier,
                is_cite=is_cite,
            )
        )
    return records


def _citation_excerpt(text: str, max_chars: int = 240) -> str:
    """Return the first non-blank run of characters, truncated to max_chars."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # Skip tier marker line if present.
        if _TIER_MARKER_RE.match(stripped):
            continue
        return stripped[:max_chars]
    return ""


def _build_record_from_text(
    rel_path: str, text: str, tier: int, schema_version: str, generated_at: str
) -> dict:
    """Build a FORMAL_DOC record from raw ``(rel_path, text, tier)``.

    v1.6.0 Feature G (instruction 011): the tier is supplied by the caller —
    from the classification decision for a dumped doc, or from
    ``_parse_tier_marker`` for a ``cite/`` doc — so a top-level dumped doc
    classified Tier 1/2 becomes byte-citable exactly like a ``cite/`` doc.
    The ``document_sha256`` is the same content key the classification manifest
    uses, so the two manifests reconcile.
    """
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return {
        "doc_id": f"FORMAL-{digest[:12]}",
        "source_path": rel_path,
        "tier": tier,
        "byte_count": len(text.encode("utf-8")),
        "line_count": len(text.splitlines()),
        "citation_excerpt": _citation_excerpt(text),
        "document_sha256": digest,
        "ingested_at": generated_at,
        "schema_version": schema_version,
        "role": "external-spec",
    }


def _formal_tier(decision: dict, text: str, is_cite: bool) -> Optional[int]:
    """The FORMAL_DOC tier for a doc, or None if it is not byte-citable.

    v1.6.0 Feature G (instruction 011): the classification ``decision`` is the
    source of truth and already encodes the promotion decision — a document the
    classification held back carries ``promotable == False`` and can NEVER acquire
    a Tier-1/2 record here. Tiers are read, never re-litigated.

    After instruction 033 the held-back set is the **Lane-C** queue
    (``RULE_CONFIRM_REQUIRED``): a backstop-flagged document (CVE/GHSA identifier,
    advisory URL, implementation source), a contract-format extension whose content
    does not validate, or one the model saw asking to be treated as authoritative.
    Verified: Lane A and Lane B both yield a record; both Lane-C shapes yield none.
    A Lane-B record is real byte-citable grounding that rests on the model's read
    alone — its ``confirmation: unconfirmed`` status rides on the classification
    record and is disclosed by the show, the gate WARN and the Stage-1 playback.

    - Floored (``promotable`` False) → None (Tier-4 context, no record).
    - ``cite/`` (operator explicit pre-sort, floor already cleared it) → the
      ``_parse_tier_marker`` Tier 1/2, unchanged from pre-Feature-G behavior.
    - Top-level dumped doc → the classification tier iff it is 1/2.
    """
    if not decision.get("promotable", False):
        return None
    if is_cite:
        return _parse_tier_marker(text)
    return decision["tier"] if decision.get("tier") in (1, 2) else None


def _build_record(rec: _FileRecord, schema_version: str, generated_at: str) -> dict:
    return _build_record_from_text(
        rec.rel_path, rec.text, rec.tier, schema_version, generated_at
    )


# NOTE (v1.5.7 fix Q2, preserved): every FORMAL_DOC record carries
# `role: "external-spec"` (schemas.md §3.6) — an external plaintext/contract
# spec supplied by the operator, whether via cite/ or dump-and-go. The other
# enum values (skill-self-spec / skill-reference) apply only when the target IS
# a Skill/Hybrid project; those records come from Phase 1's skill-surface
# scanning, not this ingest module. Emitting `role` engages the gate's
# strict-mode validation (schemas.md §3.10 field-presence detection).


def collect_documents(target_repo: Path) -> List[_FileRecord]:
    """Public helper for tests — returns the collected _FileRecord list."""
    return _collect(target_repo)


def load_tier4_context(target_repo: Path) -> List[Tuple[str, str]]:
    """Return Tier 4 context as ``(rel_path, text)`` tuples, sorted by path.

    Preserves the shape of the legacy ``load_informal_docs`` so existing
    Phase 1 prompts keep working unchanged.
    """
    target_repo = Path(target_repo)
    ref_dir = target_repo / REFERENCE_DIR_NAME
    try:
        tier4: List[Tuple[str, str]] = []
        if not ref_dir.is_dir():
            return tier4
        for path in sorted(ref_dir.iterdir()):
            if not path.is_file():
                continue
            if (path.name.startswith(".") or path.name in SKIPPED_FILENAMES
                    or path.name in CONTROL_FILENAMES):
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            tier4.append((_rel(path, target_repo), _read_text(path)))
        return tier4
    except IngestError as exc:
        raise Tier4LoadError(str(exc)) from exc


def ingest(target_repo: Path, *, llm_classifier=None) -> dict:
    """Walk ``reference_docs/`` and emit ``quality/formal_docs_manifest.json``.

    Returns the manifest as a dict for test inspection.

    v1.6.0 Feature G (instruction 011): the FORMAL_DOC (byte-citable) surface is
    now driven by the classification manifest — the source of truth for a
    top-level dumped doc's tier. A dumped doc classified Tier 1/2 and
    ``promotable`` becomes a FORMAL_DOC record exactly like a ``cite/`` doc
    (including a machine-readable contract such as ``.proto``/OpenAPI); a floored
    or background doc stays Tier-4 context with no record. ``cite/`` docs keep
    their ``_parse_tier_marker`` tier. The floor is READ from the classification
    decision (``promotable``), never re-litigated here, so this path can never
    launder a floored doc to citable. ``llm_classifier`` is the derivation AI's
    per-file tier callable (the acceptance oracle injects a stub); in a real run
    the agent writes ``quality/classification_reads.json`` before this call and it
    is synthesized from there. It is NOT recorded into the classification
    manifest, which this run overwrites.
    """
    target_repo = Path(target_repo)
    if not target_repo.exists():
        raise IngestError(f"target repo does not exist: {target_repo}")

    ref_dir = target_repo / REFERENCE_DIR_NAME
    cite_dir = ref_dir / CITE_DIR_NAME

    # Prefer an installed SKILL.md under .github/skills or .claude/skills; fall
    # back to a root-level SKILL.md (used by the QPB self-audit bootstrap).
    schema_version = (
        benchmark_lib.detect_repo_skill_version(target_repo)
        or benchmark_lib.detect_skill_version(target_repo)
    )
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Classification is the source of truth for top-level tiers (§8a). It also
    # writes quality/classification_manifest.json (and reuses a prior one,
    # content-keyed, re-running the absolute floor on every hit).
    classification = classify_reference_docs(target_repo, llm_classifier=llm_classifier, write=True)
    decisions = {r["source_path"]: r for r in classification.get("records", [])}

    formal_records: List[dict] = []
    for path in _iter_candidates(ref_dir):
        name = path.name
        # README is Tier-4 background (recorded in the classification manifest),
        # never a FORMAL_DOC; dotfiles and the sidecar are control files.
        if (name.startswith(".") or name in CONTROL_FILENAMES
                or name in SKIPPED_FILENAMES):
            continue
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS and not _classify_ext_ok(name):
            # Genuinely binary / convert-first format — abort with a hint,
            # unchanged from the plaintext-only era.
            hint = REJECT_GUIDANCE.get(
                ext, "Only .txt, .md, and .rst are ingested — convert to plaintext first."
            )
            raise IngestError(f"{_rel(path, target_repo)}: unsupported extension '{ext}'. {hint}")
        rel_path = _rel(path, target_repo)
        decision = decisions.get(rel_path)
        if decision is None:
            continue
        text = _read_text(path)  # strict UTF-8; preserves the non-UTF-8 abort.
        tier = _formal_tier(decision, text, _is_under_cite(path, cite_dir))
        if tier is None:
            continue
        formal_records.append(
            _build_record_from_text(rel_path, text, tier, schema_version, generated_at)
        )

    formal_records.sort(key=lambda r: r["source_path"])
    manifest = {
        "schema_version": schema_version,
        "generated_at": generated_at,
        "records": formal_records,
    }

    quality_dir = target_repo / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    out = quality_dir / MANIFEST_NAME
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


# instruction 033 step 3: `_load_sidecar`, `_load_advisory_rescues` and
# `_load_operator_decisions` are DELETED. They read the three superseded control
# files; `_load_decisions` reads the one channel that replaced them. Charter (c):
# gone, not renamed.
def _load_decisions(ref_dir: Path) -> List[Tuple[str, str, str, str]]:
    """Read THE operator-override channel (``reference_docs/qpb_decisions.txt``).

    Instruction 033 step 3. One format for every override the operator can make:

        <authoritative|background>  <path>  <document_sha256>  <reason>

    Returns ``(rel_path, sha256, decision, reason)`` in file order — a later line
    supersedes an earlier one for the same key. A line missing the verb, the path,
    the sha or the reason is NOT honored, and an unrecognized verb is ignored
    rather than guessed at. Missing file → empty list, which is how deleting a
    line revokes it: the file is re-read every run and nothing is remembered.

    Operator-authored ONLY. Ingest reads this and never writes it from
    classification.
    """
    path = ref_dir / DECISIONS_NAME
    if not path.is_file():
        return []
    out: List[Tuple[str, str, str, str]] = []
    for line in _read_text(path).splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split(None, 3)   # verb, path, sha256, reason (remainder)
        if len(parts) < 4 or not parts[3].strip():
            continue               # incomplete / no acknowledgment reason
        decision = parts[0].lower()
        if decision not in doc_classification._OPERATOR_DECISIONS:
            continue               # unrecognized verb — never guessed at
        out.append((parts[1], parts[2].lower(), decision, parts[3].strip()))
    return out


def signal_tokens(signals: Sequence[Tuple[str, str, str]]) -> List[str]:
    """The specific evidence an operator must name to promote a flagged document.

    ``backstop_signals`` carries the evidence as its own field — the CVE/GHSA
    identifier, the advisory URL, the code extension — so this is a projection,
    not a parse.

    It used to be a parse: the token was recovered by scanning the *rendered*
    detail (``advisory identifier 'CVE-2024-43796'``) for a quoted substring. That
    let the DOCUMENT decide what its operator had to say about it — a URL
    containing apostrophes yielded a one-letter token that any prose satisfied.
    Deriving a security gate's input from a display string is the mistake; the
    field is the fix.
    """
    return [token for _kind, _detail, token in signals]


def names_every_signal(reason: str, signals: Sequence[Tuple[str, str, str]]) -> bool:
    """Whether *reason* acknowledges EVERY backstop signal by name.

    The named-signal confirmation (instruction 033 step 3), and the reason it is
    "by name" rather than a checkbox: a promotion that says only *"yes, use it"*
    proves nothing about whether the operator saw the CVE identifier sitting in the
    document. Requiring the evidence to appear in their own words is the
    instruction-025 speed-bump carried forward — 025 made them copy the sha and the
    reason out of the manifest for exactly this reason.

    Every signal must be named: acknowledging the advisory URL while ignoring the
    CVE identifier in the same document is a partial acknowledgment, and partial is
    the shape that lets one slip through.
    """
    if not signals:
        return True
    low = (reason or "").lower()
    tokens = signal_tokens(signals)
    # An empty token is UNNAMEABLE, so it refuses rather than passing vacuously:
    # a signal nobody can acknowledge must not be one everybody has acknowledged.
    return bool(tokens) and all(tok and tok.lower() in low for tok in tokens)


def legacy_control_files(ref_dir: Path) -> List[str]:
    """Superseded control files still present — the documented-break signal.

    Instruction 033 step 3 collapses four channels into one and takes a documented
    break on the three ``qpb_*.txt`` predecessors. They are no longer read, so a
    corpus carrying one would silently lose the operator's decisions. Ingest
    surfaces them instead; the caller turns this into the one-shot conversion note.
    """
    return sorted(name for name in LEGACY_CONTROL_FILENAMES
                  if (ref_dir / name).is_file())


def conversion_note(names: Sequence[str]) -> Optional[str]:
    """The one-shot conversion note for a corpus with superseded control files."""
    if not names:
        return None
    return (
        "These control files are no longer read: {}. v1.6.0 instruction 033 "
        "collapsed the four override channels into one — {} — with the line "
        "format `<authoritative|background>  <path>  <document_sha256>  <reason>`. "
        "Convert each entry by hand (a promotion of a document carrying a CVE/GHSA "
        "identifier, an advisory link or source code must NAME that signal in its "
        "reason, which is the acknowledgment the old `qpb_advisory_rescue.txt` "
        "required), then delete the superseded files. Until you do, those decisions "
        "are NOT being applied."
    ).format(", ".join(names), DECISIONS_NAME)


def record_operator_decision(
    target_repo: Path, rel_path: str, decision: str, reason: str
) -> str:
    """Append one operator classification-review decision, content-keyed.

    Instruction 030: the mechanical form of "the operator said *treat that one as
    my specification*" (or the reverse). The caller is the running agent relaying
    an **explicit operator instruction at the end-of-Phase-1 review** — this is the
    only sanctioned writer, exactly as the agent authors ``qpb_advisory_rescue.txt``
    when the operator rescues an advisory. It grants no new authority: the file it
    writes is the operator-authored input ingest reads, and nothing about a
    *document's content* can reach this function.

    Instruction 033 step 3: this writes THE one channel (``qpb_decisions.txt``),
    and it enforces the NAMED-SIGNAL confirmation at write time. Promoting a
    document the backstop flagged — a CVE/GHSA identifier, an advisory link, an
    implementation-source file — requires the reason to name that evidence, so a
    promotion that does not is refused HERE, with the signal quoted back, rather
    than being written and then silently ignored at read time. Refusing at the
    point of writing is the difference between the operator learning now and the
    operator believing they promoted something that was never applied.

    The sha is computed from the file on disk with the same decode the classifier
    uses, so the written key matches the record the operator was shown. Idempotent:
    re-recording the same decision for the same bytes does not duplicate the line.
    Re-run ``ingest()`` afterwards for the decision to reach
    ``formal_docs_manifest.json``. Returns the line (with trailing newline).
    """
    target_repo = Path(target_repo)
    decision = (decision or "").strip().lower()
    if decision not in doc_classification._OPERATOR_DECISIONS:
        raise IngestError(
            f"operator decision must be one of "
            f"{sorted(doc_classification._OPERATOR_DECISIONS)}, got {decision!r}"
        )
    reason = " ".join((reason or "").split())
    if not reason:
        raise IngestError(
            "an operator classification-review decision must carry a reason "
            "(the acknowledgment that makes the decision reviewable)"
        )
    # The file format is whitespace-delimited and positional (the instr-025
    # rescue's shape), so a path containing whitespace would be written happily
    # and then parse back as a DIFFERENT path — the decision would silently
    # no-op, and the show would keep saying "background" while the operator
    # believes they promoted it. Refuse loudly instead (instr 030 self-Council,
    # Panelist A).
    if rel_path != rel_path.strip() or any(c.isspace() for c in rel_path):
        raise IngestError(
            f"cannot record a decision for {rel_path!r}: the operator decision "
            f"file ({DECISIONS_NAME}) is whitespace-delimited, so a "
            f"document path containing whitespace cannot be expressed in it. "
            f"Rename the document (or place it under reference_docs/cite/ to "
            f"mark it a source) and re-run the ingest."
        )
    doc = target_repo / rel_path
    if not doc.is_file():
        raise IngestError(f"no such document to decide on: {rel_path}")
    text = doc.read_text(encoding="utf-8", errors="replace")
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    # The named-signal confirmation, enforced where the operator can still act on
    # it. A promotion of a flagged document must name the evidence being overridden.
    if decision == doc_classification.OPERATOR_AUTHORITATIVE:
        signals = doc_classification.backstop_signals(text, rel_path)
        if signals and not names_every_signal(reason, signals):
            raise IngestError(
                f"cannot record this promotion of {rel_path}: it carries "
                f"{'; '.join(d for _k, d, _t in signals)}, and promoting a document "
                f"with that signal requires the reason to name it "
                f"({', '.join(signal_tokens(signals))}). Confirm you have read the "
                f"document and mean to quote it as a source despite that signal, "
                f"and say so in the reason."
            )

    line = f"{decision}  {rel_path}  {sha}  {reason}\n"

    ref_dir = target_repo / REFERENCE_DIR_NAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    out = ref_dir / DECISIONS_NAME
    if out.is_file():
        existing = _read_text(out)
        if any(l.strip() == line.strip() for l in existing.splitlines()):
            return line            # already recorded — idempotent
        if existing and not existing.endswith("\n"):
            existing += "\n"
        out.write_text(existing + line, encoding="utf-8")
    else:
        header = (
            "# Operator decisions about the documents you gathered. This is the ONE\n"
            "# override channel (v1.6.0 instruction 033): it replaced qpb_promote.txt,\n"
            "# qpb_advisory_rescue.txt, qpb_authoritative.txt and cite/ placement.\n"
            "# Written only on an explicit operator instruction; ingest reads this\n"
            "# file and never writes it from classification. Document content, the\n"
            "# classifier, and personas can NEVER add a line here.\n"
            "# Deleting a line REVOKES that decision on the next run.\n"
            "# Promoting a document that carries a CVE/GHSA identifier, an advisory\n"
            "# link or source code requires the reason to NAME that signal.\n"
            "# Format: <authoritative|background>  <path>  <document_sha256>  <reason>\n"
        )
        out.write_text(header + line, encoding="utf-8")
    return line


# v1.6.0 Feature G: classification enumerates a broader set than the plaintext
# formal-docs path — a dumped corpus can include machine-readable contracts
# (.proto/.json/.yaml/.d.ts/…) that are citable and implementation source
# (.py/.c/.go/…) that the floor demotes. All are read as text (errors replaced);
# genuinely binary files are excluded by extension.
# instruction 033 step 1: `_CONTRACT_EXTS` is gone — the extension no longer
# promotes anything, so it was split into the anchored formats (validated by a real
# parse) and the anchorless ones (routed to operator confirmation). This set is
# only about which files are READ as classification candidates, so it wants both.
_CLASSIFY_EXTENSIONS = (
    SUPPORTED_EXTENSIONS
    | doc_classification._ANCHORED_CONTRACT_EXTS
    | doc_classification._HINT_ONLY_CONTRACT_EXTS
    | doc_classification._IMPL_EXTS
    | {".json", ".yaml", ".yml"}
)


def _classify_ext_ok(name: str) -> bool:
    low = name.lower()
    if low.endswith(".d.ts"):
        return True
    return Path(low).suffix in _CLASSIFY_EXTENSIONS


def _classification_candidates(ref_dir: Path, target_repo: Path) -> List[Tuple[str, str]]:
    """All ingestible docs (top-level + ``cite/``) as ``(rel_path, text)``.

    Dump-and-go: every top-level file is a classification candidate, not just
    those under ``cite/``. Reserved control files, dotfiles and README are
    excluded; binary-extension files are skipped.
    """
    docs: List[Tuple[str, str]] = []
    for path in _iter_candidates(ref_dir):
        # README is NOT skipped here (unlike the formal-docs path): §8a item 7
        # requires it be recorded as Tier-4 background, not silently dropped —
        # the background-ledger floor rule tiers it.
        if path.name.startswith(".") or path.name in CONTROL_FILENAMES:
            continue
        if not _classify_ext_ok(path.name):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        docs.append((_rel(path, target_repo), text))
    return docs


def _load_reads(target_repo: Path) -> Dict[Tuple[str, str], dict]:
    """The agent's per-document reads, keyed by ``(source_path, sha256)``.

    Malformed entries are SKIPPED rather than guessed at, exactly like the operator
    decision channel: a read nobody can attribute to specific bytes is not a read.
    A malformed FILE raises, because silently classifying a whole corpus as unread
    because of a stray comma is the quiet failure this instruction exists to end.
    """
    path = Path(target_repo) / "quality" / READS_NAME
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise IngestError(f"{READS_NAME} is not valid JSON: {exc}") from exc
    if isinstance(payload, dict):
        payload = payload.get("reads", [])
    if not isinstance(payload, list):
        raise IngestError(f"{READS_NAME} must be a list of reads (or {{'reads': [...]}})")
    out: Dict[Tuple[str, str], dict] = {}
    for entry in payload:
        # EVERY malformed entry is refused, by name. Skipping one was the exact
        # failure the tier check below prevents, arrived at from the other side: a
        # dropped entry turns a document the agent DID read into one reported as
        # never read, and a genuine spec quietly loses its promotion. The file is
        # authored by the agent moments before the run that consumes it, so a typo
        # is worth one diagnosed re-run of a cheap idempotent step.
        if not isinstance(entry, dict):
            raise IngestError(
                f"{READS_NAME}: every entry must be an object, got {entry!r}")
        rel = entry.get("source_path")
        sha = entry.get("document_sha256")
        if not isinstance(rel, str) or not rel:
            raise IngestError(
                f"{READS_NAME}: an entry has no usable source_path ({rel!r})")
        if not isinstance(sha, str) or not sha:
            raise IngestError(
                f"{READS_NAME}: {rel} has no usable document_sha256 ({sha!r}); it "
                "must be the sha256 hex digest of the bytes you read")
        # An out-of-range INTEGER tier used to escape as a bare `ValueError` from
        # `classify_document`, which runs outside the classifier's try/except: not
        # an `IngestError`, so `main()` printed a traceback instead of its
        # diagnostic; it named neither this file nor the document; and both
        # manifests kept the PREVIOUS run's contents, leaving a stale byte-citable
        # record on disk while the run appeared to fail. A non-integer tier
        # (`"1"`, `1.0`) took the graceful `classifier_status: error` path instead
        # — the same agent typo, two paths, and the worse one is the one an
        # off-by-one takes. `tier: 5` is especially easy to write, since the
        # pipeline's own evidence vocabulary runs to "Tier 5".
        # `isinstance`, not `in` — `tier not in (1, 2, 3, 4)` is an equality test,
        # so `true` and `1.0` sailed through a guard whose message says they may
        # not. Benign in effect, but a check that admits what it claims to refuse
        # is a check nobody can rely on.
        tier = entry.get("tier")
        if tier is not None and (
                isinstance(tier, bool) or not isinstance(tier, int)
                or tier not in (1, 2, 3, 4)):
            raise IngestError(
                f"{READS_NAME}: {rel} has tier {tier!r}; a read must be 1, 2, 3, 4 "
                "or absent (1/2 authoritative, 3/4 background)"
            )
        # sha256 hex-digests are case-insensitive, and an agent writing one in
        # upper case has still read the document. Normalising here rather than at
        # the lookup keeps the two ends from disagreeing.
        #
        # Two entries for the same document and bytes: LAST WINS, the same rule the
        # operator decision channel uses, so a correction appended to the end of the
        # file supersedes what came before it rather than being ignored.
        out[(rel, sha.lower())] = entry
    return out


def _classifier_from_reads(reads: Dict[Tuple[str, str], dict]):
    """Turn the read artifact into the `llm_classifier` callable.

    The artifact IS the classifier — this is a shape change, not an authority
    change, which is why a read entry can do nothing a live callable could not.
    """
    def classifier(rel_path: str, text: str):
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        entry = reads.get((rel_path, sha))
        if entry is None:
            # Either never read, or read against DIFFERENT bytes. Both mean the
            # same thing and both must mean it loudly: nobody has read what is on
            # disk now.
            return None
        return {
            "tier": entry.get("tier"),
            "category": entry.get("category"),
            "reason": entry.get("reason"),
            "self_classifying": bool(entry.get("self_classifying")),
        }

    return classifier


def classify_reference_docs(
    target_repo: Path,
    *,
    llm_classifier=None,
    write: bool = True,
) -> dict:
    """Feature G (§8a): classify all reference docs over the deterministic floor.

    ``cite/`` placement is honored as an explicit operator pre-classification
    (it promotes past the implementation floor, exactly like the sidecar — but
    never past the advisory floor). ``llm_classifier`` is the derivation AI's
    per-file tier callable; when None, the floor still runs and floor-passed
    docs default to Tier 4 (dump-and-go stays safe without the AI in Python).
    No prior manifest is read: the classification manifest is an OUTPUT,
    regenerated every run. What carries a read between runs is the agent's
    ``quality/classification_reads.json``. Writes
    ``quality/classification_manifest.json`` when ``write`` is True.
    """
    target_repo = Path(target_repo)
    ref_dir = target_repo / REFERENCE_DIR_NAME
    cite_dir = ref_dir / CITE_DIR_NAME

    docs = _classification_candidates(ref_dir, target_repo)
    text_by_path = dict(docs)

    # An explicitly-supplied callable always wins (the tests and any embedding
    # caller); otherwise the agent's read artifact supplies it. When there is
    # neither, classification stays unwired and says so.
    if llm_classifier is None:
        reads = _load_reads(target_repo)
        if reads:
            llm_classifier = _classifier_from_reads(reads)

    # --- THE ONE CHANNEL (instruction 033 step 3) ----------------------------
    # `qpb_decisions.txt`: operator-authored, content-keyed, re-read every run so
    # deleting a line revokes it. Everything the operator can say about a document
    # is said here, in one format.
    decisions = _load_decisions(ref_dir)

    # `cite/` MIGRATION SHIM (one release). A `cite/`-placed document pre-seeds the
    # channel as a clearly-labelled, REVOCABLE entry, so an existing corpus keeps
    # working while the folder is retired next release. It is revocable in the
    # honest sense: the operator can override it by writing a `background` line for
    # the same document, because a later line supersedes an earlier one and these
    # are seeded FIRST.
    seeded: List[Tuple[str, str, str, str]] = []
    for path in _iter_candidates(ref_dir):
        if _is_under_cite(path, cite_dir) and _classify_ext_ok(path.name):
            rel = _rel(path, target_repo)
            text = text_by_path.get(rel)
            if text is None:
                continue
            seeded.append((
                rel, hashlib.sha256(text.encode("utf-8")).hexdigest(),
                doc_classification.OPERATOR_AUTHORITATIVE,
                CITE_MIGRATION_REASON,
            ))
    decisions = seeded + decisions

    # --- NAMED-SIGNAL CONFIRMATION -------------------------------------------
    # A promotion of a BACKSTOP-FLAGGED document is honored only when its reason
    # NAMES the specific signal being overridden. One that does not is REFUSED —
    # and refused visibly: the decision is still passed through as the operator's
    # `authoritative` so the record carries it and the show says "you asked me to
    # use this one as a source; I'm not", rather than dropping it silently.
    operator_decisions: List[Tuple[str, str, str]] = []
    advisory_rescues: List[Tuple[str, str]] = []
    # CONTENT-keyed, exactly like `advisory_rescues`. This was a path-keyed `set()`
    # of relative paths, and the asymmetry was a live consent leak: an operator who
    # approved `contract.py` had approved the PATH, so replacing the file's bytes
    # inherited the promotion and the swapped content shipped as Tier 1. The
    # advisory arm one line up already refused that same attack; a guard that is
    # right on one arm and absent on its sibling is the defect.
    sidecar_promotions: List[Tuple[str, str]] = []
    refused: List[str] = []
    for rel, sha, decision, reason in decisions:
        operator_decisions.append((rel, sha, decision))
        if decision != doc_classification.OPERATOR_AUTHORITATIVE:
            continue
        text = text_by_path.get(rel)
        if text is None:
            continue
        signals = doc_classification.backstop_signals(text, rel)
        if not signals:
            continue
        if names_every_signal(reason, signals):
            # Acknowledged by name -> route to the channel that clears that class
            # of signal. The two are NOT interchangeable (§8a's hard bounds), so
            # an advisory acknowledgment does not also clear implementation source.
            kinds = {k for k, _d, _t in signals}
            if kinds & {doc_classification.BACKSTOP_ADVISORY_ID,
                        doc_classification.BACKSTOP_ADVISORY_URL}:
                advisory_rescues.append((rel, sha))
            if doc_classification.BACKSTOP_IMPL_SOURCE in kinds:
                sidecar_promotions.append((rel, sha))
        else:
            refused.append(rel)

    # instruction 033 step 4: no prior-manifest reuse. Every run re-reads and
    # re-derives; the artifact that persists between runs is the operator's
    # confirmed decisions, not the machine's guesses.
    out = target_repo / "quality" / CLASSIFICATION_MANIFEST_NAME

    schema_version = (
        benchmark_lib.detect_repo_skill_version(target_repo)
        or benchmark_lib.detect_skill_version(target_repo)
        or "1.6.0"
    )
    manifest = doc_classification.classify_documents(
        docs,
        llm_classifier=llm_classifier,
        sidecar=sorted(sidecar_promotions),
        advisory_rescues=advisory_rescues,
        operator_decisions=operator_decisions,
        schema_version=schema_version,
    )
    # instruction 033 step 3 — the documented break, SURFACED. A conversion note
    # nobody sees is not a documented break, it is silent data loss: the operator's
    # decisions in a superseded file simply stop applying. Carried on the manifest
    # so the gate, the show and any caller can raise it.
    legacy = legacy_control_files(ref_dir)
    if legacy:
        manifest["legacy_control_files"] = legacy
        manifest["conversion_note"] = conversion_note(legacy)
    if refused:
        # Promotions the operator asked for that were refused for want of a named
        # signal. On the manifest so the refusal is auditable, not only rendered.
        manifest["refused_promotions"] = sorted(refused)

    if write:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
    # v1.5.7 089x: no-args is purpose-banner-safe.
    _argv_list_089x = list(sys.argv[1:] if argv is None else argv)
    try:
        from bin._purpose import print_command_intro as _print_command_intro
        from bin._purpose import print_help_banner as _print_help_banner
    except ImportError:
        from _purpose import print_command_intro as _print_command_intro  # type: ignore[no-redef]
        from _purpose import print_help_banner as _print_help_banner  # type: ignore[no-redef]
    if not _argv_list_089x:
        _print_command_intro(
            name='reference_docs_ingest',
            summary=(
            "Phase 1 reference-docs ingest — copies a curated subset "
            "of QPB references/ into the target's reference_docs/ "
            "tree. "
            ),
            role=(
            "Mandatory Phase 1 step before any agent-driven "
            "exploration (without it run_playbook.py aborts with "
            "`references missing`). Runs in the target repo's cwd. "
            ),
            usage_hint='python3 -m bin.reference_docs_ingest <target>',
        )
        return 0

    # v1.5.7 090a: full attribution banner at top of --help.
    _print_help_banner(_argv_list_089x)

    parser = argparse.ArgumentParser(description=__doc__, prog="reference_docs_ingest")
    parser.add_argument("target", nargs="?", default=".", help="Target repo path (default: cwd)")
    args = parser.parse_args(argv)

    try:
        manifest = ingest(Path(args.target).resolve())
    except IngestError as exc:
        print(f"reference_docs_ingest: {exc}", file=sys.stderr)
        return 1

    count = len(manifest["records"])
    print(f"reference_docs_ingest: wrote {count} cite record(s) to quality/{MANIFEST_NAME}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

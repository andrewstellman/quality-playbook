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
from typing import Iterable, List, Optional, Sequence, Tuple

try:
    # When run as ``python -m bin.reference_docs_ingest``.
    from bin import benchmark_lib  # type: ignore
except Exception:  # pragma: no cover - fallback when invoked as a loose script
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from bin import benchmark_lib  # type: ignore


SUPPORTED_EXTENSIONS = frozenset({".txt", ".md"})
SKIPPED_FILENAMES = frozenset({"README.md"})
REFERENCE_DIR_NAME = "reference_docs"
CITE_DIR_NAME = "cite"
MANIFEST_NAME = "formal_docs_manifest.json"

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
        if path.name in SKIPPED_FILENAMES:
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
            hint = REJECT_GUIDANCE.get(
                ext, "Only .txt and .md are ingested — convert to plaintext first."
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


def _build_record(rec: _FileRecord, schema_version: str, generated_at: str) -> dict:
    digest = hashlib.sha256(rec.text.encode("utf-8")).hexdigest()
    # v1.5.7 fix Q2: emit `role` per schemas.md §3.6 (formal_doc_role
    # enum). All records from `reference_docs/cite/` are external
    # plaintext specs uploaded by the operator — `external-spec` is
    # the correct enum value. The other two enum values
    # (`skill-self-spec`, `skill-reference`) only apply when the
    # target IS a Skill/Hybrid project with its own SKILL.md /
    # references/; those records are produced by Phase 1's skill-
    # surface scanning code, not by this ingest module. Emitting
    # `role` here promotes the manifest to v1.5.3-shaped (per
    # schemas.md §3.10 field-presence detection), engaging the
    # gate's strict-mode validation.
    return {
        "doc_id": f"FORMAL-{digest[:12]}",
        "source_path": rec.rel_path,
        "tier": rec.tier,
        "byte_count": len(rec.text.encode("utf-8")),
        "line_count": len(rec.text.splitlines()),
        "citation_excerpt": _citation_excerpt(rec.text),
        "document_sha256": digest,
        "ingested_at": generated_at,
        "schema_version": schema_version,
        "role": "external-spec",
    }


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
            if path.name.startswith(".") or path.name in SKIPPED_FILENAMES:
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            tier4.append((_rel(path, target_repo), _read_text(path)))
        return tier4
    except IngestError as exc:
        raise Tier4LoadError(str(exc)) from exc


def ingest(target_repo: Path) -> dict:
    """Walk ``reference_docs/`` and emit ``quality/formal_docs_manifest.json``.

    Returns the manifest as a dict for test inspection.
    """
    target_repo = Path(target_repo)
    if not target_repo.exists():
        raise IngestError(f"target repo does not exist: {target_repo}")

    records = _collect(target_repo)
    cite_records = [r for r in records if r.is_cite]

    # Prefer an installed SKILL.md under .github/skills or .claude/skills; fall
    # back to a root-level SKILL.md (used by the QPB self-audit bootstrap).
    schema_version = (
        benchmark_lib.detect_repo_skill_version(target_repo)
        or benchmark_lib.detect_skill_version(target_repo)
    )
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    manifest = {
        "schema_version": schema_version,
        "generated_at": generated_at,
        "records": [_build_record(r, schema_version, generated_at) for r in cite_records],
    }

    quality_dir = target_repo / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    out = quality_dir / MANIFEST_NAME
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def main(argv: Optional[Sequence[str]] = None) -> int:
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

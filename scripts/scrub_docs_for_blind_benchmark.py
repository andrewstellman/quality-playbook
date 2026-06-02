#!/usr/bin/env python3
"""Scrub docs_gathered/<repo>/*.md files of CVE/GHSA/fix-symbol terms that
would tip off QPB during a blind CVE-benchmark run.

Per repo: applies a list of regex/literal scrub terms; replaces each match
inline with `[REDACTED]`. Reports a per-file summary of scrubbed-term counts
so the operator can audit that no overscrub gutted the docs.

Per Security Research/CVE_BENCHMARK_METHODOLOGY.md's leakage_check pattern.

USAGE:
  python3 scripts/scrub_docs_for_blind_benchmark.py

The scrubbed files are written in place. Originals are recoverable from git
(commit before running, or use the --dry-run flag to preview).
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "repos" / "docs_gathered"

# Per-repo scrub terms. Each entry is (repo_dir_name, [list of regex patterns]).
# Patterns are compiled with re.IGNORECASE.
#
# Categories of scrub:
#   - CVE IDs (CVE-YYYY-NNNNN)
#   - GHSA IDs (GHSA-xxxx-xxxx-xxxx)
#   - Specific fix-PR / issue numbers tied to the patch
#   - Fix-symbol names (functions, variables, constants the patch introduced)
#   - Verbatim phrases that describe the fix shape ("fix added X")
#   - File:line citations that point AT the bug locus
SCRUB_TERMS: List[Tuple[str, List[str]]] = [
    # ---- CASE-001 setuptools (CVE-2025-47273 — path traversal) ----
    ("setuptools", [
        r"CVE-2025-47273",
        r"GHSA-5rjg(-fvgr-3xxf)?",
        r"\bissue\s*#?\s*4946\b",
        r"\bPR\s*#?\s*4946\b",
        r"/(?:issues|pull)/4946\b",   # URL form
        r"\b250a6d17[a-f0-9]*\b",     # fix commit
        r"\b250a6d17\b",
        # fix-symbol: the post-join guard the patch added
        r"if not filename\.startswith\(str\(tmpdir\)\)",
        r"\bisinstance\(name, PurePath\)",
        r"path traversal",            # category-naming the bug
        r"arbitrary file write",      # impact-naming the bug
    ]),

    # ---- CASE-002 jsPDF (CVE-2025-68428 — LFI Node build) ----
    ("jsPDF", [
        r"CVE-2025-68428",
        r"GHSA-f8cm(-6447-x5h2)?",
        r"\bPR\s*#?\s*3931\b",
        r"\bissue\s*#?\s*3931\b",
        r"/(?:issues|pull)/3931\b",
        r"\ba688c8f4[a-f0-9]*\b",
        r"\bjsPDF\.allowFsRead\b",
        r"\bprocess\.permission\b",
        r"\brealpathSync\b",
        r"path traversal",
        r"\bLFI\b",
        r"external control of file path",
        r"local file inclusion",
        r"file system access",
    ]),

    # ---- CASE-005 apache/avro (CVE-2025-33042 — code injection) ----
    ("avro", [
        r"CVE-2025-33042",
        r"AVRO-4053",
        r"\bPR\s*#?\s*3150\b",
        r"/(?:issues|pull)/3150\b",
        r"\b84bc7322[a-f0-9]*\b",
        r"\bisValidAsAnnotation\b",
        r"code injection",
        r"\bCWE-94\b",
        r"taint flow",                # categorical naming
        r"verbatim into generated",   # describes the fix shape
        r"unvalidated.{0,40}emitted",
        r"unescaped.{0,40}velocity",
    ]),

    # ---- CASE-007 apache/spark (CVE-2025-54920 — deserialization) ----
    ("spark", [
        r"CVE-2025-54920",
        r"SPARK-52381",
        r"\bPR\s*#?\s*51061\b",
        r"\bPR\s*#?\s*51312\b",
        r"/(?:issues|pull)/51061\b",
        r"/(?:issues|pull)/51312\b",
        r"SPARK-52381",
        r"\bfcf8dda2[a-f0-9]*\b",
        r"isAssignableFrom\(otherClass\)",
        r"only accept subclasses of",
        r"insecure deserialization",
        r"polymorphic deserialization",
        r"\bCWE-502\b",
    ]),

    # ---- CASE-008 dasel (CVE-2026-33320 — DoS unbounded expansion) ----
    ("dasel", [
        r"CVE-2026-33320",
        r"GHSA-4fcp(-jxh7-23x8)?",
        r"\bPR\s*#?\s*531\b",
        r"/(?:issues|pull)/531\b",
        r"\b282943b3[a-f0-9]*\b",
        r"maxExpansionDepth",
        r"maxExpansionBudget",
        r"billion laughs",
        r"billion-anchors",
        r"unbounded.{0,30}expansion",
        r"unbounded YAML",
        r"\bCWE-400\b",
        r"resource exhaustion",
        r"resource-exhaustion DoS",
    ]),

    # ---- CASE-009 evervault-go (CVE-2025-64186 — crypto/PCR check) ----
    # Important: keep PCR/attestation as legitimate API context.
    # Scrub only the FIX-specific symbols + CVE identifiers + redaction-shape
    # phrases.
    ("evervault-go", [
        r"CVE-2025-64186",
        r"GHSA-88h9(-77c7-p6w4)?",
        r"\bPR\s*#?\s*48\b",
        r"/(?:issues|pull)/48\b",
        r"\b7c824d28[a-f0-9]*\b",
        r"\bSatisfiedBy\b",
        r"\bisMinimalPCRSet\b",
        r"validateAttestationDoc",
        r"pcrNotEqual",
        r"\bCWE-347\b",
        r"empty PCRs",
        r"empty PCR0",
        r"PCR-presence check",
        r"presence check",
        r"forged.{0,40}attestation",
        r"partial.{0,40}attestation",
        r"MISSING-PCR-PRESENCE-CHECK",
    ]),

    # ---- CASE-010 gogs (CVE-2025-65852 — broken access control on DELETE /repos) ----
    # The docs_gathered focused on CVE-2026-25229 (UpdateLabel) — scrub both
    # CVE families and the fix middleware name so a blind QPB has to derive
    # any access-control gap from invariants + code.
    ("gogs", [
        r"CVE-2025-65852",
        r"CVE-2026-25229",
        r"CVE-2026-25120",
        r"CVE-2026-25232",
        r"CVE-2026-23632",
        r"CVE-2024-39930",
        r"CVE-2024-39931",
        r"CVE-2024-39932",
        r"CVE-2024-39933",
        r"CVE-2024-54148",
        r"GHSA-rjv5(-9px2-fqw6)?",
        r"GHSA-cv22(-72px-f4gh)?",
        r"\bPR\s*#?\s*8101\b",
        r"/(?:issues|pull)/8101\b",
        r"\b961a79e8[a-f0-9]*\b",
        r"\bd568e048[a-f0-9]*\b",
        r"reqRepoOwner",
        r"reqRepoAdmin",
        r"GetLabelOfRepoByID",
        r"GetLabelByID",
        r"broken access control",
        r"\bCWE-284\b",
        r"authorization bypass",
        r"read-only collaborator can delete",
        r"cross-repository label",
    ]),
]


REDACTION_MARKER = "[REDACTED]"


# Global second-pass scrub: applied to EVERY file in EVERY scrubbed repo
# AFTER the per-repo case-specific terms. Catches "prior CVE / sibling
# advisory" mentions that signal "bugs of this class have been found here
# before" even when they refer to a different CVE than the blind benchmark's
# target.
GLOBAL_SCRUB_TERMS = [
    r"CVE-\d{4}-\d{3,7}",                              # any CVE-YYYY-NNNNN
    r"GHSA-[a-z0-9]{4}-[a-z0-9]{4}-[a-z0-9]{4}",       # any GHSA-XXXX-XXXX-XXXX
    r"/advisories/GHSA-[a-z0-9-]+",                    # URL form
    r"/advisories/CVE-\d{4}-\d{3,7}",                  # URL form
]


def scrub_file(path: Path, patterns: List[re.Pattern[str]]) -> dict:
    """Replace each pattern match in `path` with REDACTION_MARKER.
    Returns a dict of pattern_str -> match_count."""
    src = path.read_text(encoding="utf-8")
    counts = {}
    new_src = src
    for pat in patterns:
        matches = pat.findall(new_src)
        if matches:
            counts[pat.pattern] = len(matches)
            new_src = pat.sub(REDACTION_MARKER, new_src)
    if counts:
        path.write_text(new_src, encoding="utf-8")
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                         help="Report what WOULD be scrubbed; don't write files.")
    args = parser.parse_args()

    total_scrubs = 0
    total_files_touched = 0
    global_patterns = [re.compile(t, re.IGNORECASE)
                        for t in GLOBAL_SCRUB_TERMS]
    for repo_name, term_list in SCRUB_TERMS:
        repo_dir = DOCS_ROOT / repo_name
        if not repo_dir.is_dir():
            print(f"  ⚠ {repo_name}: dir missing, skipping")
            continue
        patterns = [re.compile(t, re.IGNORECASE) for t in term_list]
        patterns += global_patterns
        repo_total = 0
        repo_files_touched = 0
        for md_file in sorted(list(repo_dir.glob("*.md")) + list(repo_dir.glob("*.txt"))):
            if args.dry_run:
                src = md_file.read_text(encoding="utf-8")
                counts = {}
                for pat in patterns:
                    matches = pat.findall(src)
                    if matches:
                        counts[pat.pattern] = len(matches)
                if counts:
                    repo_files_touched += 1
                    file_total = sum(counts.values())
                    repo_total += file_total
            else:
                counts = scrub_file(md_file, patterns)
                if counts:
                    repo_files_touched += 1
                    file_total = sum(counts.values())
                    repo_total += file_total
        total_scrubs += repo_total
        total_files_touched += repo_files_touched
        verb = "would-scrub" if args.dry_run else "scrubbed"
        print(f"  {repo_name:14s}: {verb} {repo_total:4d} matches "
              f"across {repo_files_touched} files "
              f"(out of {len(list(repo_dir.glob('*.md')))})")
    print()
    print(f"TOTAL: {total_scrubs} matches "
          f"{'would be ' if args.dry_run else ''}redacted "
          f"across {total_files_touched} files in 7 repos.")
    if args.dry_run:
        print("DRY-RUN — no files modified. Re-run without --dry-run to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

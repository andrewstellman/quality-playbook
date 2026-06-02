#!/usr/bin/env python3
"""
Gate 1 scanner — Blind CVE Benchmark v2 methodology.

Scans a corpus directory (e.g., repos/docs_gathered/<repo>/) for token-level
contamination patterns that disqualify the corpus from blind benchmark use.

Exit code 0 = PASS (zero hits). Non-zero = FAIL with per-line listing.

The _audit.md file is allowed to mention forbidden tokens in its procedural
"sources NOT consulted" section (e.g., "CVE database: NOT READ"). The scanner
skips _audit.md by default. Pass --include-audit to scan it too.

Per the methodology, this gate is NECESSARY but NOT SUFFICIENT. Gate 2 (blind
reviewer) catches the structural contamination this scanner cannot.
"""

import argparse
import json
import re
import sys
from pathlib import Path

PATTERNS = {
    # CVE-family identifiers (case-sensitive: real advisory IDs use uppercase prefixes;
    # excludes "go-cty" / "go-toml" / etc. package-path noise).
    # GO- (Go vuln DB) is dropped as a prefix because it collides with the entire Go ecosystem.
    "advisory_id_generic":  re.compile(r"\b(?:CVE|GHSA|CWE|PYSEC|RUSTSEC|RHSA|USN|DSA)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b"),

    # Security vocabulary (any conjugation)
    "vulnerability":        re.compile(r"\bvulnerab(?:ility|ilities|le)\b", re.I),
    "advisory_word":        re.compile(r"\badvisor(?:y|ies)\b", re.I),
    "exploit":              re.compile(r"\bexploit(?:s|able|ed|ing)?\b", re.I),

    # "patched" — exclude dotted method names (`.patch`) and all-caps `PATCH` (HTTP verb).
    # Match only standalone-word forms of patch verbs/nouns.
    "patched":              re.compile(r"(?<![.\w])(?:patched|patching|patches)\b"),

    "disclosed":            re.compile(r"\b(?:disclos(?:ed|ure|ing)|embargo(?:ed)?)\b", re.I),
    "security_fix":         re.compile(r"\bsecurity\s+(?:fix|patch|issue|advisory|bulletin|update|release|defect)\b", re.I),
    "known_issue":          re.compile(r"\bknown\s+(?:issue|bug|vulnerab|exploit|limitation|defect|problem|flaw)\b", re.I),
    "hardened":             re.compile(r"\b(?:hardened|hardening|tightened|tightening|strengthened|strengthening|fortified|fortifying)\b", re.I),
    "footgun":              re.compile(r"\b(?:footgun|gotcha)s?\b", re.I),
    "audit_word":           re.compile(r"\b(?:audit|audited|auditing|post-audit)\b", re.I),
    "coordinated":          re.compile(r"\b(?:coordinated\s+disclosure|responsible\s+disclosure)\b", re.I),

    # Fix narratives
    "fixed_in_version":     re.compile(r"\b(?:fixed|patched|resolved|addressed|repaired)\s+(?:in|by|via)\s+(?:v?\d|version|release|commit)", re.I),
    "version_with_fix":     re.compile(r"\b(?:since|after|until|before|prior\s+to)\s+v?\d+\.\d+(?:\.\d+)?\b", re.I),
    "the_bug_was":          re.compile(r"\bthe\s+(?:bug|flaw|issue|problem|defect|vulnerability|root\s+cause)\s+(?:was|is|lay|lies)\b", re.I),

    # Provenance pointers
    "commit_sha":           re.compile(r"\b[0-9a-f]{7,40}\b"),  # 7+ hex = git SHA territory
    "parent_sha":           re.compile(r"\b(?:parent\s+sha|vulnerable\s+parent|vulnerable\s+commit|the\s+bad\s+commit|fix\s+commit)\b", re.I),

    # Severity rankings
    "cvss":                 re.compile(r"\bCVSS\s*[:v]?\s*\d", re.I),
    "severity_ranking":     re.compile(r"\b(?:most|highest|primary)\s+(?:security-relevant|risk|attack\s+surface)\b", re.I),

    # Breaking change / backport / hotfix
    "breaking_change":      re.compile(r"\b(?:breaking\s+change|backport(?:ed|ing)?|hotfix(?:es|ed|ing)?)\b", re.I),

    # High-churn signals
    "high_churn":           re.compile(r"\b(?:rebuilt|high.churn|rewritten)\b", re.I),

    # Detection-method hints
    "detection_hint":       re.compile(r"\b(?:to\s+check\s+whether|verify\s+that\s+\w+\s+holds|look\s+for\s+(?:a\s+)?pattern)\b", re.I),

    # Benchmark target identifiers (NATS-N, OPENFGA-N, CASE-NNN, etc.)
    "benchmark_target":     re.compile(r"\b(?:CASE|NATS|OPENFGA|CASBIN|FINDING|BUG)-\d+\b"),

    # Pre/post-fix code annotations.
    # Note: "fixed form" was dropped — Avro has a primitive type literally named `fixed`,
    # collides with phrases like "the fixed form holds N bytes". The remaining patterns
    # are still strong signal.
    "before_after_anno":    re.compile(r"\b(?:pre-fix|post-fix|before\s+fix|after\s+fix|vulnerable\s+form)\b", re.I),
}


# Patterns that, when matched, are FALSE POSITIVES in specific contexts.
# Format: (pattern_name, false_positive_substring) — if the pattern hits and the
# matched line contains the false_positive_substring (case-insensitive), the hit
# is suppressed. Keep this list tight; abuse defeats the gate.
# Justifications:
#   monkey-patching   — documented Python idiom; setuptools/django/many libs name a module "monkey"
#   monkey patching   — same idiom, alternate spelling
#   monkey-patch      — same idiom, noun/verb form
FALSE_POSITIVES = [
    ("patched", "monkey-patching"),
    ("patched", "monkey patching"),
    ("patched", "monkey-patch"),
    ("patched", "monkey patch"),
]


def scan_file(path: Path, patterns: dict) -> list[tuple[str, int, str]]:
    """Return list of (pattern_name, line_number, line_text) for every hit."""
    hits: list[tuple[str, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return hits
    for ln_idx, line in enumerate(text.splitlines(), start=1):
        for name, regex in patterns.items():
            for m in regex.finditer(line):
                # Skip commit_sha matches that are part of a longer hash-ish word
                # We want isolated 7-40 hex chars, not embedded in versioned strings.
                if name == "commit_sha":
                    # Whole-word match check
                    matched = m.group(0)
                    # Don't flag pure-digit "SHAs" like "10000000" -- require at least one a-f char
                    if not any(c in "abcdef" for c in matched.lower()):
                        continue
                # False-positive exemption — line contains a known-legitimate
                # phrase that contains the matched token.
                line_lower = line.lower()
                if any(name == fp_name and fp_sub in line_lower
                       for fp_name, fp_sub in FALSE_POSITIVES):
                    continue
                hits.append((name, ln_idx, line.strip()))
                break  # one hit per line is enough
    return hits


def scan_corpus(corpus_dir: Path, include_audit: bool = False) -> dict:
    """Return {file_path: [hits...]} for the corpus."""
    results = {}
    if not corpus_dir.exists():
        return {"_error": f"corpus dir not found: {corpus_dir}"}

    for path in sorted(corpus_dir.rglob("*")):
        if not path.is_file():
            continue
        if not path.suffix.lower() in {".md", ".txt", ".rst"}:
            continue
        if path.name == "_audit.md" and not include_audit:
            continue
        hits = scan_file(path, PATTERNS)
        if hits:
            results[str(path.relative_to(corpus_dir))] = hits
    return results


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("corpus_dir", type=Path, help="Path to a single corpus directory")
    ap.add_argument("--include-audit", action="store_true",
                    help="Also scan _audit.md (default: skipped due to procedural-mention exemption)")
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable output")
    args = ap.parse_args()

    results = scan_corpus(args.corpus_dir, include_audit=args.include_audit)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        if not results:
            print(f"PASS — zero hits in {args.corpus_dir}")
        else:
            total = sum(len(v) for v in results.values() if isinstance(v, list))
            print(f"FAIL — {total} hits across {len(results)} files in {args.corpus_dir}")
            for fp, hits in results.items():
                print(f"\n  {fp}:")
                for name, ln, txt in hits[:10]:
                    print(f"    L{ln} [{name}] {txt[:120]}")
                if len(hits) > 10:
                    print(f"    ... +{len(hits) - 10} more")
    return 0 if not results else 1


if __name__ == "__main__":
    sys.exit(main())

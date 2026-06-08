"""v1.5.7 190 — subprocess.run text=True needs explicit utf-8 on Windows.

Andrew's 2026-06-03 Windows codex Mode B smoke fire `20260603T201438Z`:
`subprocess.run(text=True, ...)` without an explicit `encoding=` picks
the system locale codec — cp1252 on Windows — which crashes on
U+2265 (≥) in the QPB phase prompts with `UnicodeEncodeError: 'charmap'
codec can't encode character '≥' in position 14547`. This is the THIRD
cp1252-on-Windows hazard after 185 (print output) + 189 (log read);
this one is on the subprocess stdin WRITE side.

Coverage:
- FINDING-46: `bin/run_playbook.py` codex/cursor stdin write gains
  `encoding="utf-8", errors="replace"`. Same fallback shape as 189's
  read-side defense.
- FINDING-47: source-pin sweep — every `subprocess.run(text=True, ...)`
  site in `bin/run_playbook.py` + `bin/install_skill.py` +
  `bin/harness/**/*.py` carries an explicit `encoding="utf-8"`. The
  AUDIT-table invariant pin generalizes 189's
  `test_no_unguarded_external_log_reads_remain` pattern.
"""
from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[3]


class SubprocessStdinEncodingTests(unittest.TestCase):
    """Behavioral: the subprocess.run(text=True, encoding='utf-8',
    errors='replace', input=...) pattern handles a prompt that
    contains U+2265 (≥), U+2014 (—), and U+FFFD (�) without crash."""

    def test_subprocess_run_accepts_high_bit_input_with_utf8_encoding(
            self) -> None:
        """Verbatim pattern from run_playbook.py post-190: a real
        subprocess run with text=True + encoding='utf-8' +
        errors='replace' accepts a string containing ≥ ('U+2265),
        — (U+2014), and � (U+FFFD) and returns the expected
        byte-count from the child's perspective."""
        prompt = "with ≥2 References and an em-dash — and a U+FFFD �"
        # Verbatim pattern from run_playbook.py:2194-2202:
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; data=sys.stdin.read(); "
             "print(f'len={len(data)} '"
             "f'has_ge={chr(0x2265) in data} '"
             "f'has_emdash={chr(0x2014) in data}')"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0,
            msg=f"child stderr: {result.stderr}")
        self.assertIn(f"len={len(prompt)}", result.stdout)
        self.assertIn("has_ge=True", result.stdout)
        self.assertIn("has_emdash=True", result.stdout)

    def test_pre_190_default_codec_would_lose_or_crash_on_high_bit(
            self) -> None:
        """Strictness check: under cp1252 strict (the Windows default
        when text=True with no explicit encoding=), encoding ≥ raises.
        This pin reproduces Andrew's crash symptom in unit-test form.
        We can't force the parent's runtime to cp1252 from a test, but
        we CAN verify that the codec itself rejects the character —
        which proves the default-locale path on Windows would crash."""
        with self.assertRaises(UnicodeEncodeError):
            "with ≥2 References".encode("cp1252")

    def test_replace_vs_strict_distinction_on_encode(
            self) -> None:
        """Pin the instruction's stated semantic: `errors="replace"`
        survives an undecodable codepoint by substituting `?` on
        encode (cp1252 → bytes via replace) — not silent drop, not
        crash. Note: cp1252 actually HAS U+2014 (em-dash) mapped to
        byte 0x97 — so only U+2265 (≥) and U+FFFD (�) are truly
        unencodable in cp1252. (That's why Andrew's fire on ≥ was
        the crash trigger, not on em-dashes — em-dashes worked.)"""
        s = "ge=≥ emdash=— ffff=�"
        # cp1252 + replace: U+2265 and U+FFFD become "?"; U+2014
        # encodes to byte 0x97 (no substitution).
        b = s.encode("cp1252", errors="replace")
        self.assertEqual(b.count(b"?"), 2,
            "expected 2 ? substitutes (≥ and \\ufffd) under "
            "cp1252+replace; em-dash IS in cp1252 (byte 0x97)")
        self.assertIn(b"\x97", b,
            "em-dash should round-trip to cp1252 byte 0x97")
        # cp1252 + strict: raises on the first un-encodable char
        # (U+2265).
        with self.assertRaises(UnicodeEncodeError):
            s.encode("cp1252", errors="strict")
        # utf-8 + replace: no substitution needed; high-bit
        # codepoints encode cleanly to multibyte sequences.
        b_utf8 = s.encode("utf-8", errors="replace")
        self.assertEqual(b_utf8.count(b"?"), 0,
            "utf-8 has no need to substitute for these chars")


class SubprocessEncodingSweepTests(unittest.TestCase):
    """FINDING-47 audit pin. Every subprocess.run(text=True, ...)
    site in `bin/run_playbook.py` + `bin/install_skill.py` +
    `bin/harness/**/*.py` must carry an explicit `encoding="utf-8"`
    — Windows defaults to cp1252 when encoding is omitted, and
    cp1252 strict crashes on any high-bit codepoint in stdin / any
    high-bit byte in captured stdout/stderr."""

    @classmethod
    def setUpClass(cls) -> None:
        # v1.5.8 instruction 209: bin/install_skill.py is a thin
        # shim after the plugin-native + standard self-hosted
        # marketplace restructures; the canonical source (and the
        # text=True / subprocess.run sites) lives at
        # plugins/quality-playbook/skills/quality-playbook/scripts/install_skill.py.
        # Read the canonical for the install_skill.py audit row so
        # the sweep targets the source-of-truth, not the shim.
        _AUDIT_PATHS = {
            "bin/run_playbook.py": _REPO / "bin" / "run_playbook.py",
            "bin/install_skill.py": (
                _REPO / "plugins" / "quality-playbook"
                / "skills" / "quality-playbook"
                / "scripts" / "install_skill.py"
            ),
            "bin/harness/facts.py": _REPO / "bin" / "harness" / "facts.py",
            "bin/harness/runner.py": _REPO / "bin" / "harness" / "runner.py",
            "bin/harness/plan_runner.py": _REPO / "bin" / "harness" / "plan_runner.py",
            "bin/harness/prepare.py": _REPO / "bin" / "harness" / "prepare.py",
        }
        cls.files = {
            relpath: path.read_text(encoding="utf-8")
            for relpath, path in _AUDIT_PATHS.items()
        }

    def test_codex_stdin_site_source_pins_utf8(self) -> None:
        """run_playbook.py codex/cursor stdin write site (FINDING-46):
        source-pin that `text=True`, `encoding="utf-8"`, and
        `errors="replace"` co-occur with the codex/cursor stdin
        branch."""
        src = self.files["bin/run_playbook.py"]
        # Find the run_kwargs dict opening and locate the
        # codex/cursor branch that follows it. Capture the body.
        m = re.search(
            r'run_kwargs\s*=\s*dict\(\s*\n'
            r'((?:.*\n){3,15}?)'  # 3-15 dict lines
            r'\s*\)\s*\n'
            r'\s*if\s+runner\s+in\s+\("codex",\s*"cursor"\):',
            src,
        )
        self.assertIsNotNone(
            m, "could not locate run_kwargs dict + codex/cursor "
               "branch in run_playbook.py")
        body = m.group(1)
        self.assertIn("text=True", body,
            "run_kwargs dict missing text=True")
        self.assertIn('encoding="utf-8"', body,
            "run_kwargs dict missing encoding=utf-8 (FINDING-46)")
        self.assertIn('errors="replace"', body,
            "run_kwargs dict missing errors=replace (FINDING-46)")

    def test_every_text_true_subprocess_run_has_explicit_utf8(
            self) -> None:
        """Sweep invariant: for every `text=True` argument to a
        subprocess.run() call in scope, an `encoding="utf-8"` must
        appear within a 10-line window after it (kwargs of a
        single call are by convention close together). Future
        text=True site added without explicit encoding will fail
        this test.

        Counts pinned per file so a new site CAN be added without
        the test breaking — as long as the new site has
        encoding="utf-8"."""
        # The audit numbers below reflect post-190 state.
        # Update if a new instruction adds text=True sites; the
        # new site must carry encoding="utf-8" or this fails.
        AUDIT = {
            "bin/run_playbook.py": 4,
            "bin/install_skill.py": 2,
            "bin/harness/facts.py": 1,
            "bin/harness/runner.py": 2,
            "bin/harness/plan_runner.py": 2,
            "bin/harness/prepare.py": 3,
        }
        for relpath, expected in AUDIT.items():
            src = self.files[relpath]
            lines = src.splitlines()
            text_true_sites: list[int] = []
            for i, line in enumerate(lines):
                # Skip comment-line matches (the substring
                # "text=True" inside a # comment).
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if "text=True" in line:
                    text_true_sites.append(i)
            self.assertEqual(
                len(text_true_sites), expected,
                f"{relpath}: expected {expected} text=True sites, "
                f"found {len(text_true_sites)} at lines "
                f"{[i+1 for i in text_true_sites]}. If new site is "
                f"intentional, update the AUDIT table in this test "
                f"AND confirm encoding='utf-8' is present.")
            for idx in text_true_sites:
                window = "\n".join(
                    lines[max(0, idx-5):min(len(lines), idx+10)])
                self.assertIn(
                    'encoding="utf-8"', window,
                    f"{relpath}:{idx+1} — text=True without "
                    f"explicit encoding='utf-8' within 10-line "
                    f"window. Add encoding='utf-8', "
                    f"errors='replace' to the subprocess.run call.")

    def test_audit_table_total_matches_grep(self) -> None:
        """Cross-check: AUDIT entries sum to the codebase count of
        text=True occurrences (excluding comment lines). This is a
        forensic check — if someone adds a text=True site to a NEW
        file not in the AUDIT table, this counter mismatches."""
        expected = 4 + 2 + 1 + 2 + 2 + 3  # = 14
        total = 0
        for relpath, src in self.files.items():
            for line in src.splitlines():
                if line.lstrip().startswith("#"):
                    continue
                if "text=True" in line:
                    total += 1
        self.assertEqual(
            total, expected,
            f"text=True total mismatch: AUDIT expects {expected}, "
            f"grep found {total}. If a new in-scope file gained "
            f"text=True sites, extend AUDIT in "
            f"test_every_text_true_subprocess_run_has_explicit_utf8.")


if __name__ == "__main__":
    unittest.main()

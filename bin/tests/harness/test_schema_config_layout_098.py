"""v1.5.7 098 — tracked SCHEMA.md + tracked config.example.json
+ live-config fallback loader.

Per the owner decision (2026-05-25): SCHEMA.md + a sanitized
config example move from the wholesale-gitignored
``repos/`` subtree to the tracked ``bin/harness/`` location
(which the bundle-safety allowlist already excludes from the
adopter install closure). The LIVE ``config.json`` stays
gitignored in ``repos/security-test-cases/`` because it
carries machine-specific paths. The ``cases.json`` security
CVE set is UNTOUCHED — still gitignored, still private.

Test surfaces:

  SchemaMdLocationTests — the new tracked location works; the
    old path no longer ships content under tracked code; the
    file is intentionally NOT in the install closure.
  ConfigExampleTrackedTests — the example exists at
    ``harness_plans/config.example.json``, parses as JSON,
    carries no machine-specific absolute paths.
  LoadConfigFallbackTests — live config.json present → used;
    live absent → falls back to the tracked example; both
    absent → SchedulerConfig defaults.
  BundleSafetyStillGreenTests — `bin/harness/SCHEMA.md` and
    `harness_plans/config.example.json` are NOT in
    ``_bundle_files()``; ``bin/__init__.py`` carries no
    'harness' substring.
  CasesJsonStillPrivateTests — `repos/security-test-cases/
    cases.json` is gitignored; no tracked code points at a
    tracked cases.json.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from bin.harness import scheduler as SCH


_REPO_ROOT = Path(__file__).resolve().parents[3]
_HARNESS_DIR = _REPO_ROOT / "bin" / "harness"
_SCHEMA_MD = _HARNESS_DIR / "SCHEMA.md"
# v1.5.7 133: config.example.json moved bin/harness/ → harness_plans/
# (code/data separation). _HARNESS_DIR stays bin/harness/ for the
# SCHEMA.md-deleted / no-cases.json / *.py-glob checks below.
_CONFIG_EXAMPLE = _REPO_ROOT / "harness_plans" / "config.example.json"
_OLD_SCHEMA_PATH = _REPO_ROOT / "repos" / "security-test-cases" / "SCHEMA.md"


# ---------------------------------------------------------------------------
# Task A: SCHEMA.md moved to bin/harness/
# ---------------------------------------------------------------------------


class SchemaMdLocationTests(unittest.TestCase):

    def test_schema_md_deleted_at_both_locations(self) -> None:
        """v1.5.7 099 update: SCHEMA.md was DELETED per the
        simplified plan-runner model (design's ⚠️ SIMPLIFIED
        RUNNER MODEL section). The §F vocabulary now lives in
        code (closed enums in schema.py); the one-line header in
        the plan file is self-documenting. These tests pin the
        deletion at BOTH the original `repos/` path (removed by
        098) and the brief `bin/harness/` path (added by 098,
        deleted by 099)."""
        self.assertFalse(
            _SCHEMA_MD.is_file(),
            f"v1.5.7 099: bin/harness/SCHEMA.md must be DELETED "
            f"per the simplified plan-runner model.",
        )
        self.assertFalse(
            _OLD_SCHEMA_PATH.is_file(),
            f"v1.5.7 098+099: old repos/ path also removed.",
        )

    def test_no_dangling_schema_md_references_in_code(self) -> None:
        """No tracked .py under bin/harness/ references the
        deleted SCHEMA.md (either path)."""
        for py in _HARNESS_DIR.glob("*.py"):
            text = py.read_text(encoding="utf-8")
            self.assertNotIn(
                "repos/security-test-cases/SCHEMA.md", text,
                f"v1.5.7 099: {py.name} still references the "
                f"deleted repos/ SCHEMA.md path.",
            )
            self.assertNotIn(
                "bin/harness/SCHEMA.md", text,
                f"v1.5.7 099: {py.name} still references the "
                f"deleted bin/harness/SCHEMA.md path.",
            )


# ---------------------------------------------------------------------------
# Task B: config.example.json tracked
# ---------------------------------------------------------------------------


class ConfigExampleTrackedTests(unittest.TestCase):

    def test_config_example_exists(self) -> None:
        self.assertTrue(_CONFIG_EXAMPLE.is_file())

    def test_config_example_parses_as_json(self) -> None:
        data = json.loads(_CONFIG_EXAMPLE.read_text(
            encoding="utf-8",
        ))
        self.assertIsInstance(data, dict)
        # Top-level "scheduler" subobject carries the per-vendor
        # caps + cooldowns the loader consumes.
        self.assertIn("scheduler", data)

    def test_no_machine_specific_absolute_paths(self) -> None:
        """The tracked example must NOT carry absolute paths
        (no leading ``/`` outside of the doc-string comment).
        Operators set machine-specific paths in the live
        config.json."""
        text = _CONFIG_EXAMPLE.read_text(encoding="utf-8")
        # Scan for likely absolute-path tokens. The conservative
        # signal: any quoted-string value starting with ``"/``.
        # Tolerate the URL-shaped values inside $comment fields
        # by only scanning the parsed JSON (not the raw text).
        data = json.loads(text)

        def _walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k.startswith("$"):
                        continue  # skip $schema_note / $comment
                    _walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    _walk(v)
            elif isinstance(obj, str):
                self.assertFalse(
                    obj.startswith("/"),
                    f"v1.5.7 098 Task B: tracked example must "
                    f"have NO machine-specific absolute paths. "
                    f"Found leading-slash value: {obj!r}.",
                )

        _walk(data)


# ---------------------------------------------------------------------------
# Task B (continued): load_config fallback
# ---------------------------------------------------------------------------


class LoadConfigFallbackTests(unittest.TestCase):

    def test_live_config_used_when_present(self) -> None:
        """live ``<runner_root>/config.json`` present → loader
        uses it (NOT the example)."""
        with tempfile.TemporaryDirectory() as td:
            runner_root = Path(td)
            (runner_root / "config.json").write_text(json.dumps({
                "scheduler": {
                    "vendor_caps": {"anthropic": 5},
                    "global_cap": 99,
                },
            }))
            cfg = SCH.load_config(runner_root)
            self.assertEqual(cfg.cap_for(SCH.Vendor.ANTHROPIC), 5)
            self.assertEqual(cfg.global_cap, 99)

    def test_fallback_to_tracked_example_when_live_absent(
            self) -> None:
        """live config.json absent → loader falls back to
        ``harness_plans/config.example.json``. The example has
        anthropic cap=1, global_cap=4 (the defaults a fresh
        install starts at)."""
        with tempfile.TemporaryDirectory() as td:
            runner_root = Path(td)
            # No config.json in runner_root — fallback path.
            cfg = SCH.load_config(runner_root)
            # The example's anthropic cap is 1 + global_cap 4.
            self.assertEqual(cfg.cap_for(SCH.Vendor.ANTHROPIC), 1)
            self.assertEqual(cfg.global_cap, 4)

    def test_no_runner_root_falls_back_to_example(self) -> None:
        """``load_config(None)`` falls back to the tracked
        example."""
        cfg = SCH.load_config(None)
        self.assertEqual(cfg.cap_for(SCH.Vendor.ANTHROPIC), 1)
        self.assertEqual(cfg.global_cap, 4)

    def test_malformed_live_falls_through(self) -> None:
        """Malformed live JSON → loader falls through to the
        tracked example (defensive; no crash)."""
        with tempfile.TemporaryDirectory() as td:
            runner_root = Path(td)
            (runner_root / "config.json").write_text("not json")
            cfg = SCH.load_config(runner_root)
            # Fell back to the example (anthropic cap=1).
            self.assertEqual(cfg.cap_for(SCH.Vendor.ANTHROPIC), 1)


# ---------------------------------------------------------------------------
# Task D: bundle-safety still green
# ---------------------------------------------------------------------------


class BundleSafetyStillGreenTests(unittest.TestCase):

    def test_schema_md_not_in_bundle_files(self) -> None:
        from bin.install_skill import _bundle_files
        bundle = _bundle_files(_REPO_ROOT)
        dests = [str(dst) for _src, dst in bundle]
        for p in dests:
            self.assertFalse(
                "harness/SCHEMA.md" in p or p.endswith("SCHEMA.md")
                and "harness" in p,
                f"v1.5.7 098: bin/harness/SCHEMA.md MUST NOT "
                f"enter the install closure. Leaked: {p!r}",
            )

    def test_config_example_not_in_bundle_files(self) -> None:
        from bin.install_skill import _bundle_files
        bundle = _bundle_files(_REPO_ROOT)
        dests = [str(dst) for _src, dst in bundle]
        for p in dests:
            self.assertNotIn(
                "config.example.json", p,
                f"v1.5.7 098: harness_plans/config.example.json "
                f"MUST NOT enter the install closure. Leaked: "
                f"{p!r}",
            )

    def test_init_py_still_no_harness_substring(self) -> None:
        """The 091 release-gate pin: ``bin/__init__.py`` carries
        no 'harness' substring (an import here would leak the
        harness into every adopter install)."""
        init_py = (_REPO_ROOT / "bin" / "__init__.py")
        text = init_py.read_text(encoding="utf-8")
        self.assertNotIn(
            "harness", text,
            "v1.5.7 098 (re-checked): bin/__init__.py must NOT "
            "reference 'harness'.",
        )


# ---------------------------------------------------------------------------
# Task C: cases.json stays private (no change)
# ---------------------------------------------------------------------------


class CasesJsonStillPrivateTests(unittest.TestCase):
    """Per Task C: 098 does NOT move or track cases.json. It's
    the private security CVE set with answer keys."""

    def test_no_tracked_cases_json_under_bin_harness(self) -> None:
        """``bin/harness/cases.json`` MUST NOT exist (the
        cases stay private; only SCHEMA.md + config.example.json
        ship)."""
        self.assertFalse(
            (_HARNESS_DIR / "cases.json").is_file(),
            "v1.5.7 098 Task C: cases.json must stay PRIVATE "
            "in repos/security-test-cases/ — not tracked under "
            "bin/harness/.",
        )

    def test_no_tracked_acceptance_cases_json_yet(self) -> None:
        """Task C explicit note: the 4 acceptance cases
        (ACC-A/B/C/D) stay in the private cases.json for now;
        a future split into a tracked
        bin/harness/acceptance_cases.json is a DEFERRED option
        the orchestrator may pick up. Pinned NOT done yet."""
        self.assertFalse(
            (_HARNESS_DIR / "acceptance_cases.json").is_file(),
            "v1.5.7 098 Task C: acceptance-cases-split is a "
            "DEFERRED option, NOT performed in 098.",
        )


if __name__ == "__main__":
    unittest.main()

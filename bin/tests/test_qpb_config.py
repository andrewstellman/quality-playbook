"""v1.5.7 Phase 6c: regression tests for bin/qpb_config.py.

Nine acceptance scenarios per instruction 020's B4 list:
  1. No config file → built-in defaults (load_config returns None).
  2. Config file → overrides built-in default.
  3. CLI flag → overrides config file (verified via _apply_qpb_config_overrides).
  4. Typo in council_members → startup warning (validate_roster + stderr).
  5. Round-trip (save_config / load_config).
  6. unset_key removes a key.
  7. Atomic write (temp-file rename failure leaves original unchanged).
  8. XDG_CONFIG_HOME resolution priority.
  9. Malformed JSON handling (warning + None return).

All tests use a temp XDG_CONFIG_HOME to avoid touching the real
~/.qpb/config.json on the operator's machine.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import qpb_config


class _XdgTestCase(unittest.TestCase):
    """Base: every test uses a fresh temp dir as $XDG_CONFIG_HOME."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self._patch = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self._tmp.name})
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmp.cleanup()


class LoadConfigTests(_XdgTestCase):
    """Tests #1, #2, #9: load_config behavior across the three states."""

    def test_no_config_file_returns_none(self) -> None:
        # No config file written; load_config returns None.
        self.assertIsNone(qpb_config.load_config())

    def test_config_file_returns_parsed_dict(self) -> None:
        # Plant a config file; load_config returns its contents.
        cfg_dir = Path(self._tmp.name) / "qpb"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.json").write_text(
            json.dumps({"runner": "cursor", "council_members": ["claude-opus-4.7"]}),
            encoding="utf-8",
        )
        result = qpb_config.load_config()
        self.assertEqual(result, {"runner": "cursor", "council_members": ["claude-opus-4.7"]})

    def test_malformed_json_emits_warning_and_returns_none(self) -> None:
        cfg_dir = Path(self._tmp.name) / "qpb"
        cfg_dir.mkdir(parents=True)
        (cfg_dir / "config.json").write_text("{ this is not valid json", encoding="utf-8")
        buf = io.StringIO()
        with redirect_stderr(buf):
            result = qpb_config.load_config()
        self.assertIsNone(result)
        self.assertIn("malformed JSON", buf.getvalue())


class SaveConfigTests(_XdgTestCase):
    """Tests #5, #6, #7: save_config / unset_key / atomic-write."""

    def test_round_trip(self) -> None:
        qpb_config.save_config({"runner": "cursor"})
        cfg = qpb_config.load_config()
        self.assertEqual(cfg, {"runner": "cursor"})

        qpb_config.save_config({"council_members": ["claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6"]})
        cfg = qpb_config.load_config()
        self.assertEqual(cfg["runner"], "cursor")
        self.assertEqual(cfg["council_members"],
                         ["claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6"])

    def test_unset_key_removes_key(self) -> None:
        qpb_config.save_config({"runner": "cursor", "council_members": ["x"]})
        qpb_config.unset_key("runner")
        cfg = qpb_config.load_config()
        self.assertIsNone(cfg.get("runner"))
        self.assertEqual(cfg.get("council_members"), ["x"])

    def test_atomic_write_temp_rename_failure_preserves_original(self) -> None:
        # Plant an original config.
        qpb_config.save_config({"runner": "copilot"})
        original_path = qpb_config.default_config_path()
        original_content = original_path.read_text(encoding="utf-8")

        # Mock os.replace to raise; save_config should not corrupt the original.
        with mock.patch.object(os, "replace", side_effect=OSError("simulated rename failure")):
            with self.assertRaises(OSError):
                qpb_config.save_config({"runner": "cursor"})

        # Original file unchanged.
        self.assertEqual(
            original_path.read_text(encoding="utf-8"),
            original_content,
        )


class ValidateRosterTests(_XdgTestCase):
    """Test #4: typo / unknown identifier handling."""

    def test_known_identifiers_produce_no_warnings(self) -> None:
        warnings = qpb_config.validate_roster(
            ["claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6"]
        )
        self.assertEqual(warnings, [])

    def test_unknown_identifier_produces_warning(self) -> None:
        warnings = qpb_config.validate_roster(
            ["claude-opus-4.7", "definitely-not-a-real-model", "claude-sonnet-4.6"]
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("definitely-not-a-real-model", warnings[0])
        self.assertIn("unrecognized model identifier", warnings[0])

    def test_historical_roster_strings_not_flagged(self) -> None:
        # v1.5.6 roster: gpt-5.4, gemini-2.5-pro. Adopter configs that
        # pin the old roster should NOT generate warnings (KNOWN list
        # includes them).
        warnings = qpb_config.validate_roster(["gpt-5.4", "gemini-2.5-pro"])
        self.assertEqual(warnings, [])


class CLISubcommandTests(_XdgTestCase):
    """Tests #5, #6: round-trip via the CLI sub-commands."""

    def test_set_runner_then_show_round_trip(self) -> None:
        rc = qpb_config.main(["set-runner", "cursor"])
        self.assertEqual(rc, 0)
        cfg = qpb_config.load_config()
        self.assertEqual(cfg["runner"], "cursor")

    def test_set_roster_with_typo_emits_warning(self) -> None:
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            rc = qpb_config.main([
                "set-roster",
                "claude-opus-4.7,nope-not-a-model,claude-sonnet-4.6",
            ])
        self.assertEqual(rc, 0)
        self.assertIn("nope-not-a-model", buf_err.getvalue())
        self.assertIn("unrecognized", buf_err.getvalue())

    def test_set_roster_empty_returns_error(self) -> None:
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            rc = qpb_config.main(["set-roster", ""])
        self.assertEqual(rc, 2)
        self.assertIn("empty roster", buf_err.getvalue())

    def test_unset_cli_removes_key(self) -> None:
        qpb_config.main(["set-runner", "cursor"])
        qpb_config.main(["set-roster", "claude-opus-4.7,gpt-5.5,claude-sonnet-4.6"])
        rc = qpb_config.main(["unset", "runner"])
        self.assertEqual(rc, 0)
        cfg = qpb_config.load_config()
        self.assertIsNone(cfg.get("runner"))
        self.assertEqual(cfg.get("council_members"),
                         ["claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6"])


class XdgResolutionTests(_XdgTestCase):
    """Test #8: XDG_CONFIG_HOME resolution priority."""

    def test_xdg_path_wins_over_home_path(self) -> None:
        # The base class sets XDG_CONFIG_HOME to a temp dir; verify
        # config_path() returns the XDG path when it exists.
        qpb_config.save_config({"runner": "from-xdg"})
        cfg_path = qpb_config.config_path()
        self.assertTrue(str(cfg_path).startswith(self._tmp.name))
        self.assertEqual(cfg_path.name, "config.json")
        # Load returns the XDG content.
        self.assertEqual(qpb_config.load_config()["runner"], "from-xdg")

    def test_default_config_path_respects_xdg(self) -> None:
        path = qpb_config.default_config_path()
        self.assertEqual(path, Path(self._tmp.name) / "qpb" / "config.json")


class ApplyQpbConfigOverridesTests(_XdgTestCase):
    """Test #3 (CLI vs config): bin/run_playbook._apply_qpb_config_overrides
    overlay behavior."""

    def test_config_runner_overlays_when_no_cli_flag(self) -> None:
        from bin import run_playbook
        qpb_config.save_config({"runner": "cursor"})
        args = argparse.Namespace(runner="copilot", council_roster=None)
        run_playbook._apply_qpb_config_overrides(args, effective_argv=[])
        # No CLI flag: config's "cursor" wins over argparse default.
        self.assertEqual(args.runner, "cursor")

    def test_cli_runner_flag_wins_over_config(self) -> None:
        from bin import run_playbook
        qpb_config.save_config({"runner": "cursor"})
        args = argparse.Namespace(runner="claude", council_roster=None)
        # Effective argv has --claude → don't apply config override.
        run_playbook._apply_qpb_config_overrides(args, effective_argv=["--claude", "some-target"])
        self.assertEqual(args.runner, "claude")

    def test_config_roster_overlays_when_no_cli_flag(self) -> None:
        from bin import run_playbook
        qpb_config.save_config({"council_members": ["claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6"]})
        args = argparse.Namespace(runner="copilot", council_roster=None)
        run_playbook._apply_qpb_config_overrides(args, effective_argv=[])
        self.assertEqual(args.council_roster, "claude-opus-4.7,gpt-5.5,claude-sonnet-4.6")


if __name__ == "__main__":
    unittest.main()

"""v1.5.7 Phase 6a follow-on: dedicated test file for the Council roster pin.

The canonical roster lives at `bin/council_config.DEFAULT_COUNCIL_MEMBERS`.
This test asserts the exact tuple value so a future edit that accidentally
drifts the roster (typo, reorder, missing entry) fails the test suite
during release prep instead of after tag.

The historical home of this pin was `test_council_semantic_check.py::
CouncilConfigTests`, which is preserved there as a roster-shape assertion
(length + member presence). This dedicated file adds the stricter
value-pin per the Phase 6 Council Lens-1 fixup request.

v1.5.7 instruction 052 / ship-blocker A-9 extends this file with
`CouncilMembersOverrideTests`: `council_members()` must consult the
per-operator `~/.qpb/config.json` `council_members` override (it
previously returned the hardcoded `DEFAULT_COUNCIL_MEMBERS` and the
override was silently ignored end-to-end).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin.council_config import DEFAULT_COUNCIL_MEMBERS, council_members


class CouncilRosterPinTests(unittest.TestCase):
    """Pin the canonical roster's exact tuple value."""

    def test_default_council_members_exact_value(self) -> None:
        """v1.5.7 Phase 6a swap: the active roster is
        (claude-opus-4.7, gpt-5.5, claude-sonnet-4.6).

        If this test fails, either (a) a roster swap landed without
        updating this pin (update the pin AND ensure the prior roster
        identifiers are preserved verbatim in any archived Council
        responses / historical synthesis docs), or (b) someone
        accidentally drifted the tuple (revert).
        """
        self.assertEqual(
            DEFAULT_COUNCIL_MEMBERS,
            ("claude-opus-4.7", "gpt-5.5", "claude-sonnet-4.6"),
        )

    def test_council_members_returns_default_with_no_override(self) -> None:
        """council_members() returns the canonical tuple WHEN no
        per-operator override is in effect.

        v1.5.7 instruction 052 / ship-blocker A-9 semantics change:
        this assertion was previously unconditional
        (`council_members() == DEFAULT_COUNCIL_MEMBERS`), which pinned
        the *old buggy* behavior — council_members() ignored
        ~/.qpb/config.json entirely. Post-A-9 it consults the config,
        so the no-override fallback must be asserted under an isolated
        environment (otherwise this test reads the operator's real
        ~/.qpb/config.json and is non-deterministic — exactly what a
        stray D6-test config does). The override-present behavior is
        covered by CouncilMembersOverrideTests below.
        """
        with TemporaryDirectory() as xdg, TemporaryDirectory() as home:
            with mock.patch.dict(
                os.environ, {"XDG_CONFIG_HOME": xdg, "HOME": home}
            ), mock.patch.object(Path, "home", return_value=Path(home)):
                self.assertEqual(council_members(), DEFAULT_COUNCIL_MEMBERS)

    def test_roster_has_three_distinct_members(self) -> None:
        """Phase 6 Council audit requires three reviewers (per
        invariant #17). Duplicate members would silently collapse the
        2-of-3 vote and break the audit."""
        self.assertEqual(len(DEFAULT_COUNCIL_MEMBERS), 3)
        self.assertEqual(len(set(DEFAULT_COUNCIL_MEMBERS)), 3,
                         f"Roster must have 3 DISTINCT members; "
                         f"got duplicates in {DEFAULT_COUNCIL_MEMBERS}")


@contextlib.contextmanager
def _qpb_config_unimportable():
    """Make BOTH soft-import forms in council_members()
    (`from . import qpb_config` and `import qpb_config`) raise
    ImportError, deterministically.

    Setting `sys.modules[name] = None` is not sufficient on its own:
    `from . import qpb_config` resolves via the `qpb_config` attribute
    already bound on the `bin` package object (set when any earlier
    test imported it), so it never re-consults sys.modules. We also
    delattr that package attribute for the duration, then restore it.
    """
    import bin as _bin_pkg

    had_attr = hasattr(_bin_pkg, "qpb_config")
    saved_attr = getattr(_bin_pkg, "qpb_config", None)
    if had_attr:
        delattr(_bin_pkg, "qpb_config")
    try:
        with mock.patch.dict(
            sys.modules, {"bin.qpb_config": None, "qpb_config": None}
        ):
            yield
    finally:
        if had_attr:
            setattr(_bin_pkg, "qpb_config", saved_attr)


class CouncilMembersOverrideTests(unittest.TestCase):
    """v1.5.7 instruction 052 / ship-blocker A-9: council_members()
    must honor the ~/.qpb/config.json `council_members` override.

    Isolation: every test points BOTH $XDG_CONFIG_HOME AND $HOME at
    fresh temp dirs AND patches pathlib.Path.home() to the temp HOME,
    so qpb_config.config_path()'s fallback chain (XDG → ~/.qpb) can
    never reach the operator's real ~/.qpb/config.json. Without the
    $HOME / Path.home() isolation, an empty XDG dir would fall through
    to the real ~/.qpb/config.json and these tests would be
    non-deterministic whenever a stray D6-test config is present (the
    same env pollution that affects test_qpb_config in a dirty env).
    """

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self._home = TemporaryDirectory()
        self._env = mock.patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": self._tmp.name, "HOME": self._home.name},
        )
        self._env.start()
        self._home_patch = mock.patch.object(
            Path, "home", return_value=Path(self._home.name)
        )
        self._home_patch.start()

    def tearDown(self) -> None:
        self._home_patch.stop()
        self._env.stop()
        self._home.cleanup()
        self._tmp.cleanup()

    def _write_config(self, payload: object) -> None:
        cfg_dir = Path(self._tmp.name) / "qpb"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "config.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )

    def test_council_members_returns_default_when_no_config(self) -> None:
        """No config file anywhere on the (isolated) fallback chain →
        the canonical hardcoded roster."""
        self.assertEqual(council_members(), DEFAULT_COUNCIL_MEMBERS)

    def test_council_members_returns_override_when_config_present(self) -> None:
        """The A-9 fix: a valid `council_members` override flows through
        council_members() to every caller (Phase 6 dispatch + banner).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-052 A-9:

          Mutation: revert bin/council_config.py:council_members() to its
          prior one-line body ``return DEFAULT_COUNCIL_MEMBERS`` (delete
          the instruction-052 qpb_config-consultation block).
          Expected failure: THIS test fails at the assertEqual with
            AssertionError: tuples differ:
            ('claude-opus-4.7', 'gpt-5.5', 'claude-sonnet-4.6')
            != ('custom-1', 'custom-2', 'custom-3')
          because council_members() ignores the planted override and
          returns the hardcoded default — the exact A-9 symptom from
          the instruction's confirmed repro.
          Restoration: re-apply the instruction-052 body → this test
          passes (council_members() returns the override tuple).
          Bite executed during instruction-052 development: PASS→FAIL
          on mutation, FAIL→PASS on restore, confirmed. __pycache__
          was purged between mutate and restore so a stale .pyc could
          not mask the restored-clean state.
        """
        self._write_config(
            {"council_members": ["custom-1", "custom-2", "custom-3"]}
        )
        self.assertEqual(
            council_members(), ("custom-1", "custom-2", "custom-3")
        )

    def test_council_members_emits_warning_for_unknown_identifiers(self) -> None:
        """Unknown identifiers are non-fatal (validate_roster contract,
        qpb_config.py:196-210): the warning is emitted to stderr AND
        the override is still applied."""
        self._write_config(
            {"council_members": ["claude-opus-4.7", "bogus-model-x", "gpt-5.5"]}
        )
        buf = io.StringIO()
        with redirect_stderr(buf):
            members = council_members()
        self.assertEqual(
            members, ("claude-opus-4.7", "bogus-model-x", "gpt-5.5")
        )
        err = buf.getvalue()
        self.assertIn("bogus-model-x", err)
        self.assertIn("unrecognized model identifier", err)

    def test_council_members_falls_back_on_malformed_config(self) -> None:
        """Three malformed shapes each emit a stderr warning and fall
        back to DEFAULT_COUNCIL_MEMBERS without crashing the runner."""
        for payload, label in (
            ({"council_members": "claude-opus-4.7"}, "not-a-list"),
            ({"council_members": []}, "empty-list"),
            (
                {"council_members": ["claude-opus-4.7", 42, "gpt-5.5"]},
                "non-string-entry",
            ),
        ):
            with self.subTest(case=label):
                self._write_config(payload)
                buf = io.StringIO()
                with redirect_stderr(buf):
                    members = council_members()
                self.assertEqual(members, DEFAULT_COUNCIL_MEMBERS)
                self.assertIn("malformed", buf.getvalue())

    def test_council_members_falls_back_when_qpb_config_unavailable(self) -> None:
        """Soft-import failure (minimal install / isolated fixture):
        even with a valid override planted, an unimportable qpb_config
        fails closed to DEFAULT_COUNCIL_MEMBERS — no exception escapes."""
        self._write_config(
            {"council_members": ["custom-1", "custom-2", "custom-3"]}
        )
        with _qpb_config_unimportable():
            members = council_members()
        self.assertEqual(members, DEFAULT_COUNCIL_MEMBERS)


if __name__ == "__main__":
    unittest.main()

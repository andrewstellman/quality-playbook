"""v1.5.7 187 — opt-in iteration strategies via PlanRun.include_iterations.

Andrew's first methodologically-trustworthy blind CVE benchmark
(`harness_runs/20260602T222932Z`) ran QPB without iteration
strategies — setuptools DETECTED its target CVE but jsPDF
MISSED in a domain (LFI) where the adversarial pass would
plausibly help. The Mode A launch prompt at
`bin/harness/plan_runner.py:147` hardcoded "Do not run the
iteration strategies"; that was right for acceptance plans (the
106 design) but wrong for blind-bug-hunt plans.

187 makes it opt-in per plan row:
- FINDING-37: NEW `PlanRun.include_iterations: bool = False`
  dataclass field + plan-JSON parser support.
- FINDING-38: NEW `_MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS`
  constant; launch sites select between original and
  iterations-enabled based on the field.
- FINDING-39: Default-False so every existing acceptance plan
  + every plan that hasn't been updated continues unchanged.
- FINDING-40: `harness_plans/security_blind_v2_rebuild.json`
  edited to opt in (all 7 rows).
"""
from __future__ import annotations

import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[3]


def _base_plan_row(**overrides) -> dict:
    """Minimal acceptable PlanRun dict for parser tests."""
    row = {
        "description": "test row",
        "repo": "https://github.com/x/y",
        "ref": "HEAD",
        "runner": "claude",
        "model": "opus",
        "channel": "pip-local-wheel",
    }
    row.update(overrides)
    return row


class PlanRunIncludeIterationsTests(unittest.TestCase):
    """v1.5.7 187 FINDING-37: include_iterations field on
    PlanRun. Strict bool typing; default False; threaded
    through the JSON parser."""

    def test_include_iterations_default_false(self) -> None:
        # Parsing a row WITHOUT the field yields
        # include_iterations=False (acceptance plans unchanged).
        from bin.harness.plan_runner import (
            _parse_run,
        )
        run = _parse_run(0, _base_plan_row())
        self.assertIs(
            run.include_iterations, False,
            "Default must be False so every existing plan "
            "continues unchanged (187 FINDING-39).")

    def test_include_iterations_true_parsed(self) -> None:
        from bin.harness.plan_runner import (
            _parse_run,
        )
        run = _parse_run(
            0, _base_plan_row(include_iterations=True))
        self.assertIs(run.include_iterations, True)

    def test_include_iterations_false_explicit_parsed(
            self) -> None:
        # An explicit `false` value must be honored (operator
        # may have it in a plan for documentation purposes).
        from bin.harness.plan_runner import (
            _parse_run,
        )
        run = _parse_run(
            0, _base_plan_row(include_iterations=False))
        self.assertIs(run.include_iterations, False)

    def test_include_iterations_string_rejected(self) -> None:
        # The string "true" / "yes" must be REJECTED — strict
        # bool typing. An operator typo (`"true"` instead of
        # `true`) would silently change behavior on every
        # blind row; the explicit error catches it.
        from bin.harness.plan_runner import (
            _parse_run, PlanError,
        )
        with self.assertRaises(PlanError) as ctx:
            _parse_run(
                3,
                _base_plan_row(include_iterations="yes"))
        msg = str(ctx.exception)
        self.assertIn("include_iterations", msg)
        self.assertIn("runs[3]", msg)

    def test_include_iterations_int_rejected(self) -> None:
        # 0 / 1 are not booleans either (despite Python's
        # 1 == True). bool is the contract.
        from bin.harness.plan_runner import (
            _parse_run, PlanError,
        )
        with self.assertRaises(PlanError):
            _parse_run(
                0,
                _base_plan_row(include_iterations=1))


class LaunchPromptSelectionTests(unittest.TestCase):
    """v1.5.7 187 FINDING-38: launch path picks between the
    two Mode A prompts based on PlanRun.include_iterations."""

    def test_default_prompt_excludes_iterations(self) -> None:
        from bin.harness import plan_runner as _pr
        self.assertIn(
            "Do not run the iteration strategies",
            _pr._MODE_A_FULL_RUN_PROMPT,
            "_MODE_A_FULL_RUN_PROMPT must explicitly tell the "
            "agent NOT to run iterations (the 106 contract).")

    def test_iterations_prompt_enumerates_4_strategies(
            self) -> None:
        from bin.harness import plan_runner as _pr
        self.assertIn(
            "iteration strategies (gap, unfiltered, parity, "
            "adversarial)",
            _pr._MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS,
            "_MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS must "
            "enumerate the 4 strategies (matches QPB's "
            "documented default).")

    def test_iterations_prompt_does_not_exclude_iterations(
            self) -> None:
        from bin.harness import plan_runner as _pr
        self.assertNotIn(
            "Do not run the iteration strategies",
            _pr._MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS,
            "_MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS must "
            "NOT carry the iteration-exclusion clause.")

    def test_launch_site_selects_default_when_false(
            self) -> None:
        # Source-pin: the launch path references
        # _MODE_A_FULL_RUN_PROMPT in the else-branch of
        # the include_iterations check.
        src = (_REPO / "bin" / "harness" / "plan_runner.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            "plan_run.include_iterations:", src,
            "launch path must branch on "
            "plan_run.include_iterations (187 FINDING-38).")
        self.assertIn(
            "_MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS", src,
            "launch path must reference the iterations "
            "prompt constant.")

    def test_both_launch_sites_check_prompt_first(
            self) -> None:
        # Source-pin: BOTH launch sites must check
        # plan_run.prompt before plan_run.include_iterations
        # (the operator's verbatim override is the highest-
        # priority selection — 187 FINDING-38 + 106). The
        # instruction calls out two sites; if one is updated
        # symmetrically and the other isn't, the behavior is
        # different in the synchronous-launch vs detached-
        # launch flows.
        src = (_REPO / "bin" / "harness" / "plan_runner.py"
               ).read_text(encoding="utf-8")
        import re
        # Count the if/elif pattern. Two ALL-launch sites
        # exist (one synchronous, one detached) and BOTH
        # must use this shape.
        pattern = re.compile(
            r"if plan_run\.prompt:\s*\n\s*"
            r"launch_prompt = plan_run\.prompt"
            r"\s*\n\s*elif plan_run\.include_iterations:")
        matches = pattern.findall(src)
        self.assertGreaterEqual(
            len(matches), 2,
            f"Both launch sites (synchronous + detached) "
            f"must check plan_run.prompt FIRST, then "
            f"plan_run.include_iterations. Found {len(matches)} "
            f"matching site(s); expected ≥2 (187 FINDING-38: "
            f"both reference sites must be updated "
            f"symmetrically).")

    def test_both_launch_sites_use_iterations_prompt(
            self) -> None:
        # Source-pin: BOTH launch sites reference
        # _MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS in their
        # elif branch (catches the case where one site is
        # updated and the other isn't).
        src = (_REPO / "bin" / "harness" / "plan_runner.py"
               ).read_text(encoding="utf-8")
        # In the elif branch the assignment is
        # `launch_prompt = _MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS`.
        # Count occurrences (must appear at least 2x — once
        # per launch site).
        count = src.count(
            "launch_prompt = "
            "_MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS")
        self.assertGreaterEqual(
            count, 2,
            f"Both launch sites must assign "
            f"_MODE_A_FULL_RUN_PROMPT_WITH_ITERATIONS in "
            f"the include_iterations elif branch. Found "
            f"{count} assignment(s); expected ≥2 (187 "
            f"FINDING-38: symmetry across both reference "
            f"sites).")


class ManifestRoundTripTests(unittest.TestCase):
    """v1.5.7 187 FINDING-37 (Panelist C surfaced):
    include_iterations MUST survive the manifest write→read
    round-trip used by the collector's retry path
    (``_retry_pending_runs_once``) and the 186 force-run
    helper (``force_launch_pending_run``). Without persistence,
    every row that starts PENDING and is later acquired via
    the retry path silently reverts to the default prompt —
    defeating FINDING-40 on the blind benchmark's first live
    fire (pool=2, 7 rows ⇒ 5 of 7 rows start PENDING)."""

    def _make_planrun(self, include_iterations: bool):
        from bin.harness.plan_runner import PlanRun
        from bin.harness.schema import (
            InstallChannel, Mode, Runner,
        )
        return PlanRun(
            index=3,
            description="round-trip test row",
            repo="https://github.com/x/y",
            ref="HEAD",
            runner=Runner.CLAUDE,
            model="opus",
            channel=InstallChannel.PIP_LOCAL_WHEEL,
            mode=Mode.A,
            include_iterations=include_iterations,
        )

    def test_pending_manifest_entry_carries_field_true(
            self) -> None:
        from bin.harness import plan_runner as _pr
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260603T000000Z"
            hr.mkdir()
            entry = _pr._make_pending_manifest_entry(
                self._make_planrun(True), hr)
            self.assertIs(
                entry.get("include_iterations"), True,
                "pending manifest entry must carry "
                "include_iterations (187 + Panelist C).")

    def test_pending_manifest_entry_carries_field_false(
            self) -> None:
        from bin.harness import plan_runner as _pr
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260603T000000Z"
            hr.mkdir()
            entry = _pr._make_pending_manifest_entry(
                self._make_planrun(False), hr)
            self.assertIs(
                entry.get("include_iterations"), False)

    def test_entry_to_plan_run_reads_true(self) -> None:
        from bin.harness import plan_runner as _pr
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260603T000000Z"
            hr.mkdir()
            entry = _pr._make_pending_manifest_entry(
                self._make_planrun(True), hr)
            reconstructed = _pr._entry_to_plan_run(entry)
            self.assertIs(
                reconstructed.include_iterations, True,
                "round-trip must preserve True (Panelist C "
                "ship-blocker).")

    def test_entry_to_plan_run_defaults_false_on_pre_187_manifest(
            self) -> None:
        # Backward-compat: a manifest entry from a pre-187
        # harness_runs/ folder won't have the field. The
        # reader must default to False, not crash.
        from bin.harness import plan_runner as _pr
        pre_187_entry = {
            "index": 0, "description": "legacy",
            "repo": "https://github.com/x/y", "ref": "HEAD",
            "runner": "claude", "model": "opus",
            "channel": "pip-local-wheel", "mode": "A",
            # Note: NO include_iterations key.
        }
        reconstructed = _pr._entry_to_plan_run(pre_187_entry)
        self.assertIs(
            reconstructed.include_iterations, False,
            "missing field on pre-187 manifest must default "
            "False (backward-compat).")


class SecurityBlindV2PlanOptsInTests(unittest.TestCase):
    """v1.5.7 187 FINDING-40: the security_blind_v2_rebuild
    plan opts every row in to include_iterations so the next
    blind fire actually exercises the iteration strategies
    that the first fire (20260602T222932Z) missed."""

    def test_every_row_in_security_blind_v2_opts_in(
            self) -> None:
        import json
        plan_path = (
            _REPO / "harness_plans"
            / "security_blind_v2_rebuild.json")
        if not plan_path.is_file():
            self.skipTest("security_blind_v2 plan not present")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        rows = plan.get("runs", [])
        self.assertGreater(
            len(rows), 0, "plan has no runs")
        for i, row in enumerate(rows):
            self.assertIs(
                row.get("include_iterations"), True,
                f"row {i} ({row.get('description', '?')[:40]}"
                f") must have include_iterations=true "
                f"(187 FINDING-40 — blind benchmark MUST "
                f"exercise the iteration strategies).")


if __name__ == "__main__":
    unittest.main()

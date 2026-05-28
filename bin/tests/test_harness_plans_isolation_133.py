"""v1.5.7 instruction 133 — code/data separation: harness plan JSONs
moved out of bin/harness/ into a tracked top-level harness_plans/.

`bin/` is for executable Python; harness INPUT DATA (the plan JSONs +
config.example.json) now lives in harness_plans/ (a peer of agents/,
references/, phase_prompts/). harness_plans/ inherits bundle-exclusion
automatically — the install bundle is an explicit allowlist and
harness_plans/ isn't in it.

These tests pin the new layout so a future stray move/revert is
caught:
  * harness_plans/ does NOT ship (zero bundle entries under it)
  * the 5 plan files exist at their new paths
  * bin/harness/ contains NO *.json (the convention: harness data goes
    in harness_plans/, not alongside the code)
"""
from __future__ import annotations

import pathlib
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "bin"))

from install_skill import _bundle_files  # noqa: E402


_PLANS = (
    "acceptance_plan.json",
    "aup_experiment_plan.json",
    "cap_validation_plan.json",
    "cross_runner_plan.json",
    "config.example.json",
)


class HarnessPlansIsolationTests(unittest.TestCase):

    def test_harness_plans_not_in_bundle(self) -> None:
        leaked = [str(s) for s, _d in _bundle_files(_REPO_ROOT)
                  if str(s).replace("\\", "/").startswith(
                      "harness_plans/")
                  or "harness_plans" in str(_d).replace("\\", "/")]
        self.assertEqual(
            leaked, [],
            f"harness_plans/ must NOT ship in the install bundle; "
            f"leaked: {leaked}")

    def test_five_plans_exist_at_new_paths(self) -> None:
        plans_dir = _REPO_ROOT / "harness_plans"
        for name in _PLANS:
            self.assertTrue(
                (plans_dir / name).is_file(),
                f"expected harness_plans/{name} to exist after the "
                f"133 move")

    def test_bin_harness_has_no_json(self) -> None:
        # Convention pin: harness data files live in harness_plans/,
        # NOT alongside the harness code in bin/harness/. Catches an
        # accidental partial revert or a new plan landing in the wrong
        # place.
        bin_harness = _REPO_ROOT / "bin" / "harness"
        strays = sorted(p.name for p in bin_harness.glob("*.json"))
        self.assertEqual(
            strays, [],
            f"bin/harness/ must contain no *.json after the 133 "
            f"move (harness data belongs in harness_plans/); "
            f"found: {strays}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

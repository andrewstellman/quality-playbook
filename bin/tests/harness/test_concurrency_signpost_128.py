"""v1.5.7 128 — signpost the two coexisting concurrency models
(manager+scheduler vs plan_runner+inflight_registry).

Security review note #3: a reviewer inspecting ``scheduler.py``
alone concluded the global concurrency cap is "per-daemon, not
per-host." That's a misread of the ACTIVE 125 cap
(``inflight_registry.py`` IS per-host — one fcntl.flock'd file
at ``~/.qpb_harness/inflight.json``), but an understandable one:
the manager+scheduler path is a real, exposed ``qpb_harness
manager`` subcommand (NOT dead code) using a DIFFERENT
concurrency model that coexists with run-plan's, and nothing
signposted "two flows; here's which applies when."

128 adds docstring banners (PROSE, zero code change) pointing a
reader between the two flows. These tests pin the signpost as a
contract so a future refactor that drops a banner is caught.
Deliberately blunt presence checks — docstring-as-contract.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import unittest

import bin.harness as H
from bin.harness import manager as M
from bin.harness import scheduler as S
from bin.harness import plan_runner as PR


class ConcurrencySignpost128Tests(unittest.TestCase):

    def test_manager_docstring_names_run_plan_flow(self) -> None:
        # Mutation-bite: delete the manager.py banner ⇒ fails.
        # Case-insensitive: the banner writes "MACHINE-GLOBAL"
        # for emphasis; presence is the contract, not casing.
        doc = (M.__doc__ or "").lower()
        for token in ("run-plan", "plan_runner",
                       "inflight_registry", "machine-global"):
            self.assertIn(token, doc,
                           f"manager.py banner must name "
                           f"{token!r}")

    def test_scheduler_docstring_names_run_plan_flow(self) -> None:
        doc = S.__doc__ or ""
        for token in ("run-plan", "inflight_registry"):
            self.assertIn(token, doc,
                           f"scheduler.py banner must name "
                           f"{token!r}")
        # The existing "PURE STATE" framing must be preserved.
        self.assertIn("PURE STATE", doc)

    def test_init_docstring_maps_both_flows(self) -> None:
        doc = H.__doc__ or ""
        for token in ("run-plan", "manager",
                       "inflight_registry", "scheduler",
                       "concurrency"):
            self.assertIn(token, doc,
                           f"bin.harness __init__ docstring "
                           f"must name {token!r}")
        # Bundle-isolation message must remain intact.
        self.assertIn("excluded from the install bundle", doc)

    def test_plan_runner_docstring_acknowledges_split(
            self) -> None:
        # The reworded SUPERSEDES line must name "manager" so it's
        # honest about what was / wasn't superseded.
        doc = PR.__doc__ or ""
        self.assertIn("manager", doc)
        self.assertIn("run-plan", doc)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()

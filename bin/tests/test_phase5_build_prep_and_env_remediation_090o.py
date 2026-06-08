"""v1.5.7 instruction 090o: Phase 5 build-prep before TDD red/green
+ environment-failure remediation (do NOT degrade silently) + the
load-bearing guard (an assertion failure is a RED, not an environment
failure).

Motivation: 2026-05-24 Ory Keto Mode-A run (Codex / gpt-5.5, pipx
channel install). The Phase 5 green-phase `go test` timed out fetching
`modernc.org/libc` (a huge indirect dep via `modernc.org/sqlite`) on a
cold module cache. The TDD receipt fell back to patch-apply verification
(not test-proven) and the operator got no actionable guidance. After
the operator manually pre-warmed (`go mod download && go build ./...`),
a re-run of Phases 5–6 executed the real red→green and the gate passed.
090o makes the skill do that prep itself and — if it still can't — emit
specific remediation so the operator can fix it and re-run.

The load-bearing guard (Task C in the instruction): build-prep +
remediation apply ONLY to environment shapes (download/network timeout,
dep compile failure in a third-party module, missing toolchain,
cache/permission errors). An assertion failure is a RED — never
reclassified as "environment," never given the remediation/skip path,
never excused. The 089m–q TDD-credibility arc exists precisely to stop
agents laundering failures into passes; this guard is what keeps 090o's
prep+remediation surface from re-opening that hole.

Test surfaces:
  * ``test_phase5_carries_build_prep_directive`` — phase_prompts/phase5.md
    instructs the agent to prep the build via the detected build system
    (Go: `go mod download` + compile warm-up; Node: `npm ci`; Python:
    `pip install`; Rust: `cargo fetch`/build; Java: offline resolution)
    BEFORE the red/green cycle, reusing the env/caches the TDD step
    runs under.
  * ``test_phase5_carries_environment_remediation_directive`` — the
    contract instructs the agent to emit a specific remediation block
    (what failed + the fix command + re-run-Phases-5-6) and record an
    honest NOT_RUN(environment) receipt instead of degrading silently.
  * ``test_phase5_carries_red_vs_environment_guard`` — the load-bearing
    safety guard is present and explicit. Mutation bite: weakening
    the guard so an assertion failure could be laundered as
    "environment" → this test FAILs.
  * ``test_phase5_guard_lists_environment_shapes_explicitly`` — the
    contract enumerates the four environment shapes that qualify for
    the remediation path so the agent has a closed list, not an
    open-ended "is this environment or not?" judgment call.
"""
from __future__ import annotations

import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: phase_prompts/ moved into the plugin skill folder.
_PHASE5 = _REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "phase_prompts" / "phase5.md"


class Phase5BuildPrepAndEnvRemediation090oTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = _PHASE5.read_text(encoding="utf-8")

    def test_phase5_carries_build_prep_directive(self) -> None:
        """Build-prep paragraph (Task A): instructs the agent to
        prepare the build env using the detected build system BEFORE
        the red/green cycle.

        Mutation bite: drop the build-prep paragraph → this test FAILs;
        the Keto cold-cache class regresses (the agent goes straight
        to the timed red/green step without warming the cache, and a
        cold-cache `go test` times out fetching modernc.org/libc).
        """
        # Anchor on the 090o build-prep heading so a future reorg
        # doesn't accidentally drop the paragraph.
        self.assertIn("v1.5.7 090o — build-prep before the red/green",
                      self.text)
        # Each ecosystem from the instruction's list must appear by
        # its canonical command shape — these are the agent's
        # ecosystem-specific cues.
        for required_cue in (
            "go mod download",        # Go
            "npm ci",                 # Node
            "pip install",            # Python
            "cargo fetch",            # Rust
            "Maven",                  # Java
            "build system",           # framing
            "before the red/green",   # placement guarantee
        ):
            self.assertIn(
                required_cue, self.text,
                f"phase5.md build-prep paragraph is missing required "
                f"cue {required_cue!r} — 090o requires ecosystem-"
                f"specific prep cues + 'before the red/green' "
                f"placement.",
            )
        # The SAME env / cache rule — load-bearing for Keto's
        # per-run GOCACHE trap.
        self.assertIn("SAME environment the red/green will use",
                      self.text)
        self.assertIn("GOCACHE", self.text)

    def test_phase5_carries_environment_remediation_directive(
            self) -> None:
        """Env-remediation paragraph (Task B): instructs the agent
        to emit a specific remediation block + NOT_RUN(environment)
        receipt instead of degrading silently.

        Mutation bite: replace the "do NOT degrade silently"
        contract with a silent-fallback ("if prep fails, fall back to
        patch-apply verification") → this test FAILs.
        """
        self.assertIn(
            "v1.5.7 090o — environment-failure remediation",
            self.text,
        )
        self.assertIn("do NOT degrade silently", self.text)
        # The remediation block must contain three required elements:
        # what failed + fix command + re-run-Phases-5-6.
        self.assertIn("what failed", self.text)
        self.assertIn("the exact fix command", self.text)
        self.assertIn("re-run Phases 5–6", self.text)
        # NOT_RUN(environment) receipt classification per 089m–q
        # taxonomy.
        self.assertIn("NOT_RUN", self.text)
        self.assertIn("environment reason", self.text)
        # Never silently fall back — explicit prohibition.
        self.assertIn("never quietly fall back", self.text)
        self.assertIn("never claim GREEN by inspection", self.text)

    def test_phase5_carries_red_vs_environment_guard(self) -> None:
        """THE GUARD (Task C — load-bearing): an assertion failure is
        a RED, not an environment failure. This is what keeps 090o's
        prep+remediation surface from opening the laundering hole the
        089m–q TDD-credibility arc closed.

        Mutation bite (CRITICAL — pins the never-launder guard):
        rewrite the guard so an assertion failure could be classified
        as "environment" (e.g., remove the "An assertion failure is a
        RED, not an environment failure" sentence; remove the
        "never reclassify an assertion failure as 'environment'"
        clause; remove the "default to RED" disambiguation rule) →
        this test FAILs. The 089m–q taxonomy stays load-bearing.
        """
        self.assertIn(
            "v1.5.7 090o — THE GUARD",
            self.text,
        )
        # The core distinction must be stated explicitly, byte-for-byte.
        self.assertIn(
            "An assertion failure is a RED, not an environment failure.",
            self.text,
        )
        # Three "never" prohibitions per the instruction's Task C wording.
        self.assertIn(
            "Never reclassify an assertion failure as \"environment\"",
            self.text,
        )
        self.assertIn(
            "never give a real RED the remediation-and-skip path",
            self.text,
        )
        self.assertIn(
            "never excuse a real RED as a build/dep problem",
            self.text,
        )
        # Cross-reference the 089m–q honesty arc so the guard cites
        # its own purpose.
        self.assertIn("089m–q TDD-credibility arc", self.text)
        self.assertIn("laundering", self.text)
        # The "when in doubt, default to RED" disambiguation rule —
        # the safety direction is "never launder."
        self.assertIn("default to RED", self.text)
        self.assertIn("never launder", self.text)

    def test_phase5_guard_lists_environment_shapes_explicitly(
            self) -> None:
        """The contract must enumerate the 4 environment shapes that
        qualify for the remediation path so the agent has a closed
        list, not an open-ended judgment call. (Closed-list framing
        is what keeps "environment" from becoming a free-floating
        category an agent can stretch to include assertion failures.)

        Mutation bite: drop the enumerated list and replace it with
        an open-ended "any environment-shaped failure" → this test
        FAILs because the closed-list anchors are missing.
        """
        for shape_cue in (
            "download or network timeout",  # shape 1
            "compile failure in a third-party module",  # shape 2
            "missing toolchain",  # shape 3
            "cache/permission errors",  # shape 4
        ):
            self.assertIn(
                shape_cue, self.text,
                f"phase5.md guard is missing environment-shape cue "
                f"{shape_cue!r} — the closed-list framing is what "
                f"keeps 'environment' from being stretched to "
                f"include real REDs.",
            )

    def test_phase5_does_not_re_score_tdd_verdicts(self) -> None:
        """Scope-guard (Halt Condition 2): 090o is additive (prep +
        message), NOT a re-scoring of TDD verdicts. The instruction
        explicitly says: 'this instruction does not change whether
        such a run passes or fails — it adds the prep attempt and the
        actionable message.' The contract must say so explicitly so
        a future edit doesn't quietly turn this into a verdict-shift.

        Mutation bite: add language like 'environment NOT_RUN becomes
        WARN-not-FAIL' or 'environment NOT_RUN is auto-promoted to
        PASS' → this test FAILs (those phrases would re-score the
        verdict, which 090o explicitly does not do).
        """
        # Phase 5 must explicitly say "receipt-acceptance behavior for
        # the verdict is unchanged."
        self.assertIn("receipt-acceptance behavior for the verdict is unchanged",
                      self.text)
        # And the env-NOT_RUN receipt must follow the existing 089m–q
        # taxonomy — no new auto-promote rules.
        self.assertIn("089m–q taxonomy", self.text)

    def test_skill_md_not_touched_by_090o(self) -> None:
        """Halt Condition 3: SKILL.md must NOT be touched (token
        ceiling — keep the contract in phase5.md). The 090o build-
        prep / remediation / guard content lives in phase5.md, not
        SKILL.md.

        This test confirms SKILL.md does not contain the 090o anchors
        — if it does, the contract leaked into the wrong surface.
        """
        skill_text = (_REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "v1.5.7 090o — build-prep before the red/green",
            skill_text,
            "SKILL.md contains a 090o build-prep anchor — 090o's "
            "Halt Condition 3 says 'don't touch SKILL.md'. Keep the "
            "contract in phase_prompts/phase5.md.",
        )
        self.assertNotIn(
            "v1.5.7 090o — THE GUARD",
            skill_text,
            "SKILL.md contains a 090o guard anchor — 090o's Halt "
            "Condition 3 says 'don't touch SKILL.md'. Keep the "
            "contract in phase_prompts/phase5.md.",
        )


if __name__ == "__main__":
    unittest.main()

# Self-review — instruction 018 (Feature H slice 6: maturity disclosure + harness seam)

**Verdict: SHIP.** Per the instruction, this mechanical slice (two small finishes,
no new machinery, no security/correctness-critical surface) gets a focused
self-review rather than a full panelist Council — consistent with the mechanical
persona-catalog slice (013). The three required checks:

## (a) The maturity disclosure fires exactly when rubric-dependent, and not otherwise
- `build_review_summary` now computes `maturity_disclosure` over everything it
  surfaces (applied + candidates + conflict moves). A finding is rubric-dependent
  via `rubric_dependent: True` or a readability `dimension`
  (`_RUBRIC_DIMENSIONS` = well-organized / readability / readable). The caveat
  mirrors F-1's coverage-gaps disclosure: it names the readability (Well-organized)
  rubric, cites §5 Verification (b) "not yet a functional drift detector", and tells
  the operator to treat those with lower confidence — output not resting on the
  rubric is unaffected.
- **Fires iff rubric-dependent** — pinned by `MaturityDisclosureTests`: no caveat
  when everything is Complete/Correct; caveat for a Well-organized applied move; for
  an explicit `rubric_dependent` flag; for a rubric-dependent *candidate*; and the
  `maturity_disclosure` helper counts only rubric items (2 of 4 → "2 of these
  findings"; a non-rubric-only list → None). The disclosure is mechanical (keyed on
  fields the moves carry), not decorative.

## (b) The per-target seam test genuinely exercises a non-H input set through the same path
- `TargetAgnosticSeamTests.test_same_path_serves_H_and_B_input_sets` drives the SAME
  `persona_orchestration.run_personas` (stage → tool-allowlist → executor) with two
  different provisions: H's (`13_api_reference.md` + `REQUIREMENTS.md` + `rubric.md`)
  and a Feature-B-shaped one (`finding.md` + `source_excerpt.go` + `REQ-001.md` +
  `fp_rubric.md`). It asserts each run stages exactly its own target's set, the tool
  restriction is identical (Bash/fetch denied) regardless of target, and **neither
  target's inputs leak into the other** — proving context provisioning is a
  per-target parameter, not H-specific. `test_run_personas_signature_takes_provision_
  as_a_parameter` locks the seam name Feature B binds to. The seam is *asserted*, not
  rebuilt (slice 2 already built it).

## (c) No gating / calibration / Feature-B scope leaked in
- `NoGatingScopeTests` greps `persona_apply.py` and asserts NO
  calibration/verdict/pass_fail/score_threshold/gating machinery — H stays a
  remediator. No Feature B code was added (the B-shaped provision lives only in the
  test as a stand-in). No shared calibration harness introduced. The change touches
  only `persona_apply.py` (the disclosure) + a new test file.
- Note: the orchestrator has an uncommitted `docs/design/QPB_v1.6.0_Design.md` edit
  in the working tree; this instruction did not direct me to commit it, so it was
  left untouched (staged only my own files).

## Verification
Full suite green (see the instruction output for the count); Python 3.14.6. +8 tests.
No existing fixture hand-edited.

**Terminal verdict: SHIP.** After this slice, **Feature H's mechanical build is
complete** — only the live persona run (slice 7) + the integrated Council +
acceptance testing (and bundling the modules adopter-side) remain.

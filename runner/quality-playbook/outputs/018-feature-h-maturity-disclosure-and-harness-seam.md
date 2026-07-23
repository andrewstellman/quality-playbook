# Output for 018-feature-h-maturity-disclosure-and-harness-seam.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/.../scripts/persona_apply.py` | `maturity_disclosure()` + `_is_rubric_dependent()` + `_RUBRIC_DIMENSIONS`; `build_review_summary` now emits a `maturity_disclosure` caveat + a `rubric_dependent` flag per applied entry. |
| `bin/tests/test_persona_maturity_seam_v160.py` | **New** — 8 tests: maturity disclosure fires iff rubric-dependent; the per-target harness-seam lock-in (H + Feature-B input sets through the same path); a no-gating scope check. |
| `docs/process/QPB_v1.6.0_Instruction_018_Self_Council/synthesis.md` | Tracked focused self-review. |
| `runner/.../reviews/018_self_council/synthesis.md` | Gitignored self-review. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `<slice commit>` — Feature H slice 6: maturity disclosure + target-agnostic harness seam (+ 8 tests).
- `75db280` — tracked self-review.

## Acceptance oracle — pass/fail per item
| # | Item | Result |
|---|------|--------|
| 1 | Rubric-dependent run emits the maturity caveat; a non-dependent run does not | **PASS** — `MaturityDisclosureTests` |
| 2 | Orchestration spawns a persona from a Feature-B-shaped input set through the same seam as an H-shaped set; no H-specific input hard-coded | **PASS** — `TargetAgnosticSeamTests` |
| 3 | No calibration harness / gating / verdict introduced (remains a remediator) | **PASS** — `NoGatingScopeTests` |
| 4 | Existing suite unchanged and green | **PASS** — 2731 / 0 / 13 |

## How / when the maturity caveat fires
The readability rubric — the interview's **Well-organized** dimension — is the judgment layer §5 Verification (b) calls "not yet a functional drift detector". `build_review_summary` computes `maturity_disclosure` over everything it surfaces (applied moves + candidates + the moves inside conflicts). A finding is **rubric-dependent** when it carries `rubric_dependent: True` or a readability `dimension` (`well-organized` / `readability` / `readable`). When ≥1 surfaced finding is rubric-dependent, the summary carries an explicit caveat — mirroring F-1's coverage-gaps disclosure — that names the readability rubric, cites §5 Verification (b), and tells the operator to treat those findings with **lower confidence** than the byte-verified grounded changes; findings that do not depend on the rubric are unaffected. A run with **no** rubric-dependent finding carries **no** caveat (`maturity_disclosure` is `None`). It is mechanical (keyed on fields the moves carry), not decorative — `maturity_disclosure([...])` counts only rubric items ("2 of these findings").

## The per-target-seam test + the non-H input set it exercised
`test_same_path_serves_H_and_B_input_sets` drives the **same** `persona_orchestration.run_personas` (stage → tool-allowlist → executor) with two provisions:
- **H-shaped:** `13_api_reference.md` + `REQUIREMENTS.md` + `rubric.md` (docs + rendered spec + rubric).
- **Feature-B-shaped (the OPPOSITE, more-restrictive isolation):** `finding.md` + `source_excerpt.go` + `REQ-001.md` + `fp_rubric.md`.

It asserts each run stages exactly its own target's set, the tool restriction is identical (Bash + fetch denied) regardless of target, and **neither target's inputs leak into the other** — proving context provisioning is a per-target **parameter**, not H-specific. `test_run_personas_signature_takes_provision_as_a_parameter` locks the `provision` parameter name Feature B binds to. The seam is **asserted, not rebuilt** (slice 2 built it); no Feature B was built and no shared calibration harness was introduced.

## Confirmation no calibration / gating crept in
`NoGatingScopeTests` greps `persona_apply.py` and asserts the absence of calibration / verdict / pass_fail / score_threshold / gating machinery. H remains a **remediator, not a gate** — the maturity disclosure is an honesty caveat on the review summary, never a gating decision; the seam is a provisioning parameter, not a judge. The Feature-B-shaped provision exists only as a test stand-in.

## Underspecified / notes
- **Who marks a move rubric-dependent** is the persona's job at run time (slice 7): a Well-organized/readability finding sets `dimension`/`rubric_dependent` on its move. This slice provides the mechanical disclosure that keys on those fields; the actual tagging is the live persona pass. §8b names the disclosure requirement but not the per-move field — this slice defines it (`dimension` / `rubric_dependent`).
- The disclosure spans applied + candidates + conflict moves; it does not (yet) distinguish *how many* of each — a single count suffices for the F-1-style caveat. A future refinement could break it down by bucket if operators want it.

## Feature H — mechanical build complete
After this slice, **Feature H's mechanical build is complete**: guard 2 provenance/write-restriction (012), persona catalog + anchored selection (013), fresh-context orchestration + least-privilege isolation (014), guard 1 grounding + candidate bucket (015), guard 3 merge + conflict surfacing + single renumber (016), guard 4 auto-apply + review summary + concrete revert + off-switch (017), and this slice's maturity disclosure + target-agnostic harness seam (018). **Remaining for Feature H:** the **live persona run (slice 7)** — a full persona pass on chi/express/virtio with a live model finding the real gaps (§8b Verification 1; needs a live vessel, not a code tick) — plus the **integrated end-to-end Council + acceptance testing** across the composed pipeline, and **bundling the six Feature H modules adopter-side** (persona_catalog / persona_orchestration / persona_grounding / persona_merge / persona_apply + requirements_render → the five bundle-drift sites), which naturally lands with the execution/live-run slice.

## Next action expected from orchestrator
Sequence slice 7 — the live persona gap-finding run on chi/express/virtio (§8b Verification 1, a live-model vessel) together with bundling the six Feature H modules into the adopter install and the integrated end-to-end acceptance. Also outstanding: OD-9 (live-repo FP tolerance, set once Feature H has run on the real corpus) and the earlier-recorded items (Feature-G classified-non-plaintext-contracts → FORMAL_DOC wiring; the chi/express Slice-1 coherence-fixture regeneration; the drop/selective-revert BUG-reference re-point hardening).

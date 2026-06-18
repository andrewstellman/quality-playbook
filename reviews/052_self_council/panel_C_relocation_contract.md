# Panel C — relocation + install-contract preservation + Phase-E + defensive sweep — VERDICT: SHIP

Range reviewed: `20c7976..a3a5ca2` (Phase D + E focus). Independent adversarial review.

- **OK** layout: root SKILL.md is a real file (81,641 bytes); in-tree plugins/.../{SKILL.md,references} are relative symlinks resolving to root (not dangling). `test_skill_resolution_order.py` UNCHANGED in the range — no canonical runtime fallback list reordered.
- **OK** source-side `_resolve_bundle_source_root` reorder (nested-209 → nested-208 → bare source_root) correct for all three cases (clone root → nested skill folder; skill folder → itself; pre-208/adopter → itself); traced directly.
- **OK** build ships REAL files: stage() → real SKILL.md, content == root, 28 real references, no symlinks. `_assert_staged_files_are_real` exists, wired into stage(), and BITES when a symlink is planted (verified).
- **OK** gate path-pins (C1): SCRIPT_DIR/../SKILL.md resolves through the symlink to root. Skill/Hybrid (C2): `_phase4_project_type_from_artifact_shape` returns None (defer to role map) for QPB root post-relocation — correct (QPB genuinely is a skill at root now); returns "Code" only for code-shaped repos.
- **OK** install E2E from relocated layout delivers a real SKILL.md + 28 references to the runtime install location.
- **OK** Phase-E mechanical confirmation is an acceptable ship-gate posture for a pure relocation/packaging release (every behavioral surface deterministically covered); live `--claude` recall regression documented operator scope.
- **OK** defensive sweep: all root-SKILL.md-presence keys (classify_project.py, quality_gate.py:_phase4) now see QPB's root SKILL.md — correct new behavior. Adopter-side resolvers (benchmark_lib, _purpose, run_state_lib) unaffected.
- **NIT** the 3 baseline README failures (missing "Step 4" subsection + stale LAUNCH_PROMPT_LINES) predate the range (README last changed v1.5.9; the 3 failing test files untouched here; reproduced identically against base 377896f). Out of scope for v1.5.10; recommend an operator-scope README re-pin — not a ship blocker.

VERDICT: SHIP

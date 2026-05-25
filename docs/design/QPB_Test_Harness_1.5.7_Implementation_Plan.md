# QPB Test Harness (v1.5.7) — Implementation Plan

*Status: PLAN FOR REVIEW (no code yet). Owner: Andrew Stellman. 2026-05-25.*

*Companion to `QPB_Test_Harness_1.5.7_Design.md` (the WHAT — architecture, schema, the locked §F contract) and `QPB_v1.5.7_Release_Acceptance_Checklist.md` (the acceptance cases this harness automates). This doc is the HOW — location/lane decisions, the build sequence, tests, and review checkpoints the worker follows.*

---

## 1. Location, lane, and packaging (decided 2026-05-25 — supersedes the design doc's folder layout)

**Owner decision:** the harness **Python scripts live in `bin/`** alongside the other QPB scripts. The **JSON case files, config, `SCHEMA.md`, and run receipts live in `repos/security-test-cases/`** (the security chat maintains the `security_eval` JSON there; acceptance JSON is authored per the §F contract).

This supersedes the design doc's `repos/security-test-cases/harness/` layout. **Reconciliation action:** the design doc's "Folder layout" section must be updated to match (scripts in `bin/`, JSON/receipts in `repos/security-test-cases/`) so the two docs don't contradict.

Concrete packaging (proposed — confirm in review):
- **`bin/harness/`** — a subpackage holding the modules (`schema.py`, `prepare.py`, `runner.py`, `facts.py`, `grade_security.py`, `grade_acceptance.py`, `scheduler.py`, `manager.py`, `tui.py`). A subpackage (vs ~9 flat `bin/qpb_harness_*.py` files) keeps them grouped and makes import-isolation trivial to assert.
- **`bin/qpb_harness.py`** — the user-facing entry (queue/launch/TUI), self-describing on no-args per the 089x discoverability convention.
- **`bin/tests/`** — harness tests (see §4 on segregation).
- **`repos/security-test-cases/`** — `cases.json`, `config.json`, `SCHEMA.md`, `runs/`, `mirrors/`, `control/`.

**Lane consequence (load-bearing):** `bin/` is protected QPB source. Therefore the harness is built by the **worker (Claude Code)** and code-reviewed by **both chats** — Cowork does NOT apply it directly. The plan + design + SCHEMA.md (all in `docs/design/` or `repos/`) are Cowork-editable; the `bin/` code is not.

**Bundle safety (non-negotiable, per design §J + the 090c import-discipline audit):**
- The harness modules MUST be excluded from `bin/install_skill.py::_bundle_files()` — they must never enter an adopter's install closure.
- The bundled closure MUST NOT import `bin.harness` (import-isolation). The subpackage boundary makes this easy to assert. **`_bundle_files()` is an enumerated allowlist (install_skill.py ~181–194), not a `bin/*` glob — verified — so `bin/harness/` is excluded by default.**
- A test asserts BOTH: harness modules absent from the closure manifest, AND **importing the bundled closure — `bin/__init__.py` in particular (it is bundled and runs on every `import bin.*`) — does NOT transitively load `bin.harness`.** The transitive-import-via-`__init__` path is the real leak vector the allowlist alone doesn't catch. Extends `test_publish_safety_090c.py` (the existing import-discipline/publish-safety audit). **These two safety tests run in the release gate** (see §4) — their whole job is to catch a harness change leaking into the shipped skill.

## 2. Branch strategy (DECIDED 2026-05-25)

Build **directly on `1.5.7`**. Rationale: harness bugs and 1.5.7 bugs may surface together, and working on one branch keeps both in the same place. This is **safe because of §4's segregated harness tests** (decision #3): a half-built harness with red tests never gates the skill release suite or the four-ref dance, so the two bug-streams coexist on `1.5.7` without the harness destabilizing the release. The harness ships with the release as intended (no merge step).

## 3. Build phases (each = a worker deliverable + a code-review checkpoint)

Follows design build-order M, fleshed into buildable units. Each phase: deliverables → required tests → done-criteria → **review checkpoint (both chats) before the next phase**.

**Phase 1 — Substrate (claude runner, one case end-to-end).**
- Deliverables: `schema.py` (dataclasses/enums + the §F vocabulary + `expected`-entry shape), `prepare.py` (acceptance prep: worktree → docs → Phase-0 install; security prep: worktree → scrub → leakage-gate → install), `runner.py` (claude adapter: detached `start_new_session` subprocess, stream capture, max-duration timeout), `facts.py` (the two-sourced extractor from design §C — **re-run the RUN'S OWN INSTALLED `quality_gate.py`** (the channel-installed gate at the version under test — NOT the dev clone's gate) over final `quality/` with the vendor env var set, for gate-derived facts; transcript parse for live-behavior facts), receipt-dir writer. *(Using the clone's gate would mis-grade a `pip-registry@1.5.6` comparison run with 1.5.7's verdict logic, and could diverge from the verdict the run actually produced — design §C / SCHEMA.md must pin "installed gate.")*
- Tests: schema (de)serialization; prep policies incl. the leakage-gate abort; the two-sourced extractor (gate-facts from a re-run fixture, live-facts from a transcript fixture); timeout kill.
- Done: a single acceptance case runs end-to-end on a `clone` install and produces a correct `facts.json`.

**Phase 2 — Acceptance + security graders (the §F contract in code).**
- Deliverables: `grade_acceptance.py` (evaluates `expected` assertions against facts, incl. the three-state `gate_result`, the `verdict_state` ⊥ `gate_result` independence, and the `no_false_pass`/`no_false_fail` internal-consistency checks), `grade_security.py` (answer-key match → DETECTED/PARTIAL/MISSED/BLOCKED, BLOCKED⇒N/A). Author the first **1.5.7 acceptance case set** (from the checklist Tier 0–3) on **local-artifact installs** (`pip-local-wheel`/`npm-local-tgz`).
- Tests: per-assertion grading; **mutation-bites** (a mis-attribution or a false PASS must fail a test); BLOCKED⇒N/A; the independence and internal-consistency cases.
- Done: the harness grades a real local-artifact acceptance run correctly (this is the minimum that automates the 1.5.7 gate — see §5).

**Phase 3 — Parallel scheduler.**
- Deliverables: `scheduler.py` — per-vendor caps (default 1), global cap, per-vendor cooldown; picks the next queued run whose vendor has capacity.
- Tests: cap logic, cooldown, global cap, vendor-capacity selection.
- Done: N independent runs across vendors execute concurrently; same-vendor runs respect the cap.

**Phase 4 — Manager daemon + Textual TUI.**
- Deliverables: `manager.py` (owns queue/exec, writes `control/manager.pid`+heartbeat, consumes `control/commands.jsonl`, crash recovery: RUNNING+dead-PID+no-terminal → FAILED-orphaned), `tui.py` (read-mostly Textual client; list/drill-in/commands; never spawns runs), `bin/qpb_harness.py` entry.
- Tests: manager queue/recovery; **TUI screen-content tests** — render a specific state (e.g. 3 in-flight across vendors + a completed graded run) and assert the rendered output contains the right elements (run rows, in-flight markers, verdict/grade, provenance).
- Done: open/close the TUI without disturbing in-flight runs; the manager survives a restart.

**Phase 5 — Broaden runner adapters + Mode B.**
- Deliverables: codex / copilot / cursor adapters reusing `bin/run_playbook.py` patterns (flags 390–393, `command_for_runner` 1479, `--model` 504, `copilot_resolver` 1517); Mode B via reuse of `run_playbook.py`; per-adapter live-fact parsers normalized into the §C shape.
- Tests: per-adapter normalized-fact extraction; Mode A vs Mode B launch.
- Done: each CLI runs at least one case in both modes and produces correct facts.

**Phase 6 — Registry / version-pinned channels (post-publish).**
- Deliverables: `pip-registry@<ver>` / `npm-registry@<ver>` install paths; version-comparison run support.
- Tests: install-command templating per channel+version.
- Done: a post-publish smoke run installs from the registry at a pinned version.

*(The `security_eval` path rides the same engine from Phase 1; its grader lands in Phase 2 alongside the acceptance grader. The security chat's cases drive it.)*

## 4. Testing & CI integration

- Harness **functionality** tests live in `bin/tests/` but are **segregated** from the shipped-skill release gate (e.g. a `bin/tests/harness/` subdir or a naming marker) so a harness functionality bug never blocks shipping the skill. They are still run in CI and dual-env where the run touches env-detection.
- **EXCEPTION — the two bundle-safety tests (closure-exclusion + `bin/__init__` import-isolation, §1) stay IN the release gate**, NOT segregated. Their job is to catch a harness change leaking into the shipped adopter closure, so they must run alongside the skill release suite. Only harness *functionality* tests are segregated.
- Mutation-bites required on both graders. TUI screen-content tests required (Phase 4).

## 5. Mapping to the 1.5.7 acceptance gate

The minimum to **automate** the Tier 0–3 acceptance gate is **Phases 1–2** (substrate + acceptance grader + claude Mode A + local-artifact installs). Phases 3–6 (scheduler, TUI, other CLIs, registry) are quality-of-life and post-publish, NOT release blockers. So: the harness does not block publish beyond Phases 1–2 — and if those aren't ready in time, the manual checklist still gates the release (the harness automates it, it isn't a prerequisite).

## 6. Code-review protocol

- **Per-phase, both chats review** against the design + this plan + SCHEMA.md before the next phase starts (not one giant review at the end).
- Each review confirms: matches the design/§F contract; the **bundle-exclusion + import-isolation tests pass**; tests (incl. mutation-bites / TUI screen tests for the relevant phase) are present and green dual-env.
- **Council-of-Three is reserved** for any change that touches the *bundled* closure or skill behavior — which the harness must not. If a phase ever needs to modify a bundled `bin/` file or `_bundle_files()` itself, that part goes through the standard protected-source Council lane separately.

## 7. Resolved decisions (2026-05-25)

1. **`bin/harness/` subpackage** (modules grouped; import-isolation trivial to assert) + `bin/qpb_harness.py` entry.
2. **Build directly on `1.5.7`** (not a feature branch) — see §2; safe via segregated tests (#3).
3. **Harness tests segregated** from the skill release suite (own discover path / `bin/tests/harness/`); CI'd, dual-env where env-detection matters, but they do NOT gate the skill release.
4. **`stream.ndjson` always retained per run, externalized from git** — every run keeps its full raw stream as an auditable log (we don't know in advance which run matters), stored in the gitignored `runs/` tree (never selectively dropped, never committed). The small structured receipts (`invocation.json`, `facts.json`, `grading.json`, `summary.md`, the rebuildable index) ARE committed as the in-repo evidence. So: complete auditable raw log on disk, lean git history.
5. **One worker command** points the worker at the design + this plan + `SCHEMA.md` to self-sequence build-order M, **halting at each per-phase review checkpoint** (§6) before proceeding.

## 8. Definition of done (whole harness)

All phases green; bundle-exclusion + import-isolation tests pass; the 1.5.7 acceptance case set runs and grades correctly end-to-end on local-artifact installs; security cases run on the same engine; `SCHEMA.md` authoritative and summarized in `TOOLKIT.md` + `DEVELOPMENT_CONTEXT.md`; built on `1.5.7` (and carried onward to `main` in the four-ref dance) so it ships with the release.

---

**Reconciliation note for the design doc:** update its "Folder layout" + §I/§J to reflect scripts-in-`bin/` (subpackage), JSON/receipts-in-`repos/security-test-cases/`, and the bundle-exclusion + import-isolation tests as hard requirements. Everything else in the design (the §F contract, the two-sourced facts, the run matrix, the scheduler, the lifecycle) is unchanged by the location move.

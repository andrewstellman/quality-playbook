# Quality Playbook v1.5.10 — Design Document

*Status: created 2026-06-11 as the SKILL.md-trim workstream; **scope expanded 2026-06-18** (operator decision) to a full **repo-hygiene release**: SKILL.md trim + SKILL.md relocation to repo root + folder-structure cleanup + an arunner regression run that confirms the trimmed/relocated skill still works end-to-end. The intent is to hand v1.5.11 (the security release) a clean, sensibly-organized starting point.*

*The broader-scope backlog that previously held the v1.5.10 number is `QPB_v1.5.11_Design.md`. Work begins off the `1.5.9` branch HEAD on a new `1.5.10` branch.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule. The design + implementation-plan docs in `docs/design/` are planning content authored by Cowork; the **source mutations they describe are executed by the Claude Code worker**, not by Cowork directly.*

---

## Where v1.5.10 sits in the arc

Three coordinated workstreams, all in service of one goal — **a clean repo before the security work**:

1. **SKILL.md trim** — move per-phase detail from the 1,266-line source `SKILL.md` into `references/*.md` files loaded on-demand per phase. Target: source SKILL.md ~12K BPE tokens (from ~31K).
2. **SKILL.md relocation to repo root** — the canonical SKILL.md currently lives buried at `plugins/quality-playbook/skills/quality-playbook/SKILL.md`. Operator decision (2026-06-18): moving it out of the root was a mistake. Move the **real file** back to the repo root as the single source of truth; **symlink** the in-tree skill locations back to it; rewire the install-location fallback contract, packaging, and tests accordingly.
3. **Folder-structure cleanup** — the repo accumulated committed run-output and orphaned partial copies with little organizing logic. Remove the cruft from tracking (reversibly), gitignore it, and leave a structure with clear rhyme and reason.

Closed out by an **arunner × QPB integration + regression test** that exercises the trimmed + relocated skill on the standard benchmark set, confirming no behavioral break.

*Terminology note (2026-06-19): the end-to-end check is a **regression test** (does the refactor break bug-finding?) and an **integration test** (does arunner correctly drive QPB's phases?) — not a "recall run." Earlier drafts called it a "recall run/baseline," a misapplied science/public-health term; the correct quality-engineering names are regression test and integration test. "Bug recall" remains valid only as the metric it names (bugs found ÷ known bugs). Separately, **`run_playbook` is being retired** — the integration+regression test runs arunner-native (FR-61–65), and we do not use `run_playbook` going forward.*

**Why this matters:**

1. **awesome-copilot submission.** A small canonical SKILL.md can ship verbatim instead of the redirect-to-install framing the maintainers reject.
2. **Per-invocation token cost.** SKILL.md loads into context on every invocation; ~31K tokens × every run × every adopter is real cost. Lazy-loading phase content cuts the baseline.
3. **Maintainability + a clean base for v1.5.11.** A 1,266-line SKILL.md buried four directories deep, alongside committed run outputs and orphaned copies, is hard to navigate and reason about. The security work in v1.5.11 deserves a tidy starting point.

---

## Operator decisions (2026-06-18)

Two forks were surfaced from the repo audit and resolved by the operator:

- **SKILL.md move → "Canonical file at root + rewire."** Move the real SKILL.md to the repo root as source of truth; symlink the in-tree skill locations to it; update the install-location fallback list, the pyproject bundle patterns, and the affected tests. This is the highest-fidelity option to the operator's intent and the **biggest-blast-radius** item in the release — the arunner regression run is therefore load-bearing, not optional.
- **Cruft removal → "git-rm + gitignore (reversible)."** Remove stale run outputs and orphaned copies from tracking and add gitignore rules; git history preserves everything, so the change is fully reversible. **No history rewrite.** Every removal is preceded by a reference-check confirming nothing live depends on the path.

---

## Scope additions (2026-06-18, second pass)

After the trim/relocation/cleanup landed and pushed, the operator added two QPB workstreams that fit the "refactoring + maintenance" character of the release, plus related arunner work tracked separately.

### Workstream 4 — README simplification (orientation doc; Cowork may edit directly)

- **Remove the Validation section** — we are not currently validating against the QPB benchmark; revisit later (out of scope for 1.5.10, no need to discuss the replacement now).
- **Replace "Setting up automation scripts"** with an arunner-based section (we're replacing run-serial automation with arunner), or remove it.
- **Update the repository-structure diagram** to the post-relocation/cleanup layout (SKILL.md + references/ at root; cruft removed).
- **Move the Example Output section further up.**
- **Move the Table of Contents up** — above "How to install Quality Playbook" (the playbook is shorter now, so the TOC belongs higher).
- **Add a Quick Start section above the TOC** — "Install and run" in a very short block: the recommended way to run it, showing one of the three install paths (npm / pip / clone) + the actual prompt you give inside your repo after loading the skill into an agent runner like Claude Code.
- **Real token usage in Quick Start** — show actual input/output token counts from real benchmark runs (smallest repo, or "running against these three open-source repos cost these token counts"). **Source: the arunner × QPB integration+regression test's token reporting** (FR-65; see token-reporting dependency below) — NOT fabricated.

### Workstream 5 — CI/CD publish on tag (QPB source/infra; worker lane + Council)

- Add `.github/workflows/publish.yml` so a `vX.Y.Z` tag push auto-publishes to **PyPI + npm** via **OIDC trusted publishing** (no stored tokens/OTP). Draft exists (operator-supplied, from a claude.ai design session) — improve it, then **Council-review it** (operator requirement).
- Three `# CONFIRM:` items to verify against `bin/build_channel_package.py`: (1) exact stage invocation + staged output paths (`dist/npm/package.json`, `dist/pip/pyproject.toml`); (2) whether the build script already emits sdist+wheel (drop the `python -m build` step if so); (3) optionally extend the version-equality check beyond `package.json`+`pyproject.toml` to `plugin.json` + SKILL.md for internal consistency.
- Marketplace channel needs no publish job (in-tree `marketplace.json`). Only pip + npm.
- One-time external setup: register the trusted publisher (owner `andrewstellman`, repo `quality-playbook`, workflow `publish.yml`, environment `release`) in pypi.org + npmjs.com before the first tagged run — names must match exactly. (Operator step.)
- This workstream is what makes the eventual v1.5.10 tag actually publish; sequence it before the release tag.

### Workstream 6 — Clojure quality-gate fix (skill source; worker lane + Council)

A real adopter-reported bug, diagnosed 2026-06-18 (`AI-Driven Development/Quality Playbook/QPB_Clojure_Gate_Diagnosis.md`): `quality_gate.py` is **Clojure-blind**. `detect_project_language()` (`quality_gate.py:2712`) uses ordered **first-match** over a `language_order` list that lacks `.clj/.cljc/.cljs`, so a Clojure repo's stray `.py` build/lint scripts win → the project is detected as Python → the correct `test_functional.clj` fails the extension check. Missing on all three surfaces: `language_order`, `lang_to_valid` (:3816), `count_source_files` (:2759).

**This is a recurring class, not a one-off.** A comment at `:2692` records the identical failure on a **Java** project (2026-05-16); that fix only excluded QPB's own install dirs, leaving the root fragility. So the fix is the principled one, not whack-a-mole:

- **Switch `detect_project_language` from first-match-by-order to dominant-language-by-count** (pick the extension with the most files). This kills the "stray `.py` wins" class for Java, Clojure, and any future language.
- Add Clojure to all three tables: `language_order`, `lang_to_valid` (`"clj": "clj cljc cljs"`), `count_source_files` exts.
- Secondary: add a Clojure section to `references/phase2_generation_guide.md` (clojure.test/lein/kaocha structure, a skip-guard row — `(is false "BUG-NNN ...")` since clojure.test has no native xfail, JUnit-XML via `kaocha --plugin junit-xml`/`eftest`); teach `_body_has_real_assertion` / the 090s no-op detector (`:~3974`) to recognize `(deftest …)`/`(is …)`.

**Highest risk:** changing first-match→dominant-count alters detection for EVERY project, so the Council + tests must confirm the existing benchmark repos (Go `chi`, Rust `virtio`, JS `express`, and a Java case) still detect correctly. Tests use file-tree fixtures (a Clojure tree + a stray `.py`) under `bin/tests/fixtures/` — **no Clojure runtime needed** for the unit tests. (Running red-green Phases 3–6 on the actual Clojure project is a separate operator task needing the Clojure toolchain installed locally; the gate fix itself does not.)

### Related work — tracked separately (arunner repo + cross-version benchmark)

These are part of the same effort but live outside the QPB 1.5.10 source release:

- **arunner generic phase-orchestration FRs (FR-61–65)** (arunner `docs/REQUIREMENTS.md`): prompt-from-file (with light `{var}` templating — QPB prompts use `skill_fallback_guide` substitution), multi-step entries, deterministic continuation gates (default), reasoning gates (optional, fenced, separate judging context, kept OUT of the measurement path), a gate-outcome vocabulary richer than continue/halt (`skip-to-next` for QPB's Phase-3-skip; `behavior-flag` for behavior changes), and token reporting. **Status: implemented 2026-06-19** on the arunner `fr-61-65-impl` branch (instruction 002, local; 378 tests, stdlib-only, 3-panel Council SHIP). Spec on `fr-61-65-spec` (001). Both await operator review/merge to arunner `main`.
- **arunner token reporting (FR-65)**: arunner reports input+output tokens per step/sub-run/run (`run_playbook` does not emit tokens). This is the source of the README Quick-Start token numbers — another reason the integration+regression test runs arunner-native, not via the retired `run_playbook`.
- **`run_playbook` retirement.** `run_playbook` is being retired. The standing end-to-end check becomes the arunner × QPB integration+regression test (FR-61–65 phases-as-steps), graded mechanically by the regression-test scorer (`bin/regression_replay.py`) against pinned ground truth. The earlier "run a `run_playbook` baseline now" step (instr 053) is dropped — we do not use `run_playbook` going forward; the baseline for comparison is the existing pinned ground truth.

**Dependency notes:** the README Quick-Start token line is BLOCKED on the arunner × QPB integration+regression test (it provides the FR-65 token numbers). The CI/CD workstream is BLOCKED on Council review (done) and then on publish.yml reaching `origin/main` before trusted-publishing can be exercised. The integration+regression test needs a follow-up worker instruction that builds the QPB-native plan (phases as steps, `phase_prompts/`, gates = `validate_phase_artifacts`); FR-61–65 themselves are landed. The README structural edits (validation/automation/diagram/TOC/example/quick-start-shell) are NOT blocked and have landed.

---

## Repo audit findings (2026-06-18)

Measured against the live `1.5.9` working tree.

### Genuine cruft — committed by accident (remove from tracking, gitignore)

| Path | Tracked files | What it is | Action |
|---|---|---|---|
| `quality/` (esp. `quality/previous_runs/`) | 989 (904 in previous_runs) | QPB's own self-run **output** dir + archived run history; last touched 2026-05-30 "Bootstrap run". Live output should never be committed. | `git rm -r --cached`; gitignore `quality/` (keep any genuine fixtures it may hold — verify first) |
| `previous_runs/` (top-level) | 4 | Stale `BUGS_pre_v1.5.3.md` snapshots | `git rm --cached`; gitignore or move to an `archive/` |
| `spike/v1.5.9_phase_1A/` | 5 | v1.5.9 phase-1A spike evidence | move to `docs/` archive or `git rm --cached` + gitignore |
| `.github/skills/quality_gate/` | 44 | **Orphaned partial copy**: `__init__.py` + one `tests/test_quality_gate.py` + a large `tests/fixtures/challenge_coverage/` tree, with **no actual `quality_gate.py`** (the real module is `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`). No CI runs it (`.github/workflows/` is empty). | `git rm -r --cached` **after** the build-staging safety check below |

**Safety check before removing `.github/skills/quality_gate/`:** `pyproject.toml` `[tool.setuptools.package-data]` explicitly lists `_bundle/.github/skills/quality_gate/**/*`. That references the *staged* `_bundle/` tree, not the repo-root dir — but the worker MUST read `bin/build_channel_package.py` and confirm the staging step does not copy the repo-root `.github/skills/quality_gate/` into `_bundle/`. If it does, the dir is a build input, not cruft — reclassify and stop. (`.github/workflows/` being empty already establishes CI doesn't run its tests.)

### Intentional — leave alone

- `pytest/` (top-level) — a deliberate **stdlib unittest shim** so `python -m pytest` works under the stdlib-only rule (NFR-3). Not cruft.
- `repos/` (453) — benchmark material (secbench, qpb-ff, skill copies). Cowork's free-write subtree.
- `build/`, `dist/`, `quality_playbook.egg-info/`, `__pycache__/`, `docs_gathered/`, `harness_runs/`, `informal_docs/`, `pattern-discovery/`, `testing/` — already gitignored.
- `bin/`, `docs/`, `plugins/`, `harness_plans/`, `reviews/`, `metrics/`, `ai_context/`, `images/`, `reference_docs/`, `scripts/`, `quality_playbook_cli/` — legitimate source/project dirs.

---

## Design — the SKILL.md trim (workstream 1)

Current source SKILL.md: **31,038 BPE tokens / 1,266 lines** (measured). Target ~12K. The `references/` scaffolding already exists (24 files), and Phases 1–2 are already trimmed to ~5-line pointers — the lazy-load pattern is proven in production, which retires the "will the agent actually `Read` at the phase boundary?" open question.

**Stays in the trimmed canonical SKILL.md:** frontmatter; Phase Overview; phase entry contracts (tabular); invocation forms (Mode A / Mode B / harness — keep the mode-select, move the detail); the `Read references/...` load directives; non-phase-specific contract content (run_state schema pointer, install-location fallback list, version-stamp invariants); the v1.5.9 Heartbeat emission section.

**Moves to `references/` (token budget — eight sections carry ~19K):**

| Section | Tokens | Action |
|---|---|---|
| How to run — invocation contract | 6,506 | keep mode-select (~1.5K), move detail to `references/invocation_guide.md` |
| Phase 5: Reconciliation | 5,159 | move → new `references/phase5_reconciliation_guide.md` |
| How to Use | 3,040 | move detail, keep invocation |
| What This Skill Produces | 2,800 | move artifact catalog to references |
| Run-state instrumentation | 2,431 | **consolidate** into existing `references/run_state_schema.md` |
| Phase 7: Interactive | 2,375 | move → new `references/phase7_guide.md` |
| Phase 4: Spec Audit | 1,749 | **consolidate** into existing `references/spec_audit.md` |
| Recheck Mode (+results) | ~1,300 | move → new `references/recheck_mode.md` |

~22K of available savings against a 19K target — clears comfortably to ~9–12K.

**The one real gotcha:** the "consolidate" rows are *reconcile-then-point*, not append. Only 3 `Read references/` directives are wired in today, so the existing reference files (`spec_audit.md`, `run_state_schema.md`, `phase6_verify_guide.md`) may have **drifted** from the inline SKILL.md text. The worker must diff the inline section against the existing reference and reconcile, not blindly append.

**Loading model.** Trimmed SKILL.md loads at session start; each `references/phase_N_*.md` loads when the agent enters Phase N (same on-demand model the existing references use).

**Backward compatibility.** Adopters running pre-v1.5.10 installs keep working; the trim is a source-side change.

---

## Design — SKILL.md relocation to root (workstream 2)

**Target layout:** the real `SKILL.md` (and its `references/`) live at the repo root. The in-tree skill location(s) become **symlinks** back to the root file. The canonical skill source-of-truth becomes the root, matching the operator's mental model and making the file editable without descending four directories.

**The rewire surface (the load-bearing part).** The "install-location fallback list" — the ordered set of ~10 canonical layouts the skill walks to locate `SKILL.md`/`quality_gate.py` at runtime — is referenced across these source + test files (pinned by audit):

- Source: `bin/run_playbook.py`, `plugins/quality-playbook/skills/quality-playbook/scripts/install_skill.py`, `.../scripts/benchmark_lib.py`, `.../scripts/qpb_validate.py`
- Tests: `bin/tests/test_skill_resolution_order.py`, `test_phase_prompts_externalized.py`, `test_benchmark_lib.py`, `test_run_playbook.py`, `test_doc_drift.py`

Plus:

- `pyproject.toml` `[tool.setuptools.package-data]` bundle globs (`_bundle/**/*`, `_bundle/.github/skills/**/*`).
- `bin/build_channel_package.py` staging logic (what it copies into `_bundle/`).
- `bin/tests/test_skill_md_size.py` — currently pins `_SKILL_DIR = parents[2] / "plugins" / "quality-playbook" / "skills" / "quality-playbook"`; must repoint to the root.

**Design constraints for the move:**

1. The relocation must **preserve the install-location fallback contract** for *adopters* — an installed skill at `.claude/skills/quality-playbook/SKILL.md` (etc.) must still resolve. The change is to where QPB's *own* canonical source lives, plus adding root as a recognized layout; it must not break the adopter-side fallback order.
2. Symlinks vs. real-file: the **root copy is the real file**; in-tree locations are symlinks. The build/staging step (`build_channel_package.py`) must dereference symlinks when staging `_bundle/` so the published package ships real files, not dangling links.
3. The SKILL.md-size test repoints to root and keeps the ratchet (see workstream 1).

**Open question for the worker (resolve during implementation, flag if it forces a redesign):** whether any layout in the fallback list assumes SKILL.md is *not* at the repo root (e.g., a check that distinguishes "running inside the QPB repo" from "installed in an adopter project" by SKILL.md's absence at root). If so, adding root as a layout could change repo-vs-adopter detection — the worker must check `run_playbook.py`'s bundle_dir resolution (around the documented `.github/skills/SKILL.md → bundle_dir.name == "skills"` logic) before moving.

---

## Design — folder cleanup (workstream 3)

Execute the audit table above:

1. **Verify-then-remove.** For each cruft path, the worker first greps the live source tree (excluding `repos/`) to confirm nothing imports/reads it, then `git rm -r --cached` and adds a `.gitignore` entry. The `.github/skills/quality_gate/` removal additionally requires the `build_channel_package.py` staging check.
2. **No history rewrite.** Removals are from the index + working-tree-going-forward only; history retains the files.
3. **Result:** a top-level structure where every tracked dir is either source, docs, benchmark material (`repos/`), or a deliberate shim (`pytest/`) — no committed run outputs, no orphaned partial copies.

---

## arunner × QPB integration + regression test (the ship gate's load-bearing check)

Because the relocation touches the install-location contract, a green test suite is necessary but **not sufficient**. The release runs the standard benchmark **arunner-native** (FR-61–65: each QPB phase a step, prompts from `phase_prompts/`, deterministic `validate_phase_artifacts` gates between steps) against the trimmed + relocated skill. **`run_playbook` is not used** — it is being retired. The run is launched through the Claude Code worker (the sandbox can't authenticate `--claude` model calls):

- Exercise Phases 1–3 (minimum) on the standard benchmark repos (chi / virtio / express), installed fresh via `setup_repos.sh` so the skill under test is exactly v1.5.10.
- Confirm the skill **resolves SKILL.md from the new root layout at runtime**, loads each `references/phase_N_*.md` at its phase boundary, and produces artifacts of the same shape/quality as the pre-trim baseline.
- Grade mechanically: the regression-test scorer (`bin/regression_replay.py`) scores bug-detection (recall = bugs found ÷ known bugs) against the pinned ground truth; also compare REQUIREMENTS quality + Phase 6 verdict accuracy. The verdict is computed, not judged.
- If the score drops materially or a reference fails to load, identify the offending extraction and either move it back to SKILL.md or strengthen the load directive.

---

## Ship criteria

- Trimmed SKILL.md passes the new reference-resolves validator + the ratcheted token-ceiling test (repointed to root).
- Full `bin/tests/` suite green (including the rewired install-location/resolution-order tests).
- The package builds (`build_channel_package.py` + `python -m build`) with the relocated layout, staging real files (symlinks dereferenced).
- arunner × QPB integration+regression test shows no material bug-detection degradation (mechanically scored) and confirms runtime resolution from the root layout.
- Folder cleanup complete; `git status` clean; no committed run outputs remain.
- Council Self-Review Protocol 1 (panelists: audit-table/cleanup completeness, mechanical-extraction + reconciliation correctness, relocation/contract-preservation correctness) + the defensive-sweep charter per `DEVELOPMENT_PROCESS.md`.
- **awesome-copilot re-submission test:** regenerate the packet shipping the now-trimmed canonical SKILL.md directly; submit PR; iterate if rejected.
- Release prep: version stamps, CHANGELOG, README/TOOLKIT updates, tag + close-out per `DEVELOPMENT_PROCESS.md`. **Push/tag verification per the workspace rule** (`git ls-remote origin <ref>`) before claiming shipped.

---

## Risks

| Risk | Mitigation |
|---|---|
| Relocation breaks the install-location fallback contract (adopter-side resolution) | arunner regression run is the gate; rewired resolution-order tests must stay green; worker verifies repo-vs-adopter detection logic before moving |
| Build ships dangling symlinks instead of real files | `build_channel_package.py` must dereference symlinks when staging `_bundle/`; verify the built artifact contains real SKILL.md |
| SKILL.md trim degrades recall | benchmark regression run before ship; abort/iterate if recall drops |
| Existing reference files drifted from inline text | "consolidate" rows are reconcile-then-point (diff first), not blind append |
| `.github/skills/quality_gate/` is actually a build input, not cruft | mandatory `build_channel_package.py` staging check before removal |
| Cowork accidentally edits source directly | all source mutations go through the Claude Code worker; Cowork authors planning docs + brief only |

---

*End of v1.5.10 Design. Implementation plan in `QPB_v1.5.10_Implementation_Plan.md`. Predecessor (harness + standalone distribution) in `QPB_v1.5.9_Design.md`. Successor (security) in `QPB_v1.5.11_Design.md` — which inherits the clean repo this release produces.*

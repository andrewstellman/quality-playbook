# Exploration Findings

Bootstrap self-audit of the Quality Playbook (QPB) repository at v1.4.5. The artifact under audit is the skill itself: `SKILL.md` (2342 lines, specification-primary) plus the twelve reference files in `.github/skills/references/`, plus three Python modules that wrap the skill into a benchmarkable runner (`bin/run_playbook.py`, `bin/benchmark_lib.py`, `.github/skills/quality_gate/quality_gate.py`). This is a **clean benchmark run** (Phase 0 / 0b skipped) — findings below are derived from the code and the docs_gathered/ material only.

## Domain and Stack

- **Project:** Quality Playbook (QPB) — an AI skill that generates a full quality engineering system for any codebase, plus the Python harness that runs it as a cross-model benchmark.
- **Primary product:** `SKILL.md` (specification-primary). The skill is the thing users install; the Python harness is supporting tooling for the maintainer's own benchmarking workflow.
- **Secondary product:** a post-run validation gate (`quality_gate.py`) that mechanically checks conformance of artifacts a run produced.
- **Language:** Python 3.8+, standard library only (confirmed in the `pytest/` shim and `benchmark_lib.py` import list). No third-party runtime dependencies.
- **Consumer agents:** Claude Code, GitHub Copilot CLI (`gh copilot`), Cursor, Windsurf, Cowork — all named explicitly in `agents/quality-playbook.agent.md` and `docs_gathered/03_DEVELOPMENT_CONTEXT.md`.
- **Build/test:** stdlib-only unittest via a shim at `pytest/__main__.py` so `python3 -m pytest` runs without `pip install pytest`.
- **Deployment target:** installed per-repo as `.github/skills/SKILL.md` (Copilot flat), `.claude/skills/quality-playbook/SKILL.md` (Claude Code), or `SKILL.md` at repo root.

## Architecture

**Top-level layout** (`ls` at project root):

- `SKILL.md` — canonical specification, 2342 lines. The product.
- `AGENTS.md` — project-root AI bootstrap.
- `README.md`, `LICENSE.txt`.
- `.github/skills/SKILL.md` — installed copy (Copilot location, used by this run).
- `.github/skills/references/` — 14 reference files (patterns, protocols, pipeline, etc.).
- `.github/skills/quality_gate/quality_gate.py` — post-run validation gate (1141 lines).
- `.github/skills/quality_gate/tests/test_quality_gate.py` — gate test suite.
- `references/` — source-of-truth reference files at repo root (maintainer edits these; installs copy from here).
- `bin/run_playbook.py` — Python runner (1025 lines).
- `bin/benchmark_lib.py` — shared helpers (350 lines).
- `bin/tests/{test_run_playbook.py, test_benchmark_lib.py, test_resolve_targets.py}` — runner tests.
- `agents/{quality-playbook.agent.md, quality-playbook-claude.agent.md}` — orchestrator agent instructions.
- `docs_gathered/` — 83 gathered documents (README, AGENTS, benchmark protocol, bootstrap chat exports, prior bootstrap reviews, prior version reviews, external skill reviews, patent material). `INDEX.md` is the navigation entry point.
- `pytest/__main__.py` — 37-line shim so `python3 -m pytest` routes to stdlib unittest.
- `repos/` — benchmark target repos (not audited in Phase 1).
- `previous_runs/` — archive directory for prior runs (empty for this audit, per the `--no-seeds` contract).
- `council-reviews/`, `pattern-discovery/`, `docs/`, `images/` — documentation/asset directories.

**Key modules and entry points:**

- **Runner entry:** `bin/run_playbook.py:1023 raise SystemExit(main())`. `main()` (line 994) parses args, resolves targets, prints a header, dispatches to `execute_run()`.
- **Phase dispatch:** `run_one()` (line 708) selects between `run_one_phased()` (phase-by-phase with exit gates, line 645) and `run_one_singlepass()` (one session for all phases, line 671). `execute_strategy_list()` (line 718) iterates over an ordered list of iteration strategies with early stop on zero-gain.
- **Prompt construction:** `phase1_prompt()` through `phase6_prompt()` (lines 258–407) assemble the literal prompt each sub-session receives; `single_pass_prompt()` and `iteration_prompt()` handle the non-phased invocations.
- **Phase gate:** `check_phase_gate()` (line 445) enforces entry preconditions for phases 2–6 (Phase 1 is always permitted).
- **Archive/cleanup:** `archive_previous_run()` (line 565) moves `quality/` to `previous_runs/TIMESTAMP/quality/` and deletes `control_prompts/`. `lib.cleanup_repo()` (`benchmark_lib.py:204`) reverts tracked non-protected changes.
- **Kill path:** `kill_recorded_processes()` (line 832) reads per-parent PID files `.run_pids.<pid>`; `_pkill_fallback()` (line 808) is the crash-recovery best effort.
- **Shared helpers:** `benchmark_lib.py` exposes version reading (`_read_version`, `skill_version`, `detect_skill_version`, `detect_repo_skill_version`), skill installation search (`find_installed_skill`), test-file search (`find_functional_test`, `find_regression_test`), summary building, and the protected-prefix cleanup logic.
- **Quality gate:** `.github/skills/quality_gate/quality_gate.py` runs 45 numbered benchmarks (see `references/verification.md`) on a post-run `quality/` directory. `check_repo()` (line 1027) orchestrates every section. `detect_skill_version()` (line 176) has its own line parser.

**Data flow (benchmark run):**

1. `bin/run_playbook.py <target>` → `resolve_target_dirs()` resolves paths (applying version-append fallback for bare names).
2. `display_run_header()` prints config; `execute_run()` spawns a worker subprocess per target when `--parallel` (the default).
3. Each worker invokes either `gh copilot -p <prompt> --yolo` or `claude -p <prompt> --dangerously-skip-permissions`; stdout/stderr land in `control_prompts/phase{N}.output.txt` and are appended to the per-target log.
4. The agent writes artifacts to `quality/` (EXPLORATION.md, REQUIREMENTS.md, BUGS.md, patches, sidecars, etc.).
5. `lib.cleanup_repo()` reverts any tracked edits the agent made outside the protected prefixes (`quality/`, `control_prompts/`, `previous_runs/`, `docs_gathered/`).
6. After the run, the user runs `quality_gate.py .` which mechanically scores the artifacts.

**Specification-primary note:** `SKILL.md` *is* the product. Its prose contains procedural rules, quality gates, and formatting contracts. Every Python module in this repo is scaffolding around it. If the Python disappeared tomorrow, the skill would still work (run by hand in any AI CLI); if `SKILL.md` disappeared, the Python would have nothing to execute.

## Existing Tests

Two test roots, both using stdlib `unittest`:

- `bin/tests/test_run_playbook.py` — 36 tests covering `parse_args`, `parse_strategy_list`, `check_phase_gate` (phases 2–6), `archive_previous_run`, `final_artifact_gaps`, `_is_bare_name`, `phase1_prompt`, `single_pass_prompt`, `iteration_prompt`, `print_suggested_next_command`, and the `--full-run` mutual-exclusion checks.
- `bin/tests/test_benchmark_lib.py` — tests for `skill_version`, `find_installed_skill`, `cleanup_repo` (including four tests around protected prefixes), `count_matching_lines`, `print_summary`.
- `bin/tests/test_resolve_targets.py` — 220 lines; `FakeQPBRoot` context manager monkey-patches `lib.QPB_DIR` to a synthetic path containing a hand-written SKILL.md; tests the version-append fallback extensively, including the three "no also tried" edge cases (SKILL.md missing, SKILL.md without `version:` line, path-like inputs).
- `.github/skills/quality_gate/tests/test_quality_gate.py` — ~1065 lines; covers every `check_*` function in `quality_gate.py` via per-test tempdir fixtures.

**Coverage gaps observed:**

- `resolve_target_dirs()` is exercised only via `FakeQPBRoot`; the real-world case where `SKILL.md` uses the `**Version:**` bold form (which `_read_version`'s regex handles but `skill_version` does not) is not tested.
- `check_phase_gate()` tests assert individual messages but do not assert the threshold integer (80); if the number drifted to 40, the test `test_phase2_gate_requires_exploration_file` would still pass.
- `_pkill_fallback()` is not unit-tested (it invokes `pkill` as a subprocess); a refactor changing the patterns would not be caught.
- `archive_previous_run()` is tested with `control_prompts/` present but not when `previous_runs/` already has a same-timestamp entry (the code removes and re-copies, which is tested implicitly but not under concurrent races).
- The gate's `check_mechanical` function is tested for presence but not for the "should have been created but wasn't" case — because no such check exists (see Quality Risks §10).

No integration test covers the real `gh copilot -p` or `claude -p` invocation; those happen only in live benchmarks, never in CI.

## Specifications

The primary specifications consulted for Phase 1:

- **`SKILL.md`** (lines 1–945 for Phase 1 scope) — the canonical spec. Phase 1 section spans lines 347–945 and defines:
  - Three-stage exploration (open → quality risks → patterns), lines 389–411.
  - Write-as-you-go discipline, lines 403–409.
  - Candidate Bugs consolidation step, line 411.
  - 12-point gate self-check, lines 912–929.
  - Minimum 120 lines of substantive content, line 906.
  - Exact section-title requirements for gate conformance, line 914.
- **`.github/skills/references/exploration_patterns.md`** — 283 lines, six bug-finding patterns with definitions, bug-class descriptions, five diverse examples each, how-to-apply, and EXPLORATION.md output formats.
- **`.github/skills/references/orchestrator_protocol.md`** — the orchestrator contract; specifies per-phase verification gates (e.g., "more than 80 lines" for Phase 1 — see Quality Risk §1 for the drift).
- **`.github/skills/references/iteration.md`** — four iteration strategies; shared rules for ITER file naming, merge semantics, Demoted Candidates Manifest.
- **`docs_gathered/INDEX.md`** — navigation for 83 documents: project basics (01–05), genesis chats (10–13), prior bootstrap reviews (20–28), prior version reviews (30–41), patent/IP (50–51), external skill reviews (60–82).
- **`docs_gathered/03_DEVELOPMENT_CONTEXT.md`** — names the active benchmark targets (bootstrap, chi, cobra, virtio), the three-axis improvement model, known issues (TDD-compliance gaps, rate limits, cursor workspace contamination).

**Behavioral contracts derived from the spec:**

- EXPLORATION.md section titles are exact strings; any deviation fails the gate (SKILL.md:914).
- `tdd-results.json` schema_version must be `"1.1"` (SKILL.md:134, enforced in `quality_gate.py:445`).
- `integration-results.json` schema_version must be `"1.1"`; `recheck-results.json` is `"1.0"` (SKILL.md:161 and `quality_gate.py:662,738`).
- Verdict enum: `TDD verified | red failed | green failed | confirmed open | deferred` (SKILL.md:154, `quality_gate.py:497-498`).
- Protected cleanup prefixes: `quality/`, `control_prompts/`, `previous_runs/`, `docs_gathered/` (`benchmark_lib.py:177-182`).
- Iteration cycle order: gap → unfiltered → parity → adversarial (`iteration.md:8–16`, `run_playbook.py:430-436`).
- Skill version string must match across `SKILL.md`, `PROGRESS.md`, and `tdd-results.json.skill_version` (`quality_gate.py:982–1021`).

## Open Exploration Findings

Eleven concrete findings from domain-driven investigation. Each names a file path, line range, and a specific bug hypothesis. Multi-function traces are labelled `[TRACE]`.

### F-1 — Two parsers for SKILL.md `version:` disagree on format [TRACE]

`bin/benchmark_lib.py:37` defines `VERSION_PATTERN = re.compile(r"^\s*(?:version:|\*\*Version:\*\*)\s*([0-9]+(?:\.[0-9]+)+)\b", re.IGNORECASE)` and `_read_version()` (line 74) uses it. The regex accepts both `version:` and `**Version:**` in any case. 

`skill_version()` at `benchmark_lib.py:90–116` — written to mirror the legacy bash `detect_skill_version` — uses `stripped.startswith("version:")` on line 106 with default case sensitivity. If `SKILL.md` ever uses the `**Version:**` bold form (explicitly supported by `VERSION_PATTERN`), `skill_version()` returns `None`.

Call chain where this matters: `run_playbook.py:217` — `version = lib.skill_version() if _is_bare_name(raw) else None`. A `None` return silently disables the version-append fallback. The user sees only `ERROR: 'chi' is not a directory (resolved to /cwd/chi)` with no "also tried" clue (per `run_playbook.py:234`). Meanwhile, the run header at `run_playbook.py:1017` calls `lib.detect_repo_skill_version(repo_dirs[0])` which uses `_read_version` and *does* support the bold form — so the header and the fallback disagree on what the version is.

`quality_gate.py:176-191` has its own third parser: `re.sub(r".*version:\s*", "", line, count=1)` — case-sensitive `"version:"` substring but with no numeric-format validation. If `SKILL.md` ever moves to `version: "1.4.5"` (quoted YAML), quality_gate picks up `"1.4.5"` with quotes; `_read_version`'s regex rejects the quoted form entirely (returns `""`); `skill_version()` returns `"1.4.5"` including quotes. Three tools, three different version strings for the same file.

### F-2 — EXPLORATION.md line-count gate threshold drifts across three contracts

- `SKILL.md:906` — "EXPLORATION.md must contain at least **120** lines of substantive content."
- `SKILL.md:916` — Gate self-check #1: "at least **120** lines of substantive content."
- `.github/skills/references/orchestrator_protocol.md:41` — "more than **80** lines of substantive content."
- `bin/run_playbook.py:455–457` — Phase 2 entry gate warns if `line_count < 80` (a WARN, not FAIL): `messages.append(f"GATE WARN Phase 2: EXPLORATION.md is only {line_count} lines (expected 80+)")`.

The canonical threshold is 120 (the skill's self-gate) but the runner enforces 80 and even then only as a warning. A model that writes an 85-line EXPLORATION.md passes the runner gate, possibly passes the orchestrator gate, and fails the skill's own self-gate — but because the runner proceeds anyway, Phase 2 runs on a thin exploration.

### F-3 — Fourth documented install location is missing from `SKILL_INSTALL_LOCATIONS` [TRACE]

`SKILL.md:48–55` documents four install paths: (1) `references/` relative to SKILL.md, (2) `.claude/skills/quality-playbook/references/`, (3) `.github/skills/references/`, (4) `.github/skills/quality-playbook/references/` (the "alternate Copilot installation"). The same four-path fallback appears in `quality_gate.py:969–976` (for SKILL.md detection).

`bin/benchmark_lib.py:39–43` — `SKILL_INSTALL_LOCATIONS` only has three entries: `.github/skills/SKILL.md`, `.claude/skills/quality-playbook/SKILL.md`, `SKILL.md`. `find_installed_skill()` at line 128 iterates only these three.

Trace: `run_playbook.py:237` — `if lib.find_installed_skill(candidate) is None:` emits `WARN: No SKILL.md found for {candidate}. Expected at .github/skills/SKILL.md, .claude/skills/quality-playbook/SKILL.md, or SKILL.md at the target root`. A user with an `.github/skills/quality-playbook/SKILL.md` install will see this spurious warning every run, even though the skill is installed exactly where SKILL.md's own documentation says it may live.

### F-4 — `archive_previous_run` is not atomic (copytree + rmtree with no rollback) [TRACE]

`bin/run_playbook.py:565–576`:

```python
def archive_previous_run(repo_dir: Path, timestamp: str) -> None:
    ...
    archive_dir = repo_dir / "previous_runs" / timestamp / "quality"
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    if archive_dir.exists():
        shutil.rmtree(archive_dir)
    shutil.copytree(quality_dir, archive_dir)
    shutil.rmtree(quality_dir, ignore_errors=True)
    shutil.rmtree(control_prompts_dir, ignore_errors=True)
```

If the process is SIGKILLed between `copytree` and the first `rmtree`, both `previous_runs/TIMESTAMP/quality/` and `quality/` exist. On the next run, `resolve_target_dirs()` doesn't detect this; the SKILL's Phase 0 logic (`SKILL.md:304–343`) will find the partial archive and may inject seeds from an incomplete run. This compounds with `--no-seeds`: the runner's `no_seeds=True` default (line 100) tells the agent to skip Phase 0, but if someone runs with `--with-seeds` the stale archive contaminates.

Additionally, `control_prompts/` is *deleted*, not archived — for debugging a failed run, the input prompts that produced the failure are gone.

### F-5 — Phase 3 gate doesn't require all Phase 2 artifacts

`bin/run_playbook.py:459–463` — Phase 3 gate only checks `REQUIREMENTS.md`, `QUALITY.md`, `CONTRACTS.md`, `RUN_CODE_REVIEW.md`. Phase 2 produces nine core artifacts (see `SKILL.md:94–123` and `final_artifact_gaps()` at `run_playbook.py:579-595`: `RUN_INTEGRATION_TESTS.md`, `RUN_SPEC_AUDIT.md`, `RUN_TDD_TESTS.md`, `COVERAGE_MATRIX.md`, `COMPLETENESS_REPORT.md`, plus functional tests).

If Phase 2 produces only the four gate-checked files, Phase 3 runs without the spec-audit protocol or TDD protocol. The agent will generate a code review referencing documents that don't exist. The failure surfaces only in Phase 6 (quality_gate.py line 292–297: `RUN_INTEGRATION_TESTS.md` and `RUN_SPEC_AUDIT.md` are `fail`-on-missing).

### F-6 — `docs_present()` returns True for a docs_gathered/ containing only noise [TRACE]

`bin/run_playbook.py:560–562`:

```python
def docs_present(repo_dir: Path) -> bool:
    docs_dir = repo_dir / "docs_gathered"
    return docs_dir.is_dir() and any(docs_dir.iterdir())
```

`any(docs_dir.iterdir())` is True if the directory contains *any* entry — including `.DS_Store`, an empty subdirectory, a symlink, or a zero-byte file. `run_one_phased()` / `run_one_singlepass()` then skip the "SKIP: docs_gathered/ is missing or empty" guard and proceed into a run whose Phase 1 will find no real documentation.

`SKILL.md:1–505` repeatedly stresses that documentation-enriched runs find different and higher-confidence bugs; the runner doesn't validate that there's substantive documentation, only that *something* is in the directory.

### F-7 — `check_phase_gate` for Phase 1 unconditionally returns ok [TRACE]

`bin/run_playbook.py:449–450` — `if phase == "1": return GateCheck(ok=True, messages=[])`. Unlike Phase 2–6, no precondition is enforced. This is intentional (Phase 1 has nothing to gate *on*), but `run_one_phased()` (line 651) calls `archive_previous_run` only when `"1" in phase_list`. A user running `--phase 2,3,4,5,6` against a repo with an in-progress `quality/` will have that `quality/` mixed into their new run, because the archive only happens with phase 1. The Phase 2 gate then passes because EXPLORATION.md exists from the prior run — potentially with stale section titles, stale findings, stale requirements.

### F-8 — `print_suggested_next_command` suggests iteration even after run failures [TRACE]

`bin/run_playbook.py:930–946` — `execute_run` tracks `failures` and returns 1 on any worker failure, but calls `print_suggested_next_command(args)` at line 935 *before* the return, *regardless* of failures. The suggestion walks the iteration cycle ("Next iteration suggestion: ... --next-iteration --strategy gap ...") unconditionally. A user whose Phase 1 crashed (or whose worker timed out) sees a suggestion that would iterate on a broken run.

The `suppress_suggestion=True` path (lines 734, 903, 911) only suppresses for the interior calls inside `--full-run` chaining; the outermost call in the error case is not suppressed.

### F-9 — `_pkill_fallback` patterns don't cover the `gh copilot -p` worker process

`bin/run_playbook.py:808–829` — `_pkill_fallback()` uses three patterns: `"bin/run_playbook.py"`, `"claude -p"`, `"claude --model"`. All three target the Claude CLI workers. A `--copilot` run invokes `gh copilot -p <prompt> --model gpt-5.4 --yolo` (`run_playbook.py:493–494`); that process's argv matches `bin/run_playbook.py` only on the parent, not on the `gh` child. If the parent crashed and the PID file is gone, the pkill fallback orphans every `gh` child.

### F-10 — `cleanup_repo` can silently revert agent-authored fixes outside `quality/`

`bin/benchmark_lib.py:177–250` — `cleanup_repo` lists tracked non-protected paths and `git checkout -- {paths}` with `check=False`. Protected prefixes are `quality/`, `control_prompts/`, `previous_runs/`, `docs_gathered/`.

For the bootstrap self-audit (QPB audited against itself), the "source" is `SKILL.md` and `references/` — tracked files that are NOT protected. If an agent proposes a fix by editing `SKILL.md`, the edit is reverted without notice. The bright-line workflow is that fixes go in `quality/patches/BUG-NNN-fix.patch`, but an inattentive agent that writes the fix directly into SKILL.md loses its work. Only a preview line in the log ("Tidied 1 tracked file(s) in QPB: SKILL.md") records what was silently reverted — and only if stdout is captured.

### F-11 — Run-metadata filename and JSON timestamp formats are inconsistent [TRACE]

`SKILL.md:123` and `SKILL.md:175–201` specify run metadata at `quality/results/run-YYYY-MM-DDTHH-MM-SS.json`. The filename uses `-` as the time separator (ISO-like but with dashes in the time part). Inside the JSON, `start_time` uses `YYYY-MM-DDTHH:MM:SSZ` with colons (line 187 example: `"2026-04-16T10:30:00Z"`).

There is no validator that checks either format. `quality_gate.py`'s `validate_iso_date` (line 156–173) expects `\d{4}-\d{2}-\d{2}` — date-only, not datetime. It has no check for the run-metadata file at all (the gate walks `check_tdd_sidecar`, `check_integration_sidecar`, `check_recheck_sidecar`, but not a `check_run_metadata`).

If an agent writes the filename as `run-2026-04-18T23:43:14.json` (with colons, which is valid ISO 8601 but illegal on Windows filesystems and quoted in URLs), the gate doesn't catch it; on NTFS the filename fails silently. The artifact contract says this file is **Required**, but no machine check enforces its presence, filename format, or internal schema.

## Quality Risks

Domain-driven failure scenarios ranked by priority. Each names a specific function, file, and line, describes a domain-specific edge case, and explains why the code produces wrong behavior.

### QR-1 [HIGH] — Three-way version-parser divergence breaks the bare-name fallback silently

Because `benchmark_lib._read_version` (regex, accepts `**Version:**`), `benchmark_lib.skill_version` (substring, `version:` only, case-sensitive), and `quality_gate.detect_skill_version` (loose substring, no numeric validation) each parse SKILL.md differently, any stylistic change to the frontmatter (bold form, quotes, different case) produces a silent divergence. The user-visible symptom — "`ERROR: 'chi' is not a directory (resolved to /cwd/chi)`" at `run_playbook.py:234` — does not say the fallback was skipped *because* skill_version returned None. A domain expert looking at the error has no way to know whether the issue is a missing directory or a silently disabled parser. (Code paths: `benchmark_lib.py:37,74,90–116`, `run_playbook.py:217`, `quality_gate.py:176-191`.)

### QR-2 [HIGH] — Thin-exploration bypass of the 120-line gate

The model writing EXPLORATION.md is the same model that is supposed to enforce the gate on it. When the runner gate at `run_playbook.py:455–457` is 80 and the skill's self-gate is 120, the agent under context pressure can satisfy the soft runner gate and skip the skill's self-check — the v1.3.41 and v1.3.43 failure modes called out at `SKILL.md:407,914` are exactly this. Because the runner gate is only a WARN, the failure is invisible. A 85-line file passes silently; subsequent phases produce diluted artifacts and never learn why.

### QR-3 [HIGH] — Bootstrap target source files are not protected from cleanup

`cleanup_repo` (`benchmark_lib.py:177–250`) protects `quality/`, `control_prompts/`, `previous_runs/`, `docs_gathered/` — all output/input directories. For a bootstrap self-audit where the *source* (SKILL.md, references/, bin/) is also the artifact under audit, there is no protection for source edits the agent makes. If the agent edits `SKILL.md` line 906 to try `120` → `100` (an incorrect "fix"), cleanup_repo silently reverts the edit. If it edits to insert a correct fix, same outcome. The agent loses work without warning. The correct workflow is patch-only, but there is no guardrail that rejects a direct edit — only a silent revert after the session ends.

### QR-4 [MEDIUM] — Archive race on parallel parent runs

`run_playbook.py:565–576` — two parent processes starting a Phase 1 run against the same target within the same timestamped second will both call `archive_previous_run(repo_dir, timestamp)`. Both compute the same `archive_dir` (`previous_runs/TIMESTAMP/quality`). The first deletes an existing archive if present and `copytree`s. The second also deletes (now removing the first parent's archive) and `copytree`s — but `quality/` has already been deleted by the first parent's `rmtree(quality_dir, ignore_errors=True)`. `copytree` will raise `FileNotFoundError` on the second parent, worker exits with an error, and the run fails midway. Per-parent PID files (line 779–787) prevent worker collision but not archive collision.

### QR-5 [MEDIUM] — Orphaned Copilot workers after parent crash

If the parent process crashes or is SIGKILLed after `write_pid_file()` (line 798) but before `wait_for_processes()` (line 883), the PID file is orphaned. A user running `--kill` later recovers the registered PIDs, but `_pkill_fallback` (the no-PID-file case) doesn't cover `gh copilot -p` workers — only claude patterns. The `gh` children continue to run, consuming API quota until the timeout or until the user manually finds and kills them. On a macOS laptop these can accumulate across forgotten runs.

### QR-6 [MEDIUM] — EXPLORATION.md structural non-conformance slips past quality_gate.py

SKILL.md's Phase 1 self-gate (lines 914–929) requires exact section titles: `## Open Exploration Findings`, `## Quality Risks`, `## Pattern Applicability Matrix`, `## Candidate Bugs for Phase 2`. The self-gate is model-enforced — if the model skips it, nothing downstream re-enforces it. `quality_gate.py:310–313` only checks `EXPLORATION.md exists`; it does not parse the section structure. So the exact failure mode called out at `SKILL.md:914` — chi and zod producing "Architecture summary / Behavioral contracts" instead of required sections — cannot be mechanically detected. A PR review would be the only catch.

### QR-7 [MEDIUM] — Integration recommendation enum accepts empty recommendation as "canonical"

`quality_gate.py:680–686` — when `recommendation` is empty string, the check goes into the `fail("recommendation missing")` branch. But `get_str(data, key)` at line 83–88 returns `""` for non-string values, so a `null` recommendation in JSON (which is likely during iteration drafts) also lands in the fail branch (correct). However, the check `if rec in ("SHIP", "FIX BEFORE MERGE", "BLOCK")` uses exact-match — a recommendation of `"ship"` (lowercase, which some models emit) is flagged non-canonical but the agent's *spelling* of the intent is correct. Same story for `result` in `groups[]` (line 689–700) and `uc_coverage` values (line 703–713). Any stringified boolean or differently-cased label is a fail. This is strict-by-design but punishes case-insensitive model output.

### QR-8 [MEDIUM] — `check_bugs_heading` zero-bug sentinel is a loose regex

`quality_gate.py:397` — `re.search(r"(No confirmed|zero|0 confirmed)", bugs_content)` is used to pass zero-bug BUGS.md files. Any prose containing the substring "zero" ("zero-day risks", "zero in on", "0 confirmed misses so far") satisfies the regex. Combined with `correct_headings == 0 and wrong_headings == 0`, any BUGS.md that has *no* proper bug headings and *contains* any of those substrings is marked as a valid zero-bug run, with no further checks on the file. An agent that produced garbage BUGS.md ("here is the zero-th analysis of the repository") would pass this section.

### QR-9 [LOW] — Run-metadata JSON has no gate at all

Per `SKILL.md:174–201`, `quality/results/run-YYYY-MM-DDTHH-MM-SS.json` is marked **Required** in the artifact contract (`SKILL.md:123`). `quality_gate.py:1027–1053` (check_repo) does not call any `check_run_metadata` — no such function exists. The file can be absent, malformed, or have bogus schema without any FAIL. The contract promises machine-verifiable coverage of "Required" artifacts, but this one is unpoliced.

### QR-10 [LOW] — Mechanical verification is required by the artifact contract but only enforced if present

`SKILL.md:115` lists `quality/mechanical/verify.sh` as "**Yes (benchmark)**". `quality_gate.py:854–880` (`check_mechanical`) only runs if `quality/mechanical/` exists as a directory: `if not mech_dir.is_dir(): info("No mechanical/ directory"); return`. The agent can skip mechanical verification entirely — even for projects whose contracts *clearly* require dispatch-function extraction — and pay only an INFO line, not a FAIL. The v1.3.23 failure mode described at `SKILL.md:638` (model overwrites correct extraction with fabricated content) is what verify.sh exists to catch; but a model that simply doesn't create verify.sh escapes verification entirely.

## Skeletons and Dispatch

State machines and dispatch tables discovered during exploration. Each is a candidate for mechanical enumeration checks (Pattern 4).

### Skeleton: Phase selection state machine

`bin/run_playbook.py:165–170` — phase modes: `""` (single-pass), `"all"` (all six), or comma list. `validate_phase_mode` at line 157 enforces membership in `{"1"…"6","all"}`. Consumers: `run_one()` (line 708) dispatches on `bool(phase_list)`; `check_phase_gate()` (line 445) has explicit branches for phases 2–6 and a `ValueError` for unknown phase (line 483).

### Skeleton: Iteration-strategy state machine

`bin/run_playbook.py:29` — `ALL_STRATEGIES = ["gap", "unfiltered", "parity", "adversarial"]`. `parse_strategy_list` (line 34) accepts members plus `all` shorthand. Successor table at `next_strategy()` (line 430–436):

```python
{"gap": "unfiltered", "unfiltered": "parity", "parity": "adversarial", "adversarial": ""}
```

Consumers: `execute_strategy_list` (line 718), `print_suggested_next_command` (line 949).

### Skeleton: Runner dispatch

`command_for_runner()` (line 486–494) — dispatches on `runner in {"claude", "copilot"}`. Claude path adds `--dangerously-skip-permissions`; Copilot path injects `DEFAULT_MODEL = gpt-5.4` (env-overridable).

### Dispatch: Protected-prefix filter for cleanup

`benchmark_lib.py:177–201` — `PROTECTED_PREFIXES = ("quality/", "control_prompts/", "previous_runs/", "docs_gathered/")`. `_is_protected(path)` uses `startswith`. This is a **closed set** that gates whether a tracked file is reverted. Absence of a prefix from the tuple means the file is *not* protected — candidate for Pattern 4 deep dive.

### Dispatch: SKILL_INSTALL_LOCATIONS

`benchmark_lib.py:39–43` — closed list of three paths that `find_installed_skill` walks. Documentation (`SKILL.md:48–55`) asserts four paths. Mismatch noted in F-3. Pattern 4 deep dive candidate.

### Dispatch: Language-to-valid-extension table

`quality_gate.py:812–823` — `lang_to_valid` maps detected language to space-separated valid extensions. Consumed by `check_test_file_extension` at line 828. Closed set; missing language → falls through to `not in valid_list` → FAIL. If a future repo in a new language (e.g., Elixir, Swift) is added to `detect_project_language` at line 214–225, `lang_to_valid` must also be updated in lockstep. Pattern 4 deep dive candidate.

### Dispatch: Verdict enum (gate)

`quality_gate.py:497–498` — `{"TDD verified", "red failed", "green failed", "confirmed open", "deferred"}`. Authoritative source: `SKILL.md:154`. Closed set; any agent-produced verdict outside the set fails. This one *is* kept in sync (SKILL.md and gate agree on all five).

## Pattern Applicability Matrix

| Pattern | Decision | Target modules | Why |
|---|---|---|---|
| Fallback and Degradation Path Parity | **FULL** | `benchmark_lib.py:90–125`, `run_playbook.py:192–244`, `quality_gate.py:1086–1094` | Multiple fallback chains: version parsers, install-path lookups, skill detection. F-1, F-3 flagged asymmetries in open exploration; Pattern 1 pressure-tests. |
| Dispatcher Return-Value Correctness | SKIP | n/a | The Python surface is mostly procedural orchestration; functions return either a list of paths, a `GateCheck` dataclass, or an exit code. The one dispatcher (`build_phase_prompt`) is a dict lookup that raises `KeyError` on unknown phase. No multi-condition handlers where return value could drift. |
| Cross-Implementation Contract Consistency | **FULL** | `benchmark_lib.py` vs `.github/skills/quality_gate/quality_gate.py` | Both modules implement "detect the skill version" and "find SKILL.md" with different code. F-1 and F-3 surface concrete drifts; the pattern catches them structurally. |
| Enumeration and Representation Completeness | **FULL** | `SKILL_INSTALL_LOCATIONS`, `PROTECTED_PREFIXES`, `lang_to_valid`, verdict enum, integration `recommendation` enum | Every closed set in the codebase has an authoritative source (SKILL.md prose). Pattern 4 enumerates the closed sets and diffs them against the spec. |
| API Surface Consistency | SKIP | n/a | The runner has a single public surface (the CLI); no method-overload or view/wrapper pairs. The gate is likewise single-surface. The only borderline candidate is "phased vs single-pass runs" but these are deliberately different prompts, not parallel implementations of the same contract. |
| Spec-Structured Parsing Fidelity | **FULL** | `benchmark_lib.skill_version`, `quality_gate.detect_skill_version`, `quality_gate.validate_iso_date`, run-metadata filename | YAML frontmatter parsed with `startswith("version:")`; ISO 8601 datetime parsed with `\d{4}-\d{2}-\d{2}` (drops the time). Structured grammars handled with ad-hoc string logic. |

**Selected FULL: 4** — Fallback Parity, Cross-Implementation Consistency, Enumeration Completeness, Spec-Structured Parsing. SKIP rationale is specific per pattern.

## Pattern Deep Dive — Fallback and Degradation Path Parity

The skill's "locate the SKILL.md" operation is implemented as a fallback chain in three different places; each chain differs slightly. Authoritative cascade (from `SKILL.md:48–55`): `references/` → `.claude/skills/quality-playbook/references/` → `.github/skills/references/` → `.github/skills/quality-playbook/references/`.

### Primary chain — `benchmark_lib.find_installed_skill` [benchmark_lib.py:128–139]

```python
SKILL_INSTALL_LOCATIONS = (
    Path(".github") / "skills" / "SKILL.md",
    Path(".claude") / "skills" / "quality-playbook" / "SKILL.md",
    Path("SKILL.md"),
)
```

Performs: (1) try `.github/skills/SKILL.md`, (2) try `.claude/...`, (3) try `SKILL.md`. **Missing:** `.github/skills/quality-playbook/SKILL.md`. Order also differs from SKILL.md (which puts `.claude` second, `.github/skills/` third).

### Secondary chain — `quality_gate.check_version_stamps` [quality_gate.py:969–976]

```python
skill_version = detect_skill_version([
    repo_dir / "SKILL.md",
    repo_dir / ".claude" / "skills" / "quality-playbook" / "SKILL.md",
    repo_dir / ".github" / "skills" / "SKILL.md",
    repo_dir / ".github" / "skills" / "quality-playbook" / "SKILL.md",
    SCRIPT_DIR / ".." / "SKILL.md",
    SCRIPT_DIR / "SKILL.md",
])
```

Performs: SKILL.md → `.claude/...` → `.github/skills/...` → `.github/skills/quality-playbook/...` → two SCRIPT_DIR fallbacks. **Has** the fourth path. Different order from `find_installed_skill`.

### Tertiary chain — `quality_gate.main` [quality_gate.py:1086–1094]

```python
version = detect_skill_version([
    SCRIPT_DIR / ".." / "SKILL.md",
    SCRIPT_DIR / "SKILL.md",
    Path("SKILL.md"),
    Path(".claude") / "skills" / "quality-playbook" / "SKILL.md",
    Path(".github") / "skills" / "SKILL.md",
    Path(".github") / "skills" / "quality-playbook" / "SKILL.md",
])
```

Performs: SCRIPT_DIR variants first, then CWD variants. Has the fourth path.

### Parity gaps

- `find_installed_skill` omits `.github/skills/quality-playbook/SKILL.md`. Fallback doesn't degrade gracefully; it fails with a misleading warning (F-3).
- Order is inconsistent across the three chains. A user with both `.claude/...` and `.github/skills/...` installed will get the `.github/skills/...` path from `find_installed_skill`, the `.claude/...` path from `check_version_stamps` (if SKILL.md at root is missing), and `.claude/...` from `main` — three different "which SKILL.md is authoritative?" answers for the same directory.
- `skill_version` (`benchmark_lib.py:90–116`) doesn't walk any fallback at all — it reads only `QPB_DIR / "SKILL.md"` (the project root of the runner itself). For an installed-into-target run where the SKILL.md lives at `<target>/.github/skills/SKILL.md`, the fallback isn't even considered by this function.

### Candidate requirements

- REQ-004 (see Derived Requirements): all three fallback chains must walk the same ordered list of install paths, and that list must match SKILL.md's documentation.
- REQ-005: `skill_version()` must walk the install locations when called with a target directory, not just `QPB_DIR`.

## Pattern Deep Dive — Cross-Implementation Contract Consistency

Multiple modules implement "read the version: field from a SKILL.md-like file". Each gives a different answer for the same input.

### Operation: "Read the version string from SKILL.md"

Authoritative source: `SKILL.md:5–6`:

```yaml
metadata:
  version: 1.4.5
```

### Implementation A — `benchmark_lib._read_version` [benchmark_lib.py:74–81]

Uses `VERSION_PATTERN`:
```python
VERSION_PATTERN = re.compile(r"^\s*(?:version:|\*\*Version:\*\*)\s*([0-9]+(?:\.[0-9]+)+)\b", re.IGNORECASE)
```

Steps: (1) open file, (2) for each line, `VERSION_PATTERN.match(line)`, (3) if matches, return `match.group(1)`. Accepts `version:`, `VERSION:`, `Version:`, `**Version:**`, etc. Rejects anything that isn't a pure dotted-numeric (e.g., `1.4.5-beta1` → matches `1.4.5` via the `\b` boundary but truncates the suffix; `"1.4.5"` with quotes → no match because the quote breaks the pattern).

### Implementation B — `benchmark_lib.skill_version` [benchmark_lib.py:90–116]

Steps: (1) open `QPB_DIR / "SKILL.md"`, (2) for each line, `stripped = line.lstrip()`, (3) `if not stripped.startswith("version:"): continue`, (4) take remainder, split on whitespace, return first token.

Differences from A: (a) case-sensitive; (b) only walks one file (QPB_DIR's SKILL.md), no fallback list; (c) accepts *anything* in the first whitespace-split token (including quotes, commas, other characters), (d) does NOT recognize the `**Version:**` bold form.

### Implementation C — `quality_gate.detect_skill_version` [quality_gate.py:176–191]

Steps: (1) for each location in list, try to open, (2) for each line, check `if "version:" in line` (substring anywhere on the line), (3) if matched, `re.sub(r".*version:\s*", "", line, count=1)`, (4) strip spaces and trailing CR/LF.

Differences from A and B: (a) substring match anywhere on the line — a comment `# version: 1.3.5` anywhere *matches*; (b) no numeric validation — returns the rest of the line after `version:`; (c) strips *all* spaces, not just outer whitespace — a multi-word token becomes concatenated.

### Divergence matrix

| Input SKILL.md line | `_read_version` (A) | `skill_version` (B) | `detect_skill_version` (C) |
|---|---|---|---|
| `  version: 1.4.5` | `1.4.5` | `1.4.5` | `1.4.5` |
| `  VERSION: 1.4.5` | `1.4.5` | `None` (case-sensitive) | `1.4.5` |
| `  **Version:** 1.4.5` | `1.4.5` | `None` | `*1.4.5` (depends) |
| `  version: "1.4.5"` | `""` (no match) | `"1.4.5"` (with quotes) | `"1.4.5"` (with quotes) |
| `# version: 1.3.5 (prior)` | `""` (no match — `#` prefix) | `None` (`#` prefix) | `1.3.5(prior)` (substring matched, spaces stripped) |
| `  version: 1.4.5-beta1` | `1.4.5` (truncated at `\b`) | `1.4.5-beta1` | `1.4.5-beta1` |

### Candidate requirements

- REQ-001 (see Derived Requirements): exactly one authoritative `skill_version()` helper; all other call sites must delegate.
- REQ-002: the helper must accept the bold form (`**Version:**`) since SKILL.md's own internal banner at line 42 uses that style, and any installer/bumper that rewrites the banner must not invalidate the parser.

## Pattern Deep Dive — Enumeration and Representation Completeness

Several closed sets in the code are derived from prose in `SKILL.md`. Each is a candidate for mechanical extraction and comparison.

### Closed set 1: `SKILL_INSTALL_LOCATIONS` [benchmark_lib.py:39–43]

- **Purpose:** paths `find_installed_skill` walks when a target is resolved.
- **Authoritative source:** `SKILL.md:48–55` (four paths).
- **Extracted entries (3):** `.github/skills/SKILL.md`, `.claude/skills/quality-playbook/SKILL.md`, `SKILL.md`.
- **Missing entry:** `.github/skills/quality-playbook/SKILL.md`. Confirmed present in `quality_gate.py:972–973` and explicit in SKILL.md.

### Closed set 2: `PROTECTED_PREFIXES` [benchmark_lib.py:177–182]

- **Purpose:** path prefixes that `cleanup_repo` refuses to revert.
- **Authoritative source:** inferred — there is no single-paragraph list in SKILL.md, but the comment above the tuple says "playbook run outputs and inputs." All agent-produced artifacts live under `quality/`; SKILL.md contracts also mention `control_prompts/`, `previous_runs/`, `docs_gathered/` as run-critical.
- **Extracted entries (4):** `quality/`, `control_prompts/`, `previous_runs/`, `docs_gathered/`.
- **Missing candidates:** none from SKILL.md directly, but `AGENTS.md` is a required artifact (`SKILL.md:106,122`) that lives at the project root, not under any prefix. An inattentive agent that regenerates `AGENTS.md` in Phase 2 has its regeneration reverted by cleanup_repo unless the agent uses a patch. See QR-3.

### Closed set 3: `lang_to_valid` in `check_test_file_extension` [quality_gate.py:812–823]

- **Purpose:** maps detected language to valid test-file extensions.
- **Authoritative source:** `detect_project_language` at `quality_gate.py:214–225` defines the language set; SKILL.md's test naming conventions (`SKILL.md:72`, e.g. "`test_functional.py` (Python), `FunctionalSpec.scala` (Scala), `functional.test.ts` (TypeScript), `FunctionalTest.java` (Java)") imply the extension-to-language mapping.
- **Extracted entries:** ten language keys matching `detect_project_language`.
- **Missing entries:** SKILL.md mentions Scala `.scala`, TypeScript `.ts`, Java `.java`, Rust `.rs`, Go `.go`, Python `.py`. The dict has all of these plus `kt`, `js`, `c`, `agc`. No obvious gap; this one is the best-maintained closed set in the codebase.

### Closed set 4: `ALL_STRATEGIES` [run_playbook.py:29]

- **Purpose:** iteration strategy names; any argument outside this set is rejected by `parse_strategy_list` (line 65–70).
- **Authoritative source:** `iteration.md:8–16` and `SKILL.md:280–287`.
- **Extracted entries (4):** gap, unfiltered, parity, adversarial. Matches the doc exactly.

### Closed set 5: Phase string set [run_playbook.py:161]

- **Purpose:** phase-mode members; `validate_phase_mode` rejects non-members.
- **Authoritative source:** SKILL.md sections "Phase 1"–"Phase 6" (explicitly named).
- **Extracted entries (6):** "1" through "6". Matches.

### Candidate requirements

- REQ-004: `SKILL_INSTALL_LOCATIONS` must contain all four paths listed in `SKILL.md:48–55`, in the order specified there.
- REQ-006: `PROTECTED_PREFIXES` must include `AGENTS.md` (or `AGENTS.md` must be moved under a protected prefix).

## Pattern Deep Dive — Spec-Structured Parsing Fidelity

YAML frontmatter and ISO 8601 datetimes are parsed with ad-hoc string logic rather than structured parsers. Each shortcut handles the common case but breaks on valid spec inputs.

### Parser 1: `skill_version` [benchmark_lib.py:90–116]

- **Spec:** YAML 1.2 (SKILL.md frontmatter is a YAML block enclosed in `---`).
- **Implementation technique:** `stripped.startswith("version:")` then `split()` first token.
- **Spec-valid input that breaks the parser:** `version: "1.4.5"` (YAML-valid quoted string). Parser returns `"1.4.5"` with the quotes included — the version string downstream comparisons would fail because `"1.4.5"` ≠ `1.4.5`.
- **Why it breaks:** no YAML parser, no quote handling. The "first whitespace-split token" heuristic assumes bare scalars only.

### Parser 2: `quality_gate.detect_skill_version` [quality_gate.py:176–191]

- **Spec:** YAML 1.2.
- **Implementation technique:** `if "version:" in line` (substring), then `re.sub(r".*version:\s*", "", line, count=1)` and strip all spaces.
- **Spec-valid input that breaks the parser:** a YAML block like this:
  ```yaml
  description: "The version: 1.4.5 release of the skill"
  version: 1.4.5
  ```
  The `description:` line contains the substring `"version:"` inside quotes, which the parser accepts as the match. It strips up through that inner `version:` and returns `1.4.5release` (all spaces removed). Downstream comparison against `1.4.5` fails.
- **Why it breaks:** substring scan, no line-start anchor, no YAML-aware key recognition.

### Parser 3: `validate_iso_date` [quality_gate.py:156–173]

- **Spec:** ISO 8601 (the SKILL.md contract at line 154 says `"ISO 8601 (YYYY-MM-DD), not a placeholder, not in the future"`).
- **Implementation technique:** `re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str)`.
- **Spec-valid input that breaks the parser:** `2026-04-18T23:43:14Z` — a full ISO 8601 datetime, which the SKILL.md run-metadata example uses for `start_time`/`end_time` (SKILL.md:187). `re.fullmatch` rejects anything beyond YYYY-MM-DD. Also: `2026-04-18T23:43:14+00:00` (another valid ISO form) is rejected.
- **Why it breaks:** regex is locked to a date-only sub-grammar; the spec says "ISO 8601" and the spec's own examples use datetime forms. The gate checks `tdd-results.json.date` against this — which must be date-only by convention — but any agent that writes an ISO datetime gets a FAIL on what is actually valid ISO 8601.

### Parser 4: run-metadata filename format — no parser at all

- **Spec:** `SKILL.md:123,175` — `run-YYYY-MM-DDTHH-MM-SS.json`.
- **Implementation:** not implemented. No gate checks this file's filename format, presence, or schema.
- **Spec-valid input that breaks the system:** an agent writes the filename with `HH:MM:SS` (colons, standard ISO) instead of `HH-MM-SS` (dashes). On NTFS/FAT this is illegal; the file write fails silently depending on filesystem. No gate reports the miss.

### Candidate requirements

- REQ-003: version parsing must use a single helper that accepts quoted and bold forms and rejects lines that only *contain* `version:` as a substring.
- REQ-007: datetime fields in sidecar JSON must be validated against the full ISO 8601 grammar (date-only and datetime), not just `\d{4}-\d{2}-\d{2}`, OR the SKILL.md contract must explicitly restrict fields to date-only.
- REQ-008: a `check_run_metadata()` section must exist in `quality_gate.py` that verifies the run-metadata file's filename format, presence, and minimal schema.

## Candidate Bugs for Phase 2

Consolidated from open exploration, quality risks, and pattern deep dives. Prioritized.

### CB-1 [HIGH] — Version-parser divergence silently disables bare-name fallback

- **Source stage:** Open exploration (F-1), Quality Risks (QR-1), Pattern deep dives (Cross-Implementation Consistency, Spec-Structured Parsing).
- **Code location:** `benchmark_lib.py:74-81` (`_read_version`), `benchmark_lib.py:90-116` (`skill_version`), `run_playbook.py:217` (call site), `quality_gate.py:176-191` (`detect_skill_version`).
- **What the code review should look for:** whether `skill_version()` and `_read_version()` agree on every plausible SKILL.md frontmatter (bare form, bold form, quoted, case variations). Whether the `ERROR: '...' is not a directory` message communicates that the fallback was considered but skill_version returned None. Whether the three version parsers have tests that assert identical behavior on identical input.

### CB-2 [HIGH] — Fourth install path missing from `SKILL_INSTALL_LOCATIONS`

- **Source stage:** Open exploration (F-3), Pattern deep dives (Fallback Parity, Enumeration Completeness).
- **Code location:** `benchmark_lib.py:39-43` vs `SKILL.md:48-55` vs `quality_gate.py:972-976` vs `quality_gate.py:1091-1094`.
- **What the code review should look for:** verify the constant tuple matches the SKILL.md documentation exactly; confirm all three chains (`find_installed_skill`, `check_version_stamps`, `main`) use the same list and order; flag the divergence as a single source-of-truth bug.

### CB-3 [HIGH] — EXPLORATION.md line-count threshold drift (80 vs 120)

- **Source stage:** Open exploration (F-2), Quality Risks (QR-2).
- **Code location:** `run_playbook.py:455-457`, `SKILL.md:906,916`, `orchestrator_protocol.md:41`.
- **What the code review should look for:** whether the runner gate enforces 120 (matching the skill's self-gate), or whether the skill's self-gate lowers to 80 (matching the runner). Three-way inconsistency is the bug; any single source of truth fixes it. Also: `run_playbook.py` gate is only a WARN — should it be a FAIL?

### CB-4 [HIGH] — `archive_previous_run` not atomic; control_prompts/ discarded

- **Source stage:** Open exploration (F-4), Quality Risks (QR-4).
- **Code location:** `run_playbook.py:565-576`.
- **What the code review should look for:** whether `copytree` followed by `rmtree` can leave the repo in a half-archived state; whether `control_prompts/` should be archived alongside `quality/` for debugging; whether concurrent parallel runs against the same target within the same second race.

### CB-5 [MEDIUM] — Bootstrap target source files unprotected from cleanup

- **Source stage:** Open exploration (F-10), Quality Risks (QR-3), Pattern deep dive (Enumeration Completeness).
- **Code location:** `benchmark_lib.py:177-250`, `SKILL.md:106,122` (AGENTS.md contract).
- **What the code review should look for:** whether `AGENTS.md` (required at project root) is reverted by cleanup_repo in a bootstrap run where an agent regenerates it as part of Phase 2; whether the cleanup log line is visible to users or only emitted to a log file; whether a patch-only workflow is enforced anywhere.

### CB-6 [MEDIUM] — Phase 3 entry gate incomplete

- **Source stage:** Open exploration (F-5), Quality Risks (none directly — this is a contract gap, not a runtime failure scenario).
- **Code location:** `run_playbook.py:459-463` vs `SKILL.md:94-123` (artifact contract) and `run_playbook.py:579-595` (`final_artifact_gaps`).
- **What the code review should look for:** whether the Phase 3 gate should require all Phase 2 artifacts the `final_artifact_gaps` check looks for at the end, or whether a deliberate subset is OK; whether Phase 4 and Phase 5 gates have the same partial-enforcement issue.

### CB-7 [MEDIUM] — `docs_present` accepts noise-only directories

- **Source stage:** Open exploration (F-6).
- **Code location:** `run_playbook.py:560-562`.
- **What the code review should look for:** whether the presence check should count actual document files (non-hidden, non-empty) or is `any(iterdir())` sufficient; what the failure mode looks like when `docs_gathered/.DS_Store` is the only entry.

### CB-8 [MEDIUM] — Suggestion printed after failed runs

- **Source stage:** Open exploration (F-8), Quality Risks (QR-5 tangentially).
- **Code location:** `run_playbook.py:930-946`.
- **What the code review should look for:** whether `print_suggested_next_command` should gate on `failures == 0` or on `status == 0`; whether the suggestion should switch to "Retry with `--phase 1`" when a crash occurred.

### CB-9 [MEDIUM] — `_pkill_fallback` misses Copilot workers

- **Source stage:** Open exploration (F-9), Quality Risks (QR-5).
- **Code location:** `run_playbook.py:808-829`.
- **What the code review should look for:** whether the pattern list should include `"gh copilot -p"` for Copilot orphan recovery; whether the pattern `"claude -p"` risks killing *unrelated* Claude CLI sessions on the user's machine and should be narrowed to the playbook's exact invocation string.

### CB-10 [LOW] — Quality gate does not verify run-metadata JSON

- **Source stage:** Open exploration (F-11), Quality Risks (QR-9), Pattern deep dive (Spec-Structured Parsing).
- **Code location:** `quality_gate.py:1027-1053` (missing `check_run_metadata`), `SKILL.md:123,174-201`.
- **What the code review should look for:** whether the gate should enforce the filename format, the presence of required fields (`schema_version`, `skill_version`, `project`, `model`, `start_time`), and internal JSON validity; whether `validate_iso_date` needs to be extended or replaced with a full ISO 8601 datetime parser for `start_time`/`end_time`.

### CB-11 [LOW] — EXPLORATION.md structural non-conformance slips past quality_gate

- **Source stage:** Quality Risks (QR-6), Pattern deep dive (Enumeration Completeness).
- **Code location:** `quality_gate.py:310-313`.
- **What the code review should look for:** whether `quality_gate.py` should parse EXPLORATION.md for the required section titles (`## Open Exploration Findings`, `## Quality Risks`, `## Pattern Applicability Matrix`, `## Candidate Bugs for Phase 2`, `## Gate Self-Check`) and FAIL on absence, so that the model's self-gate failure is mechanically detected.

### CB-12 [LOW] — Zero-bug sentinel in `check_bugs_heading` is a loose regex

- **Source stage:** Quality Risks (QR-8).
- **Code location:** `quality_gate.py:397`.
- **What the code review should look for:** whether the sentinel should be anchored (e.g., `^## No confirmed bugs$`) or whether only structured file content (explicit count field) should satisfy the zero-bug path.

## Derived Requirements

Working identifiers — Phase 2 will renumber and expand with full conditions of satisfaction, doc sources, tiers.

- **REQ-001 [Tier 2] [source] `benchmark_lib.py:90-116`, `benchmark_lib.py:74-81`, `quality_gate.py:176-191`** — The repository must expose exactly one authoritative `skill_version` helper. All other call sites must delegate to it. The helper must accept lines beginning with `version:` (case-insensitive) and `**Version:**` (bold form, case-insensitive). Specificity: **specific**.
- **REQ-002 [Tier 1] [SKILL.md §Locating reference files, line 48-55]** — `SKILL_INSTALL_LOCATIONS` in `benchmark_lib.py` must include all four paths documented in SKILL.md §Locating reference files, in the order SKILL.md specifies. Specificity: **specific**.
- **REQ-003 [Tier 2] [source] `benchmark_lib.py:74-81`, `quality_gate.py:176-191`** — Version-parsing helpers must reject lines that only *contain* the substring `version:` (e.g., inside a quoted description field). Match must be at the start of a stripped line. Specificity: **specific**.
- **REQ-004 [Tier 1] [SKILL.md §Phase 1 completion gate, line 906,916]** — Phase 1 must produce an `EXPLORATION.md` of at least 120 lines of substantive content. The entry gate in `run_playbook.py:check_phase_gate` for Phase 2 must FAIL (not WARN) when the line count is below 120. Specificity: **specific**.
- **REQ-005 [Tier 2] [source] `benchmark_lib.py:90-116`, `run_playbook.py:217`** — When `skill_version()` returns None, the subsequent `ERROR: ... is not a directory` message must explicitly state that the version-append fallback was attempted or skipped, and why. Specificity: **specific**.
- **REQ-006 [Tier 1] [SKILL.md §Complete Artifact Contract, line 106,122]** — `AGENTS.md` at the project root is a required artifact. `cleanup_repo` must not revert edits to it, OR the playbook must provide a gate that catches silent cleanup reversions of required artifacts. Specificity: **specific**.
- **REQ-007 [Tier 1] [SKILL.md §Sidecar JSON Canonical Examples, line 154]** — ISO 8601 date validation in `quality_gate.py:validate_iso_date` must align with the fields it checks: date-only fields (`date` in sidecars) use `YYYY-MM-DD`; datetime fields (`start_time`/`end_time` in run-metadata) must accept the full ISO 8601 datetime grammar (with `T` and timezone suffix). Specificity: **specific**.
- **REQ-008 [Tier 1] [SKILL.md §Complete Artifact Contract, line 123; §Run Metadata, line 174-201]** — `quality_gate.py` must include a `check_run_metadata` section that verifies presence, filename format (`run-YYYY-MM-DDTHH-MM-SS.json`), JSON parseability, and the required fields (`schema_version`, `skill_version`, `project`, `model`, `start_time`). Specificity: **specific**.
- **REQ-009 [Tier 2] [source] `run_playbook.py:565-576`** — `archive_previous_run` must leave the repository in a consistent state under crash recovery: either both `quality/` and `previous_runs/TIMESTAMP/quality/` exist simultaneously (no destructive move until copy is verified), or the operation is atomic at the OS level. `control_prompts/` must be archived alongside `quality/`, not discarded. Specificity: **specific**.
- **REQ-010 [Tier 2] [source] `run_playbook.py:459-463`] —** The Phase 3 entry gate must require all Phase 2 artifacts that the artifact contract marks as required (not just the four currently checked). The same rule applies to Phase 4 and Phase 5 entry gates. Specificity: **specific**.
- **REQ-011 [Tier 2] [source] `run_playbook.py:560-562`] —** `docs_present()` must verify the directory contains at least one non-hidden, non-empty documentation file — not just that `iterdir()` yields anything. Specificity: **specific**.
- **REQ-012 [Tier 2] [source] `run_playbook.py:808-829`] —** `_pkill_fallback` must cover `gh copilot` workers in addition to `claude` workers. The `claude -p` pattern must be narrowed so it does not kill unrelated Claude CLI sessions the user is running. Specificity: **specific**.
- **REQ-013 [Tier 1] [SKILL.md §Phase 1 completion gate, line 914,919]** — `quality_gate.py` must parse `EXPLORATION.md` for the required exact section titles and FAIL when any are missing. The mechanical gate must mirror the skill's self-gate. Specificity: **specific**.
- **REQ-014 [Tier 2] [source] `run_playbook.py:930-946`] —** `print_suggested_next_command` must not suggest "next iteration" when the run returned non-zero. When failures occurred, the suggestion must tell the user to investigate or re-run the failed phase. Specificity: **specific**.
- **REQ-015 [Tier 3] [source] `quality_gate.py:397`** — The zero-bug sentinel in `check_bugs_heading` must use an anchored regex (e.g., match a specific zero-bug declaration section) rather than a free substring search for "zero" or "0 confirmed". Specificity: **specific**.
- **REQ-016 [Tier 3] [source] `benchmark_lib.py:185-196`** — `_parse_porcelain_path` must handle quoted paths from `git status --porcelain` (paths with special characters are quoted unless `-z` is used). Specificity: **specific**.
- **REQ-017 [Tier 2] [source] architectural; spans `benchmark_lib.py`, `run_playbook.py`, `quality_gate.py`** — The runner, the library, and the gate must share a single canonical source for closed sets that mirror SKILL.md prose (install paths, protected prefixes, verdict enum, iteration strategies, phase identifiers). Drift between any two is a bug. Specificity: **architectural-guidance**.

## Derived Use Cases

Phase 2 will expand each of these with trigger events, preconditions, acceptance criteria, and links to requirements. They are scoped to the QPB project, not to any target being audited.

- **UC-01 — Maintainer runs the playbook against a single target repository.**
  Actor: QPB maintainer (end-user developer). Goal: generate a full quality system for a third-party repo so they can evaluate bug yield and compare across models.
  Trigger: `python3 bin/run_playbook.py <target>` from the QPB directory. Expected outcome: `quality/` populated in the target, log file alongside the target, artifact summary printed.

- **UC-02 — Maintainer runs a bootstrap self-audit (QPB audited against itself).**
  Actor: QPB maintainer. Goal: catch quality issues in the skill itself using the skill's own methodology. Specific to this run.
  Trigger: `bin/run_playbook.py .` (target = QPB root). Expected outcome: exploration findings about the skill's own prose, code, and gates land in `quality/EXPLORATION.md`, not mixed with any target-specific noise. `docs_gathered/` supplies the meta-context that makes the exploration meaningful.

- **UC-03 — Benchmark operator compares multiple AI agents against the same target.**
  Actor: a researcher replicating v1.4.5 benchmark numbers. Goal: run the same target against Claude Opus, Claude Sonnet, GPT-5.4, Copilot to compare bug yield. Trigger: multiple `bin/run_playbook.py --claude --model opus|sonnet` invocations plus Copilot runs. Expected outcome: each run produces a timestamped archive in `previous_runs/`, and the run-metadata JSON captures `model`, `model_provider`, `runner`, `start_time`, `end_time` for cross-model analysis.

- **UC-04 — Benchmark operator runs a full-cycle iteration chain.**
  Actor: same as UC-03 but running `--full-run` or the iteration cycle manually. Goal: capture the 40–60% iteration uplift described in `SKILL.md:227`. Trigger: `bin/run_playbook.py --full-run <target>` or chained `--next-iteration --strategy gap|unfiltered|parity|adversarial`. Expected outcome: strategy chain runs with early stop on zero-gain; each strategy's findings merge into `EXPLORATION_MERGED.md`; the Demoted Candidates manifest is populated for the adversarial pass.

- **UC-05 — Maintainer kills a runaway parallel run.**
  Actor: same user who started a parallel benchmark from a terminal. Goal: stop all worker processes on demand without searching the process tree manually. Trigger: `python3 bin/run_playbook.py --kill` (or Ctrl-C in the controlling terminal). Expected outcome: every registered worker PID (across all parent parents) receives SIGTERM; PID files are cleaned up; orphaned workers from a crashed parent are recovered via the pkill fallback.

- **UC-06 — User (non-maintainer) runs the playbook on their own project via an AI agent.**
  Actor: a developer on some unrelated project who installs the skill and asks their AI agent (Claude Code, Cursor, Copilot) to run the playbook. Goal: get a quality system generated for their codebase without having to run any Python themselves. Trigger: the user types "Run the quality playbook on this project" in their AI chat; the agent reads `.github/skills/SKILL.md` (or Claude/Copilot variant) and walks the six phases interactively. Expected outcome: end-of-phase messages guide the user through phases 1→2→3→4→5→6, each in its own chat context.

- **UC-07 — Operator validates a completed run with the quality gate.**
  Actor: the user or CI. Goal: confirm mechanically that the generated artifacts conform to the artifact contract. Trigger: `python3 .github/skills/quality_gate/quality_gate.py .` (or `--all` for a batch). Expected outcome: 0 FAIL required to ship; WARN counts surfaced; per-benchmark pass/fail details in the log.

## Notes for Artifact Generation

Context that Phase 2 will need to generate correct artifacts without re-exploring:

- **Test framework:** stdlib unittest only. The pytest shim at `pytest/__main__.py` makes `python3 -m pytest` route to `unittest.main`. Functional tests (Phase 2) should use `import unittest; class X(unittest.TestCase)`; do not introduce pytest-style fixtures or decorators.
- **Import pattern:** `from bin import run_playbook` and `from bin import benchmark_lib as lib` (seen in `bin/tests/test_run_playbook.py:6` and `bin/tests/test_resolve_targets.py:22`). New tests must use the same pattern or imports will fail.
- **Monkey-patch idiom:** `FakeQPBRoot` in `bin/tests/test_resolve_targets.py:26-68` is the template for tests that need to swap `lib.QPB_DIR`. Don't invent a new pattern; extend or reuse this.
- **SKILL.md line counts and offsets:** Phase 2 will re-read sections of SKILL.md. Key offsets: Phase 1 starts line 347, ends line 945 (the `---` before Phase 2); artifact contract table is 90–123; sidecar examples 131–171; run-metadata 174–201; iteration strategies in a separate reference.
- **Authoritative closed sets** (see Pattern deep dives) — Phase 2 should lift these verbatim into CONTRACTS.md: `SKILL_INSTALL_LOCATIONS`, `PROTECTED_PREFIXES`, `ALL_STRATEGIES`, verdict enum, recommendation enum, `lang_to_valid`. Each becomes a contract line with a citation.
- **Specificity spread:** 16 of the 17 derived requirements are `specific`; 1 is `architectural-guidance`. This is under the ≤3 limit for architectural-guidance (`SKILL.md:701-708`), and above the `0-on-15+` minimum. No reclassification needed.
- **Functional test file naming:** for this project, the right name is `quality/test_functional.py` (Python project detected by `quality_gate.py:214-225`). `check_test_file_extension` will FAIL on any other extension.
- **Regression tests:** when bugs are confirmed in Phase 3, they go in `quality/test_regression.py` in the same module style.
- **Mechanical verification applicability:** this project has closed-set contracts (the five enumerations in the Enumeration deep dive). Phase 2 **should** create `quality/mechanical/` with a `verify.sh` that mechanically extracts each closed set and diffs against a saved baseline. Do NOT skip with "not applicable" — this project is the canonical case for mechanical extraction.
- **Documentation depth:** `docs_gathered/03_DEVELOPMENT_CONTEXT.md` is the deepest single document and gives the three-axis improvement model (exploration / iteration / triage) that should inform QUALITY.md's coverage targets. `docs_gathered/04_BENCHMARK_PROTOCOL.md` is the reference for any Phase 5 TDD protocol wording. `50_Quality_Playbook_Patent_Review.md` and `51_*.pdf` inform the "novel mechanism" framing for architectural-guidance requirements.
- **No external services:** QPB has no DB, no HTTP server, no background worker. Integration tests (`RUN_INTEGRATION_TESTS.md`) should exercise the full benchmark pipeline end-to-end (parse → run → gate), using a synthetic target repo fixture. UC-mapping: UC-01, UC-02, UC-07 exercise the integration pipeline.
- **Project overview for REQUIREMENTS.md** (per SKILL.md:654–665): lead with "Quality Playbook is an AI-driven quality-engineering skill: given any codebase, a compliant AI agent follows its six-phase procedure to produce a complete quality system — requirements, functional tests, a three-pass code review with regression tests, a Council-of-Three spec audit, TDD-verified patches, and a post-run validation gate. The skill is installed into a target repo under `.github/skills/` or `.claude/skills/` and is invoked by asking an AI agent to 'run the quality playbook'. The repository also ships a Python benchmark harness (`bin/run_playbook.py`) that runs the skill non-interactively across multiple target repos for cross-model comparison, and a post-run gate (`quality_gate.py`) that mechanically validates artifact conformance." Actors: QPB maintainer, benchmark operator, non-maintainer end-user developer running the skill in their own repo via an AI agent, the AI agent itself (five major vendors).

## Gate Self-Check

Executed per SKILL.md:912–929. Each check was run against the on-disk contents of `quality/EXPLORATION.md` and `quality/PROGRESS.md` after they were written.

1. **PASS** — `quality/EXPLORATION.md` is 631 lines (≥ 120). Content is substantive findings with file paths, line numbers, derived requirements, and use cases — not padding.
2. **PASS** — `quality/PROGRESS.md` exists and its Phase 1 completion line is marked `[x]` with timestamp `2026-04-18T23:43:14Z`.
3. **PASS** — `## Derived Requirements` contains REQ-001 through REQ-017 (17 entries), each with a specific file path and, where applicable, a function name and line range (e.g., REQ-002 cites `benchmark_lib.py:90-116` and names `skill_version`).
4. **PASS** — A section titled `## Open Exploration Findings` exists (line 105) with 11 findings (F-1 through F-11). Every finding names a file and line number. Findings span four modules: `benchmark_lib.py` (F-1, F-3, F-11), `run_playbook.py` (F-4, F-7, F-8, F-10), `quality_gate.py` (F-5, F-6), and `SKILL.md` vs runner (F-2), plus `_pkill_fallback` patterns (F-9) — ≥ 4 distinct subsystems/modules.
5. **PASS** — Findings F-1, F-3, F-4, F-6, F-7, F-8, and F-11 are tagged `[TRACE]` and each traces behavior across ≥ 2 functions or code locations (e.g., F-1 traces `_read_version` + `skill_version` + `detect_skill_version`; F-4 traces `archive_previous_run` + `cleanup_repo`; F-11 traces filename generation + JSON timestamp write). Seven TRACE findings is well above the ≥ 3 minimum.
6. **PASS** — A section titled `## Quality Risks` exists (line 204) with 10 domain-driven failure scenarios QR-1 through QR-10 ranked HIGH/MEDIUM/LOW. Each names a specific function/file/line, describes a domain-specific failure (e.g., QR-1: bare-name CLI invocation on a SKILL.md shipped with the bold version form silently resolves to a nonexistent directory); QR-3 explains why bootstrap self-audits risk reverting real source edits. None of the risks are "the code does this right" observations or "mature library" dismissals.
7. **PASS** — A section titled `## Pattern Applicability Matrix` exists (line 286) with a six-row table covering every pattern from `exploration_patterns.md`: Fallback Parity (FULL), Dispatcher Return-Value (SKIP with rationale), Cross-Implementation Consistency (FULL), Enumeration Completeness (FULL), API Surface Consistency (SKIP with rationale), Spec-Structured Parsing (FULL). Each row lists target modules and codebase-specific rationale.
8. **PASS** — Exactly 4 patterns are marked FULL (Fallback Parity, Cross-Implementation Consistency, Enumeration Completeness, Spec-Structured Parsing). 4 is within [3, 4].
9. **PASS** — Exactly 4 sections begin with `## Pattern Deep Dive — ` (lines 299, 356, 406, 448). Each contains concrete file:line evidence (e.g., `benchmark_lib.py:128–139`, `quality_gate.py:969–976`, specific regex strings, line-count threshold numbers). Count matches the 4 FULL patterns in the matrix.
10. **PASS** — All 4 pattern deep-dives trace code paths across ≥ 2 functions: Fallback Parity compares `find_installed_skill` + `check_version_stamps` + `quality_gate.main`; Cross-Implementation Consistency compares `_read_version` + `skill_version` + `detect_skill_version`; Enumeration Completeness walks 5 closed sets each defined in one location and consumed in another; Spec-Structured Parsing compares 4 parsers. Well above the ≥ 2 minimum.
11. **PASS** — A section titled `## Candidate Bugs for Phase 2` exists (line 490) with 12 prioritized bug hypotheses CB-1 through CB-12. Each entry names file:line, tags the stage that surfaced it (F-n / QR-n / Pattern n), and names what the code review should verify.
12. **PASS** — Ensemble balance confirmed: CB-1, CB-2, CB-3, CB-4, CB-5, CB-6, CB-7, CB-8, CB-9 all originate from open exploration (F-1…F-11) or quality risks (QR-1…QR-10) — far above the ≥ 2 minimum; CB-1, CB-2, CB-3, CB-11 are materially strengthened by the Cross-Implementation / Enumeration pattern deep dives; CB-10 was surfaced by Pattern 4 (Enumeration Completeness applied to the run-metadata closed-set). ≥ 1 pattern-strengthened candidate is satisfied multiple times over.

**Gate result: 12/12 PASS.** Phase 1 may complete. Proceed to writing the end-of-phase message and STOP — per SKILL.md:948, Phase 2 will not be entered unless the user explicitly asks.


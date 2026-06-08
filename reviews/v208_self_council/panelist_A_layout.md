# Panelist A — Layout correctness + defensive sweep

## ROLE-LOCK PREAMBLE

I am Panelist A, a self-Council reviewer for instruction 208 at commit
`bfea8a1`. I am NOT the orchestrator. My single deliverable is this
verdict file, which ends in a `VERDICT: SHIP | CONCERN | FIX-REQUIRED`
block. I do not simulate the orchestrator, do not run the other
panelists, do not aggregate.

## 1. Charter recap

Verify `_bundle_files()` sources, no duplicates at old root, defensive
sweep of `bin/*.py` + `bin/tests/*.py` for hardcoded OLD paths
(`SKILL.md`/`references/`/`phase_prompts/`/`agents/`/`quality_gate.py`/
`ai_context/TOOLKIT.md` at root), `_bundle/` destination paths
unchanged, and `marketplace.json` drops `skills` + `strict`.

## 2. `_bundle_files()` audit — 57 entries, every source under `skills/quality-playbook/`

I executed `_bundle_files(repo_root)` via importlib and dumped every
`(src, dst_rel)` pair. All 57 entries resolve under
`skills/quality-playbook/...`. Sample (full enumeration produced 57
files; abbreviated here):

| dst_rel | src (under repo) |
| --- | --- |
| `SKILL.md` | `skills/quality-playbook/SKILL.md` |
| `quality_gate.py` | `skills/quality-playbook/scripts/quality_gate.py` |
| `skill-template.gitignore` | `skills/quality-playbook/skill-template.gitignore` |
| `ai_context/TOOLKIT.md` | `skills/quality-playbook/ai_context/TOOLKIT.md` |
| `references/*.md` (24) | `skills/quality-playbook/references/*.md` |
| `phase_prompts/*.md` (10) | `skills/quality-playbook/phase_prompts/*.md` |
| `agents/*.md` (3) | `skills/quality-playbook/agents/*.md` |
| `bin/citation_verifier.py` | `skills/quality-playbook/scripts/citation_verifier.py` |
| `bin/_purpose.py` | `skills/quality-playbook/scripts/_purpose.py` |
| `bin/reference_docs_ingest.py` | `skills/quality-playbook/scripts/reference_docs_ingest.py` |
| `bin/benchmark_lib.py` | `skills/quality-playbook/scripts/benchmark_lib.py` |
| `bin/__init__.py` | `skills/quality-playbook/scripts/__init__.py` |
| `bin/quality_playbook.py` | `skills/quality-playbook/scripts/quality_playbook.py` |
| `bin/archive_lib.py` | `skills/quality-playbook/scripts/archive_lib.py` |
| `bin/council_semantic_check.py` | `skills/quality-playbook/scripts/council_semantic_check.py` |
| `bin/migrate_v1_5_0_layout.py` | `skills/quality-playbook/scripts/migrate_v1_5_0_layout.py` |
| `bin/role_map.py` | `skills/quality-playbook/scripts/role_map.py` |
| `bin/council_config.py` | `skills/quality-playbook/scripts/council_config.py` |
| `bin/run_state_lib.py` | `skills/quality-playbook/scripts/run_state_lib.py` |
| `bin/validate_phase_artifacts.py` | `skills/quality-playbook/scripts/validate_phase_artifacts.py` |
| `bin/qpb_config.py` | `skills/quality-playbook/scripts/qpb_config.py` |
| `bin/qpb_validate.py` | `skills/quality-playbook/scripts/qpb_validate.py` |
| `bin/qpb_phase.py` | `skills/quality-playbook/scripts/qpb_phase.py` |

Confirmed clean. `_resolve_bundle_source_root()` + `_scripts_dirname()`
correctly redirect the QPB clone root to the skill folder and pick
`scripts/` over `bin/` at source.

## 3. No-duplicates check

```
$ ls SKILL.md references phase_prompts agents quality_gate.py
  skill-template.gitignore ai_context/TOOLKIT.md
  .github/skills/quality_gate/quality_gate.py
```
All seven returned "No such file or directory". The legacy
`.github/skills/quality_gate/` directory keeps only `__init__.py`
(a re-export shim that loads the canonical script by file path
from the new location) and `tests/`. No file is duplicated at
both old and new locations.

## 4. Defensive sweep — FIVE STALE legacy-path imports in `bin/tests/*.py`

Three layers of sweep:

**4a. Source-side root-relative constants (`bin/*.py`)** — all 9
matches confirmed pointing at the NEW location:
- `bin/build_channel_package.py:154`: `skill_folder / "SKILL.md"` where `skill_folder = repo_root / "skills" / "quality-playbook"` — OK.
- `bin/classify_project.py:293-295`: probes `target_dir / "SKILL.md"` (adopter-target-relative), then falls back to nested plugin-native location — OK (adopter-side, not QPB source).
- `bin/qpb_harness.py:228`: `Path(__file__).resolve().parents[1] / "skills" / "quality-playbook" / "SKILL.md"` — OK.
- `bin/run_playbook.py:1220-1223`: `PHASE_PROMPTS_DIR = ... / "skills" / "quality-playbook" / "phase_prompts"` — OK.
- `bin/run_playbook.py:2927-2928`: `_skill_src_root = qpb_root / "skills" / "quality-playbook"` + `for subdir in ("references", "phase_prompts", "agents")` — OK (joined under the skill folder).
- `bin/run_playbook.py:4913-4924` (`_GATE_INSTALL_LOCATIONS`): install-target paths — OUT-OF-SCOPE (adopter side, the documented 10 AI-tool install layouts; gate at `.claude/skills/quality-playbook/quality_gate.py` etc., not a QPB source location).
- `bin/run_playbook.py:4440`: prose-string `python3 .github/skills/quality_gate.py .` — same adopter help string; OUT-OF-SCOPE (the `.github/skills/quality_gate.py` form is one of the 10 documented adopter install layouts and refers to the adopter's install root, not the QPB clone).
- `bin/submit_awesome_copilot.py:1091`: `repo_root / "skills" / "quality-playbook" / "SKILL.md"` — OK.
- `bin/submit_awesome_copilot.py:432-434, 761, 766`: write paths INSIDE a freshly created packet dir, not QPB-source-relative — OK.

**4b. `ai_context/TOOLKIT.md`** — every match in `bin/*.py` /
`bin/tests/*.py` either (a) is a string literal in a test fixture
or (b) reads from `_SKILL_DIR / "ai_context" / "TOOLKIT.md"` where
`_SKILL_DIR` is the new skill folder. Confirmed via
`test_doc_gathering_skill_integration_132.py:132-134`,
`test_plugin_layout_208.py:97-100`, and `test_doc_drift.py:65,326`.

**4c. `quality_gate.py` legacy `.github/skills/quality_gate/` import**
— **FIVE stale references in `bin/tests/*.py`**. Each does
`sys.path.insert(0, str(LEGACY_GATE_DIR))` then `import quality_gate`,
where `LEGACY_GATE_DIR = <repo>/.github/skills/quality_gate/`. The
post-208 file layout there is `__init__.py` + `tests/` only — no
`quality_gate.py` file — so `import quality_gate` raises
`ModuleNotFoundError` in isolation.

| File | Line | Stale path |
| --- | --- | --- |
| `bin/tests/test_citation_stale.py` | 37 | `_QPB_ROOT / ".github" / "skills" / "quality_gate"` |
| `bin/tests/test_cardinality_gate.py` | 18 | `QPB_ROOT / ".github" / "skills" / "quality_gate"` |
| `bin/tests/test_phase3_prompt_worked_example.py` | 27 | `QPB_ROOT / ".github" / "skills" / "quality_gate"` |
| `bin/tests/test_phase6_integration.py` | 36 | `Path(...).resolve().parents[2] / ".github" / "skills" / "quality_gate"` |
| `bin/tests/test_quality_gate_language_detection.py` | 54 | `_QPB_ROOT / ".github" / "skills" / "quality_gate"` |

I confirmed empirically that each of these five test files **fails
to import in isolation** with:

```
ImportError: Failed to import test module: test_phase6_integration
ModuleNotFoundError: No module named 'quality_gate'
```

The full `unittest discover bin/tests` run only "passes" because
some EARLIER alphabetically-discovered test (`test_archive_lib.py`
imports succeed via a different route, then by the time the
five-file suspects load, `sys.modules['quality_gate']` is already
populated). Reproduced both modes:

- `python3 -m unittest bin.tests.test_phase6_integration` →
  `FAILED (errors=1) ModuleNotFoundError: No module named 'quality_gate'`
- `python3 -m unittest bin.tests.test_phase3_prompt_worked_example
  bin.tests.test_cardinality_gate bin.tests.test_citation_stale
  bin.tests.test_phase6_integration
  bin.tests.test_quality_gate_language_detection`
  → `FAILED (errors=5)` — all five fail.
- `python3 -m unittest discover bin/tests -t .` →
  3219 tests run, 1 failure (the pre-existing README line-number drift
  the build agent already flagged), errors=0 — the five-suspect
  failures are masked by sys.modules cache pollution from an
  earlier-loaded test.

The pre-208 contract was: every test runs cleanly in isolation
(developers do focused TDD on a single file constantly). 208 broke
this contract for 5 test files. The companion `test_phase7_variations.py`
WAS correctly updated to point at
`skills/quality-playbook/scripts/` (line 36-42), proving the fix is
known and small; the sweep just missed these five neighbours.

**Fix:** in each of the 5 files, change the `.github/skills/quality_gate`
path token to `skills/quality-playbook/scripts` (the same fix
`test_phase7_variations.py` shows).

## 5. `_bundle/` destination layout unchanged

```
$ ls quality_playbook_cli/_bundle/
  SKILL.md  quality_gate.py  skill-template.gitignore
  ai_context/TOOLKIT.md  references/  phase_prompts/  agents/  bin/

$ ls quality_playbook_cli/_bundle/bin/
  __init__.py _purpose.py archive_lib.py benchmark_lib.py
  citation_verifier.py council_config.py council_semantic_check.py
  install_skill.py migrate_v1_5_0_layout.py qpb_config.py
  qpb_phase.py qpb_validate.py quality_playbook.py
  reference_docs_ingest.py role_map.py run_state_lib.py
  validate_phase_artifacts.py
```

Flat bundle layout preserved bit-for-bit. The pip wheel /
npm tarball install destinations are FROZEN by the published
v1.5.8 contract.

## 6. `marketplace.json` fields

```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "quality-playbook",
  "description": "Find the bugs that AI code review misses…",
  "owner": { "name": "Andrew Stellman", "email": "andrew@stellman.com" },
  "plugins": [
    { "name": "quality-playbook", "source": ".", "category": "productivity" }
  ]
}
```

Valid JSON. `skills` field ABSENT. `strict` field ABSENT.
`.claude-plugin/plugin.json` is present (NEW file, version `1.5.8`,
matches `pyproject.toml`). Confirmed compliant with the charter.

## 7. Finding narratives

### FIX-REQUIRED-1: Five `bin/tests/*.py` files still import `quality_gate` via the legacy `.github/skills/quality_gate/` sys.path insert (defensive-sweep miss)

**Files & lines:**
- `bin/tests/test_citation_stale.py:37-40`
- `bin/tests/test_cardinality_gate.py:18-21`
- `bin/tests/test_phase3_prompt_worked_example.py:27-30`
- `bin/tests/test_phase6_integration.py:36-39`
- `bin/tests/test_quality_gate_language_detection.py:54-57`

**Symptom:** Each file does
`sys.path.insert(0, str(<repo>/.github/skills/quality_gate))` then
`import quality_gate`. Post-208 the `quality_gate.py` file lives at
`skills/quality-playbook/scripts/quality_gate.py`; the legacy path
holds only `__init__.py` + `tests/`. Running any of the five files
in isolation fails with `ModuleNotFoundError: No module named
'quality_gate'`. Verified empirically:

```
$ python3 -m unittest bin.tests.test_phase6_integration
ImportError: Failed to import test module: test_phase6_integration
ModuleNotFoundError: No module named 'quality_gate'
FAILED (errors=1)
```

The full `unittest discover` ostensibly passes because an
alphabetically earlier test (e.g. `test_archive_lib.py` /
`test_doc_gathering_skill_integration_132.py:40` which adds the
NEW `skills/quality-playbook/scripts/` to sys.path) primes
`sys.modules['quality_gate']` before the five suspects load. This
masks the breakage during a full-suite run but blows up any
developer doing focused single-file TDD — exactly the workflow
`bin/tests/` are designed for. Build agent's claimed "3219 tests, 1
failure" full-suite number is technically true but conceals five
broken isolation-mode imports.

**Why this is a defensive-sweep miss:** `ai_context/DEVELOPMENT_PROCESS.md`
codified (after 207 C-NIT2) the Defensive-sweep Council charter for
content-fix instructions: grep ALL bundled-source consumers for the
old paths. The build agent updated `test_phase7_variations.py:36-42`
to point at the new `skills/quality-playbook/scripts/` location (the
correct fix pattern is right there) but missed five neighbours that
use the identical legacy-path-insert idiom. The grep was incomplete.

**Suggested patch (per file):** replace
```python
GATE_DIR = QPB_ROOT / ".github" / "skills" / "quality_gate"
```
with
```python
GATE_DIR = QPB_ROOT / "skills" / "quality-playbook" / "scripts"
```
mirroring `test_phase7_variations.py`. Optionally update the
neighbouring code comments that say "lives inside
.github/skills/quality_gate/" (verified at
`test_cardinality_gate.py:16`).

**Verification after patch:** each of the five files runs cleanly
in isolation via `python3 -m unittest bin.tests.<file_stem>` →
zero errors, zero failures.

## 8. Optional NITs

- **NIT-1 (informational, low):** `bin/tests/test_cardinality_gate.py:16`
  has a code-comment saying "the gate module path — it lives inside
  .github/skills/quality_gate/." This is stale prose post-208 but not
  load-bearing; folded into the FIX-REQUIRED-1 patch makes sense.
- **NIT-2 (informational, low):** `bin/tests/test_archive_lib.py:624`,
  `test_legacy_project_type_consistency.py:3,190`, `test_npm_channel_e2e_089v.py:30`,
  `test_pip_channel_package_parity_089u.py:214`, etc. carry similar
  legacy-path prose in comments / fixture-string-literals (not
  runtime path constants). These are documentary, not executable —
  no correctness risk, but a follow-up sweep to canonicalize the
  prose would be hygienic. Out of scope for 208 if any case-by-case
  judgment needed.
- **NIT-3 (informational):** `bin/install_skill.py` shim and
  `bin/__init__.py` path-extension pattern are elegant — single-file
  solutions where 16+ per-module shims would have been the obvious
  but uglier alternative. No action.
- **NIT-4 (informational):** `_quality_gate_source()` in
  `install_skill.py:274-293` defensively keeps the pre-208
  `.github/skills/quality_gate/quality_gate.py` fallback for
  half-restored clones. Good belt-and-suspenders; the comment
  explicitly documents the intent (improves error messages for
  partial clones rather than enabling the legacy layout).

## 9. Final block

```
VERDICT: FIX-REQUIRED
```

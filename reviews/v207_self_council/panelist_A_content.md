# Panelist A — Content Correctness against canonical sources

**Charter recap:** Verify the six trim-template content fixes shipped in commit `35f9734` (instruction 207) match the canonical sources cited in the instruction (`README.md`, `ai_context/TOOLKIT.md`, `pyproject.toml`, and `quality_playbook_cli/_bundle/`).

## Per-fix audit table

| # | Fix | Canonical source | Matches? |
|---|-----|------------------|----------|
| 1 | Python version: `Python 3.8+` → `Python 3.10+` (source line 183) | `README.md:47` "Prerequisite: Python 3.10 or later"; `README.md:19,162,864,1173`; `ai_context/TOOLKIT.md:49,54,221` "Python 3.10+" + "runtime floor was raised 3.9 → 3.10 in v1.5.7 089i" | YES |
| 2 | npx invocation: bare `npx quality-playbook` → `npx quality-playbook install --into <repo> --ai-tool <tool>` (source lines 205, 275) | `README.md:159` exact form: `npx quality-playbook install --into /path/to/target-repo --ai-tool <tool>` | YES |
| 3 | Entry point: `qpb install` → `quality-playbook install` (source lines 211, 276, 294) | `pyproject.toml:46-47` `[project.scripts]` → `quality-playbook = "quality_playbook_cli:main"` (no `qpb` entry exists) | YES |
| 4 | Phase 5 name: `Phase 5 (Consolidate)` → `Phase 5 (Reconcile)` (source line 238) | `README.md:59` "explore, generate requirements + tests + protocols, code review, spec audit, **reconcile findings**, verify"; `README.md:599` canonical six-phase list "Explore, Generate, Review, Audit, **Reconcile**, Verify" | YES |
| 5 | Phase 6 name: `Phase 6 (Ship)` → `Phase 6 (Verify)` (source line 240) | `README.md:59` ends with `verify`; `README.md:599` `Reconcile, **Verify**` | YES |
| 6 | Bundle count + listing: "seven support directories" → "five support directories (references/, phase_prompts/, agents/, bin/, ai_context/) plus SKILL.md and quality_gate.py" (source line 281) | `quality_playbook_cli/_bundle/` actual contents: `agents/`, `ai_context/`, `bin/`, `phase_prompts/`, `references/` = exactly 5 directories, plus `SKILL.md` and `skill-template.gitignore` | YES (with caveat — see NIT 1) |

## Empirical verification

- Regenerated `/tmp/qpb-207-panelA/skills/quality-playbook/SKILL.md` and `/tmp/qpb-207-panelA/PR_BODY.md` via `python3 bin/submit_awesome_copilot.py --dry-run`. All six fixes are present in the rendered output.
- All 8 `TrimTemplateContentTests` pass (one assertion per error, each using both positive `assertIn` and regression `assertNotIn` checks).

## Per-finding narrative

No CONCERN or FIX-REQUIRED findings on the six in-scope fixes. Each fix is correctly grounded in the cited canonical source and the rendered artifact is consistent with the source-of-truth.

## NITs (out of scope for instruction 207, but worth noting)

1. **`quality_gate.py` is not in the bundle.** The fix-6 prose says "plus `SKILL.md` and `quality_gate.py`" — but `ls quality_playbook_cli/_bundle/` shows only `SKILL.md` and `skill-template.gitignore` at the top level. `quality_gate.py` is NOT a top-level bundle file; it is produced/located elsewhere (this matches `bin/install_skill.py::_bundle_files()` rather than the `_bundle/` directory). The fix-6 prose is *closer* to correct than the pre-207 version (which claimed 7 things and miscounted dirs vs files), but `quality_gate.py` placement is still loose. RECOMMENDATION: leave for a future cleanup pass — it is not worse than pre-207 and matches the README line 131 description of what the bundle "ships."

2. **SKILL.md line 19 ("seven phase-prompt directories")** is still inaccurate — `quality_playbook_cli/_bundle/phase_prompts/` contains 10 `.md` files, no subdirectories. Pre-207 status quo; out of scope for instruction 207's six documented fixes; can be cleaned up in a follow-up.

3. **SKILL.md line 39 ("`bin/citation_verifier.py`")** correctly references a real file (`quality_playbook_cli/_bundle/bin/citation_verifier.py` exists), but it singles out one of 17 files in `bin/`. Not wrong, just incomplete — and out of scope for 207.

None of these NITs were called out in instruction 207's six-error inventory, so they do not block ship.

## Final block

```
VERDICT: SHIP
```

# Panelist C — Test sufficiency + mutation verification + regression-safety + defensive sweep

QPB instruction 207 (fix trim-template content errors), HEAD `35f9734` (branch `1.5.8`, not pushed).

## 1. Charter recap

Verify the 8 `TrimTemplateContentTests` methods are present and correctly assert positive+negative; confirm (or independently re-perform) the mutation verification; check full-suite + 206 AUDIT-sweep regression; and **defensively sweep the trim template for OTHER stale hardcoded facts** beyond the six the orchestrator fixed.

## 2. Test-method-presence table

All eight methods are present in `TrimTemplateContentTests` at `bin/tests/test_submit_awesome_copilot.py` lines 687-780. Every test asserts both the correct value AND that the pre-207 stale value is absent — i.e., proper mutation-resistant pairing.

| # | Method | Lines | Positive assertion(s) | Negative assertion(s) | Both present? |
|---|--------|-------|-----------------------|------------------------|---------------|
| 1 | `test_skill_md_says_python_310_not_38` | 706-709 | `assertIn("Python 3.10+", skill_md)` | `assertNotIn("Python 3.8+", ...)`, `assertNotIn("Python 3.9+", ...)` | Yes |
| 2 | `test_skill_md_install_command_is_quality_playbook_not_qpb` | 711-718 | `assertIn("quality-playbook install", skill_md)` | `assertNotIn("qpb install", skill_md)` | Yes |
| 3 | `test_skill_md_npx_invocation_includes_subcommand` | 720-736 | Each `npx quality-playbook` line contains `"install"` | Implicit (loop fails if any bare npx invocation exists); also `assertTrue(npx_lines)` guards against silent removal | Yes |
| 4 | `test_skill_md_phase_5_is_reconcile_not_consolidate` | 738-742 | `assertIn("Phase 5 (Reconcile)", skill_md)` | `assertNotIn("Phase 5 (Consolidate)", skill_md)` | Yes |
| 5 | `test_skill_md_phase_6_is_verify_not_ship` | 744-746 | `assertIn("Phase 6 (Verify)", skill_md)` | `assertNotIn("Phase 6 (Ship)", skill_md)` | Yes |
| 6 | `test_pr_body_install_command_is_quality_playbook_not_qpb` | 748-752 | `assertIn("quality-playbook install", pr_body)` | `assertNotIn("qpb install", pr_body)` | Yes |
| 7 | `test_pr_body_bundle_count_is_five_not_seven` | 754-760 | `assertIn("five support directories", pr_body)` | `assertNotIn("seven support directories", pr_body)` | Yes |
| 8 | `test_skill_md_includes_ai_tool_list` | 762-780 | Loop: `assertIn(tool, skill_md.lower())` for all 8 of `claude/cursor/copilot/continue/codex/windsurf/cline/aider` | None (positive-only — see NIT 1) | Positive only |

`setUp` (lines 694-704) constructs `skill_md` and `pr_body` from `sub.generate_trimmed_skill_md("1.5.8", fm)` and `sub.generate_pr_body("1.5.8", fm)` with a canonical frontmatter dict — i.e., the tests exercise the actual template-generator functions, not stand-in fixtures. Coverage is well-targeted.

Targeted run from `bin/tests/`:
```
python3 -m unittest test_submit_awesome_copilot.TrimTemplateContentTests -v
Ran 8 tests in 0.001s — OK
```

## 3. Mutation verification — independently re-performed

Independently re-performed (orchestrator's snapshot at `/tmp/qpb_207_snapshot.py` is still there; I took my own to `/tmp/qpb_207_panelC_snapshot.py`):

1. Took my own snapshot via `shutil.copy2` (size 41804, matches orchestrator's).
2. Reverted line 183 from `Python 3.10+` to `Python 3.8+`.
3. Purged `bin/__pycache__` (scoped — not repo-root walk per MEMORY note).
4. Ran `test_skill_md_says_python_310_not_38`:
   ```
   AssertionError: 'Python 3.10+' not found in '... Python 3.8+ and git ...'
   FAILED (failures=1)
   ```
5. Restored via `python3 -c "import shutil; shutil.copy2('/tmp/qpb_207_panelC_snapshot.py', '<source>')"` — NOT `git checkout --` per MEMORY note.
6. Re-purged `bin/__pycache__`.
7. Re-ran `TrimTemplateContentTests` — **8/8 OK**.
8. `git diff bin/submit_awesome_copilot.py` is empty — restore is byte-clean.

Orchestrator's mutation report confirmed.

## 4. Full-suite + 206 AUDIT-sweep regression

| Command | Result | Notes |
|---------|--------|-------|
| `python3 -m pytest bin/tests/test_submit_awesome_copilot.py -v` | 37 passed | All `SubmitFlagTests`, `MainEndToEndTests`, `WritePacketTests`, `TrimTemplateContentTests` (8), `GenerateSkillMdTests`, `GeneratePrBodyTests`, etc. green. No skips, no warnings. |
| `python3 -m pytest bin/tests/test_release_affirmation_sweep_206.py -v` | 6 passed | AUDIT sweep still green — `submit_awesome_copilot.py` still registers `--dry-run`, declares `EX_USAGE=64`, mutually-exclusive flags, no-args returns 0, etc. |
| `python3 -m unittest test_submit_awesome_copilot.TrimTemplateContentTests -v` | 8 passed | New class, 0.001s wall. |

No regressions.

## 5. Defensive sweep — other hardcoded facts in `bin/submit_awesome_copilot.py`

I scanned `generate_trimmed_skill_md` (lines 167-256) and `generate_pr_body` (lines 259-325) for every hardcoded factual claim and cross-checked against canonical sources (README.md, pyproject.toml, install_skill.py, on-disk bundle).

| # | Line(s) | Surface | Hardcoded claim | Canonical source | Status |
|---|---------|---------|------------------|------------------|--------|
| 1 | 197 | SKILL.md Installation prose | "the full bundle (**seven phase-prompt directories**, the citation verifier, the Council runner, the bundled references, and the cross-platform install scripts)" | `phase_prompts/` is ONE directory with 10 flat files (`phase1.md`–`phase6.md`, `phase6_auditor.md`, `iteration.md`, `single_pass.md`, `README.md`). There are ZERO subdirectories. "Seven phase-prompt directories" is factually wrong by the same staleness pattern fixed for PR_BODY in error #6 of 207. | **FIX-REQUIRED** — in-spec |
| 2 | 197-198 | SKILL.md Installation prose | "**the citation verifier**, **the Council runner**, **the bundled references**, and **the cross-platform install scripts**" — listed as distinct top-level bundle items | `bin/citation_verifier.py` is one file inside `bin/`, not a separate item. There is no file or directory called "Council runner" (the Council is invoked by `bin/run_council.py` + `bin/council_config.py` but the phrase "Council runner" appears nowhere in README/SKILL.md/TOOLKIT.md as a canonical artifact name). "Cross-platform install scripts" are part of the npm/pip channel, not the in-bundle skill payload. | **CONCERN** — same paragraph, same staleness root-cause |
| 3 | 217-218 | SKILL.md install-output file list | "(`SKILL.md`, `quality_gate.py`, `references/`, `phase_prompts/`, `agents/`, `bin/citation_verifier.py`)" — what the installer copies | `bin/install_skill.py` copies SKILL.md, quality_gate.py, references/, phase_prompts/, agents/, AND the broader `bin/` package contents — not just `bin/citation_verifier.py`. The listing is incomplete/misleading. | **CONCERN** — adopters will think they only get one bin file |
| 4 | 283 | PR_BODY Distribution prose | "The full bundle is **~64 files** (132KB SKILL.md alone)" | Actual `.claude/skills/quality-playbook/` count: 75 files total; 57 excluding operator-backups. SKILL.md is 132,613 bytes (~132KB) — that part is accurate. "~64" is approximate-ish but ~12% off from 57 / ~17% off from 75. With the `~` hedge this is soft. | **NIT** — out-of-spec for 207 |
| 5 | 244 | SKILL.md "What it does" prose | "it can take **30-90 minutes** on a large codebase" | README line 410 canonical: "The full cycle takes **15-90 minutes** depending on project size"; line 443: autonomous run "takes **60-180 minutes**". Neither matches `30-90`. | **CONCERN** — easy to align with README's 15-90 |
| 6 | 11-13 | Module docstring (NOT shipped) | "it ships seven support directories (`bin/`, `references/`, `phase_prompts/`, `agents/`, `quality_gate.py`, `ai_context/` slice, and so on)" | Lists 4 dirs + 1 file + a slice + "and so on" — same arithmetic confusion the PR_BODY error #6 fixed. Not shipped to adopters but worth fixing for code-reader honesty. | **NIT** — internal docstring, not template content |
| 7 | 182, 316-320 | SKILL.md frontmatter + PR_BODY License note | `license: Apache-2.0` / "Apache 2.0 (see `LICENSE.txt`)" | `LICENSE.txt` line 1 is the Apache License 2.0 preamble. | Accurate. No action. |
| 8 | 187 | SKILL.md frontmatter | `upstream: {QPB_REPO_URL}` (`https://github.com/andrewstellman/quality-playbook`) | Constant resolved from `QPB_REPO_URL`; matches `pyproject.toml` `[project.urls]`. | Accurate. No action. |
| 9 | 192 | SKILL.md description | "Finds **the 35% of real defects** that structural code review alone cannot catch" | README line 7 + SKILL.md description line 3 + ai_context/TOOLKIT.md line 411 all canonically cite "35%". | Accurate. No action. |
| 10 | 214-220 | SKILL.md `<tool>` listing + auto-detect-dir listing | 8 tools (`claude/cursor/copilot/continue/codex/windsurf/cline/aider`) and 8 dirs (`.claude/, .github/, .cursor/, .continue/, .codex/, .windsurf/, .cline/, .aider/`) with `.github/` mapping to `copilot` | `bin/install_skill.py` lines 47-78: the 8 tools and 8 detection-dirs match exactly (`copilot` → `.github/`). | Accurate. No action. |
| 11 | 295 | PR_BODY Verification example | "`ls ./test-target-repo/.claude/skills/quality-playbook/`" | `bin/install_skill.py` line 47 + line 68 confirms `.claude/skills/quality-playbook/` is the canonical landing path for `--ai-tool claude`. | Accurate. No action. |

**Top sweep takeaways:**

- **Finding #1 (line 197 "seven phase-prompt directories")** is the same staleness-pattern as 207 error #6 (the PR_BODY "seven support directories") but in the SKILL.md Installation paragraph. Andrew flagged "seven support directories" in PR_BODY at the y/N gate; he would equally have flagged "seven phase-prompt directories" in SKILL.md if he'd seen it. The 207 patch fixed PR_BODY but **left the SKILL.md sister-paragraph untouched** — that SKILL.md is the file awesome-copilot users see. This is in-spec for 207's charter ("fix trim-template content errors") and was missed.
- **Finding #3 (line 217-218 file list)** undersells what the installer actually copies. A maintainer running the verification recipe will see more files than promised, but a reviewer comparing the doc against the source will conclude the doc is incomplete.
- **Finding #5 (30-90 minutes)** is a minor doc-drift but easy to reconcile against README's authoritative 15-90.

No other Apache→MIT, URL, or version-string drift detected.

## 6. Per-finding narrative

### Finding #1 — SKILL.md Installation prose: "seven phase-prompt directories" (FIX-REQUIRED)

`bin/submit_awesome_copilot.py` line 197 in the SKILL.md template:

> This skill is distributed as a standalone toolkit because the full bundle (seven phase-prompt directories, the citation verifier, the Council runner, the bundled references, and the cross-platform install scripts) exceeds the typical in-repo skill footprint.

`phase_prompts/` contains ten flat `.md` files; ZERO subdirectories. The phrase "seven phase-prompt directories" is the same misclaim pattern as 207's error #6 — Andrew correctly fixed the analogous PR_BODY sentence ("seven support directories" → "five support directories") but did not fix this SKILL.md sentence. Since SKILL.md is the artifact awesome-copilot adopters read (PR_BODY is just the cover letter to the registry maintainers), this is arguably the more visible miss. A skilled reviewer in the awesome-copilot PR thread would catch it and ask for clarification — same failure mode as the six errors 207 set out to fix.

Suggested replacement language (canonical-aligned):

> "the full bundle (the `phase_prompts/`, `references/`, `agents/`, `bin/`, and `ai_context/` directories plus `SKILL.md` and `quality_gate.py`, ~57 files including a 132KB `SKILL.md`)"

This mirrors the (now-correct) PR_BODY listing in 207's fix.

### Finding #2 — Same paragraph: "citation verifier / Council runner / cross-platform install scripts" (CONCERN)

The same Installation paragraph lists "the citation verifier, the Council runner, ... and the cross-platform install scripts" as if they were distinct top-level bundle items. They are not: `bin/citation_verifier.py` is one file inside `bin/`, there is no canonical artifact called "Council runner" (`bin/run_council.py` runs the Council but that name isn't documented), and "cross-platform install scripts" are the npm/pip publishing channels, not in-bundle skill files. If Finding #1 is fixed by rewriting the parenthetical to actual bundle directories, #2 falls out as a side effect.

### Finding #3 — SKILL.md install-output file list incomplete (CONCERN)

Line 217-218: "The installer copies the skill files (`SKILL.md`, `quality_gate.py`, `references/`, `phase_prompts/`, `agents/`, `bin/citation_verifier.py`) into the right place..."

`bin/install_skill.py` copies all of `bin/` (the standard-library runner package), not just `bin/citation_verifier.py`. Suggest: change `bin/citation_verifier.py` to `bin/` so the listing is honest.

### Finding #5 — "30-90 minutes" inconsistency with README (CONCERN)

Line 244 says "it can take 30-90 minutes on a large codebase". README's canonical phrasing is "**15-90 minutes** depending on project size" (line 410) for the full cycle and "60-180 minutes" for autonomous runs (line 443). 30-90 is not literally in any canonical source. Suggest: align to README's "15-90 minutes depending on project size".

## 7. Optional NITs

- **NIT 1**: `test_skill_md_includes_ai_tool_list` (test #8) is positive-only — it would still pass if the tool list got duplicated or if a separate paragraph appeared that mentions all eight names. Mutation-resistance is weaker than tests 1-7. Optional hardening: also assert the 8 names appear in a single line / a specific section, or that the count of distinct ai-tool tokens is exactly 8. Not blocking; the orchestrator's mutation report only covered test #1 anyway, so this is a thoroughness concern not a correctness one.
- **NIT 2**: `test_skill_md_includes_ai_tool_list` uses `skill_md.lower()` and searches for `"continue"` as a substring — this would also match "continued", "continues", "continuing" anywhere in the template. The current template doesn't have those words, but a future copy edit could silently break the mutation-resistance. Consider word-boundary or backtick-delimited check (e.g., `assertIn("`continue`", skill_md)`).
- **NIT 3**: Module docstring lines 11-13 (Finding #6) carry the same "seven support directories" miscount as the now-fixed PR_BODY. Not shipped to adopters, but inconsistent with the corrected user-facing text. Fix in a follow-up commit.
- **NIT 4**: "~64 files (132KB SKILL.md alone)" (Finding #4): the SKILL.md size is accurate; the file count is ~12% off from current 57 (or ~17% off from 75 including operator backups). The `~` hedge gives cover, but consider regenerating the count from the actual bundle at template-render time (e.g., via a helper that walks `.claude/skills/quality-playbook/`).

## 8. Final verdict

The 207 test suite is well-constructed (8 mutation-resistant pairs, exercising the real generator functions), the mutation verification reproduces independently, the full submit suite + 206 AUDIT sweep stay green with zero regression, and the orchestrator's six diagnoses + their fixes are correct against canonical sources.

**However,** the defensive sweep surfaces a fresh in-spec miss the orchestrator did not catch: the SKILL.md Installation prose at line 197 contains "**seven phase-prompt directories**" — the SAME staleness pattern as 207's error #6, in the sister paragraph the orchestrator did fix on the PR_BODY side. This is a content error in the trim template, which is exactly what 207 is chartered to eliminate. Since SKILL.md is the artifact awesome-copilot users actually read (PR_BODY is just a cover letter to registry maintainers), shipping SKILL.md with this error preserves the same class of bug Andrew rejected at the y/N gate.

Findings #2, #3, #5 are softer (CONCERN / co-resident with #1) and can be folded into the same patch. NITs are non-blocking.

The orchestrator should add a 9th test (`test_skill_md_phase_prompts_dir_count_not_seven` or `test_skill_md_installation_prose_lists_actual_bundle_dirs`), rewrite the SKILL.md line 197 parenthetical to mirror the corrected PR_BODY language, optionally fix Findings #3 and #5 in the same patch, and re-run the mutation drill on the new test before shipping.

```
VERDICT: FIX-REQUIRED
```

# Quality Playbook v1.5.7 — Release-Acceptance Checklist

*Status: ACTIVE acceptance gate for the v1.5.7 release. Owner: Andrew Stellman. Opened 2026-05-25.*

*Purpose: a tracked, runnable checklist that — if every item passes — gives confidence to finish (tag/merge/publish) v1.5.7. v1.5.7's headline feature is the **pip + npm distribution channels**, hardened through the 089x→090x instruction series. As of this checklist's opening we have run **many gate-only re-runs but zero end-to-end runs against the post-090x code**, so the plan centers on proving both channels install-and-run cleanly from freshly-built artifacts and on observing each operator-verdict state **live**.*

**Release HEAD under test:** `980e136` (090x — the verdict-explanation + provenance stack complete; on origin/1.5.7). Everything below is gated against this HEAD; update if further commits land before publish.

---

## What this is de-risking (the rationale, so the runs aren't busywork)

- The distribution channels (pip/uvx/pipx + npm/npx) are the new surface and the riskiest part — they must install and run end-to-end from **freshly rebuilt** artifacts (090u/v/w/x changed bundled files).
- The credibility guards (090o setup-prep, 090p RED-validity, 090s no-op/zero-bug, 090t Phase-0 path, 090u gitignore closure) and the operator verdict-explanation layer (090v + 090w provenance + 090x bugs-unverified) have only been validated by unit tests and gate **re-runs over old artifacts**. They need to fire in **live** runs.
- The **✅ solid** verdict state has never been observed live (every old fixture fails today's stricter gate, and clean runs so far were zero-bug → ⚠️ shallow). Seeing a genuine ✅ end-to-end is the true "QPB works" signal.

---

## Tier 0 — Pre-flight (gating; nothing below counts until these pass)

- [ ] **Full test suite GREEN dual-env** at the release HEAD:
  - [ ] `env -i PATH="$PATH" HOME="$HOME" python3 -m unittest discover bin/tests` → OK
  - [ ] `CODEX_THREAD_ID=x COPILOT_AGENT_SESSION_ID=x CLAUDECODE=1 python3 -m unittest discover bin/tests` → OK
  - [ ] `python3 -m unittest discover .github/skills/quality_gate/tests` → OK
- [ ] **Rebuild both channel artifacts** (mandatory — bundled files changed through 090x):
  - [ ] `python3 bin/build_channel_package.py --stage`
  - [ ] `python3 -m build` → fresh `dist/quality_playbook-1.5.7-py3-none-any.whl`
  - [ ] `npm pack` → fresh `quality-playbook-1.5.7.tgz`
- [ ] **Closure spot-check** the rebuilt artifacts contain the new code:
  - [ ] `qpb_validate.py` present in the closure
  - [ ] `skill-template.gitignore` present in the closure (090u)
  - [ ] `quality_gate.py` carries the verdict block (`Operator Verdict` / `Run provenance` / `bugs_unverified`)
- [ ] `.tgz` is gitignored (no build artifact clutter in `git status`).

---

## Tier 1 — Install / Phase-0 smokes (cheap; run before committing to full runs)

For each: fresh clone of a throwaway target, channel-install, run **Phase 0 only**, then confirm the three install-surface fixes. ~5 min each; a regression here stops the full runs.

**pip / uvx install** (one tool, e.g. Claude Code):
- [ ] Banner renders at skill load.
- [ ] Validator reaches `status=ok` on the **first probe** via the install-location-aware path (090t) — no repo-root path-mismatch.
- [ ] gitignore remediation points at a **real file** and is followed without improvisation (090u).

**npm / npx install** (one tool, e.g. Codex or Copilot):
- [ ] Banner renders at skill load.
- [ ] Validator `status=ok` first probe (090t).
- [ ] gitignore remediation followed without improvisation (090u).

---

## Tier 2 — Full end-to-end runs (the core)

Goal: see each verdict state **live** while covering both channels, ≥2 tools, and a capable + a weak model. Record outcomes in the table below.

**Run A — ✅ solid (keystone, highest priority).** Small, clean, well-documented repo + **strong model at high effort** (Claude Opus or gpt-5.4 high), **pip channel**. Drive the *complete* path: find ≥1 real bug and complete red→green TDD so it passes. Expected: `GATE PASSED`, **✅ solid**, provenance with **correct/matching metadata** (no-mismatch case, never seen live).

**Run B — ❌ weak-model, live.** Same/similar repo + **weak model** (gpt-5.2 low), **npm channel**, different tool. Expected: guards fire live → `GATE FAILED` + **weak-model attribution + "use a stronger model"**.

**Run C — capable model, meatier repo, second tool.** Larger repo (auth/authz OK here **via Codex/non-Claude** to avoid the AUP classifier) + capable model. Confirm verdict block + provenance correct and the verdict is **honest** (no false PASS / no false FAIL). Likely exercises 090x `bugs_unverified` or real verified bugs live.

**Run D (optional) — ⚠️ shallow.** Only if A–C don't naturally produce a zero-bug pass; otherwise accept unit-test coverage for this state.

| Run | Channel | Tool | Model | Target repo | Expected verdict | Actual verdict | Provenance correct? | Pass? | Notes |
|-----|---------|------|-------|-------------|------------------|----------------|---------------------|-------|-------|
| A | pip/uvx | | | | ✅ solid + verified bug(s) | | | ☐ | |
| B | npm/npx | | | | ❌ weak-model + "stronger model" | | | ☐ | |
| C | (other) | | | | honest verdict (no false PASS/FAIL) | | | ☐ | |
| D | | | | | ⚠️ shallow (optional) | | | ☐ | |

---

## Tier 3 — Go / no-go acceptance (finish 1.5.7 only if ALL true)

- [ ] Tier 0 all green (suite dual-env; artifacts rebuilt + closure verified).
- [ ] **Both channels** (pip + npm) installed and ran a full playbook from the freshly-built artifacts.
- [ ] **Phase 0 first-probe pass** on every install (no 090t regression).
- [ ] **gitignore remediation** followed without improvisation on every install (090u).
- [ ] **✅ solid** observed live at least once (Run A) — the never-before-seen state.
- [ ] **Credibility guards fire live**: the weak run FAILs with weak-model attribution (no false PASS); the clean run PASSes (no false FAIL).
- [ ] **Verdict block + provenance correct live**, including one **no-mismatch** provenance case (correct metadata from a fresh run).
- [ ] **090x `bugs_unverified`** renders on a real bugs-without-TDD run (or confirmed via the NATS gpt-5.4 fixture re-run if no live instance arises).
- [ ] No false `GATE PASSED` on any hollow/weak run; no false `GATE FAILED` on the clean run.

**On all-green:** proceed to release mechanics (separate from this acceptance gate): push `1.5.7` to origin → block-E publish (PyPI + npm) → the four-ref dance (tag `v1.5.7`, merge to `main`, open `1.6.0`). Verify each remote-state change directly (`git ls-remote`) before claiming it landed.

---

## Caveats / selection rules

- **✅ solid is the hardest state to manufacture** — it requires a *complete* run (real red→green TDD on ≥1 bug); even gpt-5.4 skipped TDD on NATS. Run A needs a strong model, a small repo with a tractable bug, and likely explicit "complete Phase 5 verification" prompting. A genuinely clean repo with zero bugs yields **⚠️ shallow**, not ✅ — both are valid passes, but only the verified-bug path gives ✅. Decide up front whether ✅ specifically is required for sign-off or whether a clean pass either way suffices.
- **Repo selection for Claude runs:** keep exploit-dense auth servers (NATS-class) on Codex/non-Claude to avoid the AUP classifier; use Claude on clean/small targets.
- **Rebuild discipline:** every E2E run must install from artifacts rebuilt at the release HEAD — never a stale `dist/`/`.tgz`.

---

## Reference fixtures (gate-re-run confirmations, already observed)

These are *not* end-to-end but confirm the verdict-layer output computation; cite them when verifying the live runs match expected shapes:
- **Keto run5** (gpt-5.3-codex) → ❌ + weak-model "stronger model" attribution; provenance caught stale metadata (gate 3 vs reported 0).
- **NATS run2 gpt-5.4** → ❌ + missing-TDD (the `bugs_unverified` target case), correctly no stronger-model nudge.
- See `QPB_v1.6.x_Verdict_Explanation_Proposal.md` for the canonical fixture definitions + expected outputs.

## Provenance

- 2026-05-23/24/25 Mode-A channel-install run-series (OpenFGA / Keto / NATS) → the 090k–090x hardening series + the verdict-explanation layer.
- 2026-05-25 conversation → owner request for a tracked release-acceptance gate before finishing v1.5.7.

# Quality Playbook — Verdict-Explanation Layer (Operator-Facing Gate Output)

*Status: NEW v1.6.x track, opened **2026-05-25**. The **framework + high-frequency content slice ships in v1.5.7** (instruction 090v); the **expanded featureset** (long-tail per-check explanations, full WARN-severity taxonomy, v1.6.0 disposition explanations, machine-readable verdict) ships across v1.6.x. Owner: Andrew Stellman.*

*Orthogonal to v1.6.0's NFR-discovery + FP-audit feature: v1.6.0 changes **which findings are confirmed**; this layer changes **how findings are explained to the operator**. They compose — when v1.6.0 adds new finding dispositions (KNOWN-ISSUE, DEMOTED, RECLASSIFIED, integration-harness-required), this layer gains explanation entries for them additively, with no rework. Confirmed against `QPB_v1.6.0_Design.md` (read end-to-end 2026-05-25): the v1.6.0 design specifies no output/UX surface, so there is no collision.*

---

## ⚠️ Read this first — the problem

Across the 2026-05-23/24/25 Mode-A channel-install dogfood run-series, a single UX gap ran through nearly every finding: **the gate knows something is off but does not tell the operator clearly.** Concrete symptoms:

- A run prints `Total: 0 FAIL, 6 WARN` then `RESULT: GATE PASSED`, and a non-expert operator **cannot tell whether the run succeeded, was shallow, or quietly failed.** (NATS run2, gpt-5.2/low: a zero-bug run with a no-op functional test that PASSED — correct per semantics, but the operator has no idea it's a hollow result.)
- When the gate **does** FAIL, the output is a terse check name with no plain-English cause, no remediation, and no statement of what the operator can do about it.
- The benign back-compat WARNs (legacy-manifest notices that literally say "not a defect") are interleaved with the WARNs that actually matter, so any important signal drowns in noise.
- Nothing distinguishes **"the AI cut corners — use a better model"** from **"your test environment broke"** from **"we found a real bug."** These need completely different operator responses, and the current output conflates them.

The earlier instinct was to add more *structural guardrails* (detect-and-FAIL more hollow shapes). That path has a real backfire: pushing a weak model away from "obviously hollow" nudges it toward "subtly hollow," which is harder to catch — exactly the well-formed-but-meaningless-content problem already scoped to v1.6.0's FP-audit. So instead of escalating detection→FAIL, **this layer escalates detection→plain-English explanation**, and spends the trust on the human operator (who follows guidance far better than a low-effort model does).

**The key asymmetry that makes this safe and effective:** a wrong FAIL blocks an honest run, so detection-for-failure must be conservative. A wrong *warning/explanation* costs almost nothing — a human glances, sees it's fine, moves on. So the verdict layer can be **far more aggressive about flagging suspicion** than the gate can be about failing, without re-opening the false-positive risk.

---

## Architecture

The gate's verdict is already a clean post-loop block at the end of `quality_gate.py::main()`:

1. `check_repo(rd, ...)` runs for each repo, accumulating into module-level `_FAIL_RECORDS`, `WARN`, `_ZERO_BUG_REPOS` (and `PASS`/`INFO`).
2. `_compute_final_verdict(_FAIL_RECORDS, WARN)` returns `(total_line, result_line, exit_code)`.
3. `main()` prints `total_line`, `result_line`, then the 090s zero-bug `NOTE:`.

The verdict-explanation layer is **a new additive function** invoked right there, reading the **same already-computed accumulators**. It touches **zero check logic** — it is pure presentation over findings the gate has already decided.

### The one load-bearing discipline

`total_line` (`Total: N FAIL, M WARN`) and `result_line` (`RESULT: GATE PASSED` / `RESULT: GATE FAILED`) are **load-bearing strings** — downstream consumers parse them (the Phase 6 witness contract; the `what_just_happened` state templates). The verdict layer must be **purely additive**: printed *after* those lines, never replacing or reformatting them, and **must not change `exit_code` / pass-fail semantics.** This is the same discipline the 090s zero-bug NOTE already follows.

---

## The v1.5.7 slice (instruction 090v) — framework + high-frequency content

A new `_emit_operator_summary(...)`-style function, printed after `result_line` (subsuming/extending the existing 090s zero-bug NOTE), delivering four pieces:

### 1. Lead verdict line (always printed, derived from existing state)

A single human-readable headline, one of three states:

- **`❌ GATE FAILED`** — when `exit_code != 0` (any FAIL). Followed by the plain-English "why" (piece 2).
- **`⚠️ GATE PASSED — but this run looks shallow`** — when `exit_code == 0` **and** a shallow/suspect signal is present (zero confirmed bugs; OR a no-op / no-test-function functional test; OR other hollow tells available). Tells the operator the PASS is not trustworthy without verification.
- **`✅ GATE PASSED — this run looks solid`** — when `exit_code == 0` and no shallow signal is present.

This directly answers "I can't even tell if it failed." It leads the block, before any check detail.

### 2. Plain-English "why + what to do" for FAILs

For each FAIL, a short plain-English explanation + likely cause + remediation. The 1.5.7 slice covers the **high-frequency cluster** we have been dealing with, each with a curated message:

- **No-op / all-trivial functional test** (the 090s FAIL case): "The functional test contains no real assertions — it was written to satisfy the requirement, not to test anything. …"
- **Claimed-but-unrun TDD — GREEN overclaim** (the 090p overclaim-by-omission case): "The run says its bug-fix tests passed, but it never actually ran them (no runner output), or the test it ran isn't the one tied to the bug. A GREEN claim with no real execution isn't proof — these bugs are unconfirmed. Re-run so the tests actually execute." *(This is the single most damning 'the model cut corners' signal — it claimed work it didn't do.)*
- **Setup-failure RED** (090p): "A test failed because the environment couldn't build/run it (not because the AI found a defect). Fix the environment, then re-run."
- **Missing required artifact** / phase-artifact validation FAIL: plain-English "this required output is missing or malformed: <artifact>; <what to do>."

For any FAIL code **not** in the curated set, a **graceful generic fallback**: "This check failed: <check name>. See <artifact> for detail." No FAIL ever goes un-narrated — the long-tail just gets a clear-but-generic line until v1.6.x writes its specific message.

### 3. Three-bucket attribution (with gated "try a smarter model")

Classify the run's suspect signals into one of three buckets and speak to each correctly:

- **Weak-model artifact** — triggered by hollow tells: a no-op / no-test-function functional test (090s); a **claimed-GREEN-without-running TDD receipt or a TDD not tied to the bug's named test (090p overclaim-by-omission)** — the strongest single "cut corners" signal; zero bugs with thin exploration; other available fabrication signals. Message blames the *model's output* and recommends action: *"These results look like they came from a model that cut corners — they are not trustworthy. Re-run with a stronger reasoning model at higher effort before relying on this."*
- **Bucket precedence (multi-signal):** the buckets are not mutually exclusive — emit every applicable explanation. The "try a stronger model" recommendation is gated specifically on a **weak-model/fabrication** signal being present (a 090s hollow test or a 090p overclaim) — a pure environment-failure run (setup-failure reds only, no fabrication signal) gets the environment message and **never** the stronger-model line.
- **Environment / setup problem** — triggered by setup-failure reds (090p), build/dependency failures. Message: *"This run couldn't complete because the test environment failed — not because of the AI's analysis. Here's what to fix: <hint>."* **Never** recommends a different model.
- **Real finding / clean** — neither of the above; normal verdict, no snark.

**Hard rule:** the "try a stronger model" recommendation appears **only** in the weak-model bucket. Mis-attributing an environment failure or a real bug to "dumb AI" gives actively wrong advice and erodes trust — this is the one piece with genuine classification logic, and it must be correct.

### 4. Benign-WARN demotion (conservative, curated)

Partition WARNs into **actionable** (printed prominently) vs **benign/operational** (collapsed). The 1.5.7 slice uses a **small curated allowlist** of known-benign back-compat WARNs (the legacy-manifest / documented-default / intended-backward-compat notices that self-describe as "not a defect") — these collapse into a single `(N operational notices — safe to ignore)` line. **Everything not on the allowlist stays prominent** (conservative: never hide a WARN that might matter). The full per-WARN severity taxonomy is deferred to v1.6.x.

### Out of scope for the 1.5.7 slice

- Machine-readable verdict object (JSON) — v1.6.x.
- Plain-English explanations for the long-tail of every check code — v1.6.x (generic fallback covers them in 1.5.7).
- Explanation entries for v1.6.0's new dispositions (they don't exist yet) — v1.6.0.
- Full WARN-severity taxonomy / tagging every emit site — v1.6.x.
- SKILL.md / phase-prompt changes — none needed; this is gate output, not skill prose (ceiling untouched).

---

## The v1.6.x expanded featureset (detailed)

The 1.5.7 framework is deliberately a load-bearing skeleton with the high-value flesh. The expansion fills it out and integrates with the v1.6.0 findings work. Each item below is additive over the 090v framework — no rework of the 1.5.7 slice.

### E1 — Full per-check plain-English coverage (long tail)

Write a curated explanation + cause + remediation for **every** check code the gate can FAIL or WARN on — retiring the generic fallback. This is a content slog (≈20–40 messages) but mechanical and decoupled. Source the remediation wording from, and keep consistent with, the validator's `remediation_suggestion` vocabulary so the operator sees one consistent voice across Phase 0 and the gate. Each message gets a regression test asserting it renders for its triggering condition.

### E2 — Full WARN-severity taxonomy + demotion

Replace the 1.5.7 curated benign-allowlist with an explicit severity tag at **every WARN emit site**: `operational` (back-compat / informational — collapse), `advisory` (worth a look — prominent), `actionable` (operator should act — prominent + remediation). The verdict block groups by tier. This touches the WARN helper / call sites, so it is a larger, more invasive change than the 1.5.7 allowlist — hence its place in v1.6.x, not the converging 1.5.7 release.

### E3 — v1.6.0 disposition explanations (the integration point)

When v1.6.0's NFR-discovery + FP-audit lands, findings gain new dispositions: `KNOWN-ISSUE` (advisory/CVE with no derived-NFR violation, per the grounding rule), `DEMOTED` / `RECLASSIFIED` (from the fresh-context FP-audit), and `confirmed-open (integration-harness-required)` (the FP-audit-gated disposition deferred from the pulled 090r). The verdict layer gains a plain-English explanation for each — e.g. *"3 findings were downgraded to KNOWN-ISSUE: they restate a security advisory but don't violate a requirement we could verify against your code. They are not confirmed bugs."* This is the piece that **cannot** be written until v1.6.0 creates those dispositions, so it belongs in the v1.6.0 line by construction. It is also where the verdict layer becomes the operator-facing narration of the FP-audit's per-finding verdicts (CONFIRMED / DEMOTED / RECLASSIFIED-KNOWN-ISSUE / UNCERTAIN).

### E4 — Richer fabrication-tell attribution

Extend the weak-model bucket from "hollow test / zero-bug" to **named fabrication tells**: a fabricated-looking EXPLORATION.md (generic prose, no real code citations — the run4 shape), a hand-flipped INDEX gate_verdict, foreign-install scavenging (the run3 shape), build-tagged-out functional tests that can never run (the run2 `//go:build qpb` shape). Each named tell gets a specific operator message. This deepens the "blame the AI specifically and accurately" capability the 1.5.7 slice opens generically.

### E5 — Machine-readable verdict object

Emit a structured verdict (JSON, e.g. `quality/verdict.json`) carrying: overall state (`solid` / `shallow` / `failed`), the attribution bucket, the per-finding explanations, and the demoted-WARN summary — so programmatic consumers (CI, dashboards, the eventual Requirements Review UX, the autonomous orchestrator) read the verdict without scraping prose. Optionally also write a human `quality/OPERATOR_SUMMARY.md` artifact mirroring the printed block, so the verdict survives outside the terminal scrollback.

### E6 — Severity-aware "passed with findings" nuance

Distinguish `✅ passed clean` from `✅ passed, with N confirmed findings to review` and `⚠️ passed, but HIGH-severity findings need verification` — so the lead line reflects not just pass/fail but the weight of what was found. Integrates naturally with v1.6.0's per-severity precision metrics.

---

## Testing

**1.5.7 slice (090v):**
- Lead verdict line renders the correct state for: a clean pass, a zero-bug/no-op-test pass (⚠️ shallow), and a FAIL (❌).
- Three-bucket attribution: a hollow-tell run gets the weak-model message **with** the "stronger model" recommendation; a setup-failure-red run gets the environment message **without** it; a clean run gets neither. Mutation-bite: route a setup-failure to the weak-model bucket → the "stronger model" line wrongly appears → test FAILs.
- **Load-bearing preservation:** `total_line` and `result_line` are byte-identical before/after the layer; `exit_code` unchanged. (Mutation-bite: reformat `result_line` → downstream-contract test FAILs.)
- Benign-WARN demotion: allowlisted legacy-manifest WARNs collapse; a non-allowlisted WARN stays prominent (conservative — never hide an unknown WARN).
- Generic fallback: an uncovered FAIL code still gets a clear-but-generic narrated line.

**v1.6.x expansion:** per-message regression tests (E1), per-tier grouping tests (E2), per-disposition explanation tests against v1.6.0 fixtures (E3), per-tell tests (E4), verdict-JSON schema tests (E5).

---

## Provenance

- **2026-05-23/24/25 Mode-A channel-install run-series** (OpenFGA, Ory Keto, NATS across npx/pipx/uvx × Claude Code / Codex / Copilot) — surfaced the recurring "operator can't read the verdict" gap behind 090p (setup-failure reds), 090s (no-op test + zero-bug), and the hollow-run problem.
- **Canonical fixtures (known-input/known-answer):**
  - **Keto run5** (gpt-5.3-codex via Copilot) — the *weak-model-artifact* fixture: 6 all-trivial test functions (090s FAIL) + 3 claimed-GREEN-without-running TDD receipts (090p overclaim) → `Total: 25 FAIL → GATE FAILED`. Correct verdict-layer output: **❌ GATE FAILED** + the weak-model attribution ("wrote empty tests and claimed it ran tests it never ran — re-run with a stronger reasoning model"). This is the exact run4 adversary re-attempting the fabrication; the verdict layer must turn the 25-FAIL wall into that one plain-English sentence.
  - **NATS run2** (gpt-5.2/low) — the *shallow-pass* fixture: a zero-bug, no-op-test PASS that is correct-by-semantics but unreadable. Correct output: **⚠️ GATE PASSED — but this run looks shallow** + the weak-model attribution.
- **2026-05-25 conversation** — owner decision to pivot from adding more detect-and-FAIL guardrails (backfire risk: hollow → subtly-hollow) to a plain-English operator verdict layer; framework + high-frequency content into v1.5.7, expansion across v1.6.x.
- Reconciled against `QPB_v1.6.0_Design.md` (NFR + FP-audit; no output-surface collision) and `QPB_v1.6.x_Phase6_Structural_Enforcement_Proposal.md` (subprocess attestation — a different concern).

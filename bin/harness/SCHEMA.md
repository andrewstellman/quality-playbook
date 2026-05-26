# QPB Test Harness — SCHEMA (authoritative contract)

*Status: LOCKED 2026-05-25 (formalizes the locked §F contract from `docs/design/QPB_Test_Harness_1.5.7_Design.md`). This file is the single source of truth for the case/run schema, the normalized run-fact object, and the closed assertion vocabulary. `ai_context/TOOLKIT.md` + `ai_context/DEVELOPMENT_CONTEXT.md` summarize and link here. Claude authors run/case JSON against this; the grader reads exactly this. If something can't be expressed here, EXTEND this file deliberately — never allow free-form.*

---

## 1. Case schema (`cases.json` is a list of cases)

A **case** = identity + prep policy + expected outcome. Run inputs are physically separated from the answer key / expected assertions.

```json
{
  "id": "ACC-001",
  "type": "acceptance",                     // "acceptance" | "security_eval"
  "title": "weak model on keto → honest fail",
  "inputs": {
    "repo_url": "https://github.com/ory/keto",
    "target_ref": "<sha-or-tag>",           // the version QPB runs against
    "reference_docs_source": "<path or 'gather'>",  // acceptance: docs present
    "prep": "acceptance"                    // "acceptance" (normal) | "security" (blind)
  },
  "expected": [ /* §4 assertions — ACCEPTANCE ONLY */ ],
  "answer_key": { /* §1.1 — SECURITY ONLY; never enters run inputs */ }
}
```

- **`type` is mandatory.** The existing 10 cases are `security_eval`; acceptance cases are new.
- **`acceptance`** cases carry `expected` (a list of §4 assertions) and NO `answer_key`.
- **`security_eval`** cases carry `answer_key` and NO `expected`. The answer key MUST NOT appear in `inputs` or anywhere the run can read it.

### 1.1 Security `answer_key` (security_eval only)

```json
"answer_key": {
  "cwe": "CWE-89",
  "vulnerable_parent": "<sha>",
  "file": "path/to/file.go",
  "symbol": "FunctionOrMethod",
  "behavior": "one-line description of the planted defect"
}
```

## 2. Run schema (`runs/<case-id>/<run-id>/invocation.json`)

A **run** binds a case to one point of the run matrix. Rerun-with-a-different-axis = a new run referencing the same case.

```json
{
  "run_id": "20260525T194300Z",            // UTC YYYYMMDDTHHMMSSZ
  "case_id": "ACC-001",
  "axes": {
    "runner": "claude",                     // claude | copilot | codex | cursor
    "mode": "A",                            // A (agent drives) | B (run_playbook.py harness)
    "install_channel": "pip-local-wheel",   // §3 enum
    "install_version": null,                // for *-registry@<version|latest>; else null
    "model": "opus",
    "thinking": "high"                      // low | medium | high | xhigh | null
  },
  "qpb_version": "1.5.7",
  "target_sha": "<sha>",
  "cli_command": "...",                     // full command, verbatim
  "cwd": "...",
  "env_snapshot": { /* vendor markers etc. */ },
  "scrubbed_docs_manifest": null,           // security only: files+hash
  "leakage_gate": null,                     // security only: "clean" | "ABORTED"
  "started_at": "...", "ended_at": "...",
  "exit_code": 0,
  "terminal_state": "COMPLETED"             // §6
}
```

## 3. `install_channel` enum (per-run)

| Value | Meaning | Use |
|-------|---------|-----|
| `clone` | `python3 -m bin.install_skill --into <t> --ai-tool <tool>` from the QPB clone | dev / now |
| `pip-local-wheel` | `uvx`/`pipx` from a locally-built wheel | **pre-publish acceptance** |
| `npm-local-tgz` | `npx` from a locally-built `.tgz` | **pre-publish acceptance** |
| `pip-registry@<version\|latest>` | install from PyPI at a pinned version | post-publish smoke + version comparison |
| `npm-registry@<version\|latest>` | install from npm at a pinned version | post-publish smoke + version comparison |

Pre-publish acceptance MUST use `*-local`. `install_version` carries the pin for `*-registry`.

## 4. Closed assertion vocabulary — THE CONTRACT

Each `expected` entry: `{ "assertion": <name>, "comparator": "==" | "!=" | "in", "value": <expected> }`.
Examples: `{"assertion":"verdict_state","comparator":"==","value":"failed"}`,
`{"assertion":"attribution","comparator":"==","value":"weak_model"}`,
`{"assertion":"phase0_first_probe","comparator":"==","value":true}`.

### 4.1 Acceptance assertions

| Assertion | Type / domain | Maps to fact |
|-----------|---------------|--------------|
| `gate_result` | enum `PASS` \| `CLEANUP` \| `FAIL` | gate.gate_result (three-state) |
| `verdict_state` | enum `solid` \| `shallow` \| `failed` | verdict.verdict_state |
| `attribution` | enum `weak_model` \| `incomplete_verification` \| `none` | verdict.attribution |
| `recommends_stronger_model` | bool (true ONLY when attribution=weak_model) | verdict.recommends_stronger_model |
| `phase0_status_ok` | bool | phase0.status==ok |
| `phase0_first_probe` | bool | phase0.first_probe_ok |
| `banner_rendered` | bool | install.banner_rendered |
| `gitignore_remediation_followed` | bool | install.gitignore_remediation_followed |
| `provenance_runner_matches` | bool | provenance.detected_runner == axes.runner |
| `provenance_model_labeled_selfreport` | bool | provenance.selfreport_model_label present+labeled |
| `provenance_bugcount_vs_gate` | enum `match` \| `expect_mismatch` | provenance.provenance_mismatch |
| `no_false_pass` | bool | §4.3 |
| `no_false_fail` | bool | §4.3 |
| `bugs_unverified_message_present` | bool | verdict.bugs_unverified_present |

### 4.2 Security assertions

| Assertion | Type / domain | Maps to |
|-----------|---------------|---------|
| `answer_key_cited` | bool — BUGS.md/writeups cite the planted file/symbol/behavior | quality artifacts vs case.answer_key |
| `outcome` | enum `DETECTED` \| `PARTIAL` \| `MISSED` \| `BLOCKED` | security grader |

### 4.3 F-notes (LOCKED — part of the contract)

1. **`verdict_state` ⊥ `gate_result` are INDEPENDENT axes — the grader must not cross-couple them.** A `CLEANUP` (GATE PASSED WITH CLEANUP NEEDED) run is exit-0, and its lead verdict line is ✅ solid *or* ⚠️ shallow depending on shallow signals — there is no distinct CLEANUP lead state. So `gate_result=CLEANUP` may pair with either `verdict_state`, and `verdict_state=failed` does NOT imply `gate_result=FAIL`. A case may assert both independently.
2. **`no_false_pass` / `no_false_fail` are internal-consistency (tool-correctness) checks, NOT expectation-matching** (which would be redundant with asserting `gate_result`):
   - `no_false_pass` = the gate never reports `PASS`/`CLEANUP` while substantive (non-record-keeping) FAILs exist.
   - `no_false_fail` = the gate never reports `FAIL` on a run with zero substantive FAILs.
3. **`BLOCKED` (AUP/usage-policy stop) is graded `N/A`**, never `MISSED` (security) and never a false acceptance fail.
4. **`outcome` enum values** (security DETECTED/PARTIAL/MISSED) require human review before they count (`reviewed:true` in grading.json); auto-grade is the first pass.

## 5. Normalized run-fact object (`runs/.../facts.json`)

**Two-sourced (LOCKED):**
- **Gate-derived facts** come from **re-running the RUN'S OWN INSTALLED `quality_gate.py`** (the channel-installed gate at the version under test — NOT the dev clone's gate) over the run's final `quality/` artifacts, with the run's **vendor env var set** (`CODEX_THREAD_ID`/`COPILOT_AGENT_SESSION_ID`/`CLAUDECODE`) so `detected_runner` is correct. Deterministic; identical to what the run produced.
- **Live-behavior facts** are NOT in the artifacts and come from the transcript/stream.

```json
{
  "phase0": { "status": "ok", "probe_attempts": 1, "first_probe_ok": true },        // live
  "verdict": { "verdict_state": "shallow", "attribution": "none",
               "recommends_stronger_model": false, "bugs_unverified_present": false }, // gate
  "provenance": { "detected_runner": "codex", "selfreport_model_label": "gpt-5",
                  "gate_bug_count": 1, "reported_bug_count": 1, "provenance_mismatch": false }, // gate
  "gate": { "gate_total": "...", "gate_result": "CLEANUP", "cleanup_gaps": 0 },        // gate
  "install": { "banner_rendered": true, "gitignore_remediation_followed": true },     // live
  "run_meta": { "blocked": false, "stop_reason": null, "exit_code": 0,
                "timings": {}, "raw_receipt": "stream.ndjson" }
}
```

`gate_result` legal raw values: `GATE PASSED` → `PASS`, `GATE PASSED WITH CLEANUP NEEDED` → `CLEANUP`, `GATE FAILED` → `FAIL`.

## 6. Terminal states (run lifecycle)

`QUEUED → PREPARING → RUNNING → <terminal> → (GRADED if terminal == COMPLETED)`

`COMPLETED` (exit 0 + gate verdict) · `FAILED` (nonzero/crash/no verdict) · `TIMED_OUT` · `BLOCKED` (AUP stop ⇒ N/A) · `KILLED` (user) · `ABORTED_PREP` (clone/checkout/leakage-gate/install failed — run never started). Grading runs only on `COMPLETED`; all other terminals grade `N/A (run incomplete)` with the reason.

## 7. Receipts (per run dir)

`invocation.json` · `status.json` (state+PID+heartbeat+exit+terminal) · `facts.json` (§5) · `stream.ndjson` (raw — **always retained, externalized/gitignored, never committed**) · `quality/` (target artifacts copied out) · `grading.json` (verdict + per-assertion results + evidence + `reviewed:false` + optional `human_verdict`) · `summary.md`. `runs_index.json` is a rebuildable cache. Structured receipts ARE committed; raw streams are not.

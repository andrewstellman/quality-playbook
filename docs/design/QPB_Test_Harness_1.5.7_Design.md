# QPB Test Harness (v1.5.7) — Design

*Status: DESIGN FOR REVIEW (no code yet). Owner: Andrew Stellman. 2026-05-25.*

*This design doc lives in `~/Documents/QPB/docs/design/`. The harness code, `cases.json`,
`SCHEMA.md`, and run receipts live in the benchmark sandbox at
`~/Documents/QPB/repos/security-test-cases/`.*

A general QPB test harness over a shared execution / receipt / orchestration substrate. It
serves **two case types** on one engine:

- **`security_eval`** — does QPB find a planted/known bug? Graded blind against an answer key.
  (Source: `CVE_BENCHMARK_*.md` in `~/Documents/AI-Driven Development/Security Research/`.)
- **`acceptance`** — does the tool itself behave correctly (verdict state, attribution,
  provenance, Phase-0, install surface)? Graded against an expected behavioral shape.
  (Source: `docs/design/QPB_v1.5.7_Release_Acceptance_Checklist.md`, Tier 0–3.)

Built to be ready the moment QPB v1.5.7 + the pip/npm installers ship, and reusable for every
future release's acceptance gate.

---

## ⚠️ SIMPLIFIED RUNNER MODEL (2026-05-26 — supersedes the file-format + SCHEMA.md complexity below)

Owner decision: collapse the case/run-plan/SCHEMA split into **one plain file → one self-contained
output folder → one summary table**. The assertion *vocabulary* (§F) is unchanged; everything about
*how it's expressed and run* simplifies. **`SCHEMA.md` is deleted** — the file below is self-evident
with its one-line header.

**One input file** = a `pools` header (per-runner concurrency) + a `runs` array. No `id` (runs are
identified by array index; a `description` is the human justification, drillable in the TUI). `expect`
is a **flat map** of `assertion -> value` (no `{assertion, comparator, value}` triples); a **list
value means "one of"**.

```json
{
  "pools": { "claude": 2, "codex": 1, "copilot": 1 },
  "runs": [
    { "description": "Finds + verifies the known gson duplicate-key bug — should reach solid",
      "repo": "gson", "ref": "<pre-fix-sha>", "runner": "claude", "model": "opus",
      "channel": "pip-local-wheel",
      "expect": { "gate_result": "PASS", "verdict_state": "solid", "no_false_pass": true } },
    { "description": "Weak model cuts corners — should fail with weak-model attribution",
      "repo": "chi", "ref": "main", "runner": "codex", "model": "gpt-5.2", "channel": "npm-local-tgz",
      "expect": { "gate_result": "FAIL", "attribution": "weak_model", "recommends_stronger_model": true } },
    { "description": "Capable model on a meaty authz repo — honest verdict, clean install surface",
      "repo": "keto", "ref": "master", "runner": "copilot", "model": "gpt-5.4", "channel": "pip-local-wheel",
      "expect": { "gate_result": ["PASS","CLEANUP","FAIL"], "no_false_pass": true, "no_false_fail": true,
                  "phase0_first_probe": true, "banner_rendered": true, "gitignore_remediation_followed": true } }
  ]
}
```

**One harness-run folder** (self-contained, created per harness run, timestamped):
```
<harness-run>/
├── SUMMARY.md       ← the result table (below) — how the whole run turned out
├── plan.json        ← copy of the input file that was run
├── run-00/  target/ (cloned repo + QPB installed) · invocation.json · stream.ndjson · facts.json · grading.json · summary.md
├── run-01/  …
└── run-02/  …
```

**Each run** does exactly five steps: clone `repo@ref` into `run-NN/target` → `npx`/`pipx` install via
`channel` → run with the run's `runner`+`model` → grade facts against `expect` → log MET/NOT. Runs
execute in parallel up to the **per-runner pool** sizes (reuse the existing `scheduler.Scheduler`
for gating; the manager daemon + TUI are optional bells-and-whistles, NOT required for this flow).

**One table** at the end (`SUMMARY.md`), run_playbook-style Y/N per phase + the acceptance result.
The phase columns show what *mechanically* happened (a weak run shows N's + `FAILED`); the **`result`**
column is the acceptance verdict — *did it match `expect`?* — so a `gate=FAILED` run reads `✓ MET`
when failing was the prediction:
```
#  description                         repo  runner  model    P0 P1 P2 P3 P4 P5 P6  gate     result
0  Finds + verifies gson dup-key bug   gson  claude  opus     Y  Y  Y  Y  Y  Y  Y   PASSED   ✓ MET
1  Weak model cuts corners…            chi   codex   5.2-low  Y  Y  Y  N  -  -  -   FAILED   ✓ MET
2  Capable model on meaty authz…       keto  copilot 5.4      Y  Y  Y  Y  Y  Y  Y   FAILED   ✓ MET
=> 3/3 MET — acceptance PASSED
```

**Terminology:** GATE PASS/FAIL is QPB's judgment of the run; the acceptance **result** is MET/NOT-MET
= "did QPB behave as the run's `expect` predicted." A predicted failure that fails = MET.

*The sections below (case/run schema split, SCHEMA.md, §C–§N component framing) are the prior, more
elaborate design; they're retained for the contract details (esp. the §F assertion vocabulary and the
two-sourced fact extraction, both still valid) but the input/output/SCHEMA mechanics are superseded by
this simplified model.*

## Decisions locked (2026-05-25)

- **One engine, two case types** (`type` field per case). Each type owns a **prep policy** and a
  **grader**, both plugged into the same engine. Security prep (scrub/answer-key/leakage) and
  acceptance prep are **sibling plugins** — do not bend one path to do the other; keep them thin
  configs over one engine.
- **The closed assertion vocabulary is THE contract** (§F). Lock it first — Claude authors run
  definitions against it, the grader evaluates it. It is the only place free-form is forbidden.
- **Graders read a normalized run-fact object, never raw CLI output** (§C).
- **Parallel, concurrency-aware scheduler with per-vendor caps** (§H) — not strict-sequential.
  Default cap 1/vendor (so default behavior is effectively sequential per vendor), configurable.
- **Grading is automatic + non-blocking**; verdicts store evidence + `reviewed:false` for later
  human override; the queue never waits on review.
- **Manager daemon owns execution; the Textual TUI is a read-mostly client** (commands via a
  control file; the TUI never spawns runs).
- **Reuse `bin/run_playbook.py`** for runner invocation/parsing — don't rebuild (§G).
- **install_channel is a per-run, version-pinned enum** (§D).
- **Ship as release tooling, excluded from the adopter install closure** (§J).
- **Build order is dependency sequencing, not a scope cut** (§M).

---

## A. Scope — one engine, two case types

```
                 ┌───────────────── shared engine ─────────────────┐
   case (type) → │ scheduler → prep policy → runner adapter → run   │ → receipts
                 │              (per type)    (per runner)    facts  │
                 └──────────────────────────────┬───────────────────┘
                                                 ▼
                              normalized run-fact object (§C)
                                                 ▼
                                    grader (per type) → grading.json
```

A **case** = identity + prep policy + expected outcome. A **run** = a case bound to one point of
the run matrix (§E). The security path and the acceptance path share everything except their
prep policy and their grader.

## B. The two oracles (why the graders differ)

| | `security_eval` grader | `acceptance` grader |
|---|---|---|
| Question | Did QPB find the planted bug? | Did the tool behave correctly? |
| Prep | **Blind:** scrub `reference_docs/`, leakage-grep, abort if the bug is named; answer key never enters run inputs | **Normal run:** docs present, no scrub; prep policy per-case |
| Oracle | Answer-key match | Expected behavioral shape (assertions) |
| Outcomes | `DETECTED \| PARTIAL \| MISSED \| BLOCKED` | per-assertion pass/fail (§F) |

`BLOCKED` (AUP/usage-policy stop) is graded **N/A**, never a detection failure.

## C. Normalized run-fact extraction layer

Both graders consume a common **fact object**, regardless of CLI; graders never touch raw CLI
output. Facts are **two-sourced** — this is the key robustness decision (it removes the Mode-A
dependency on scraping the agent's free-form chat for the verdict block):

- **Gate-derived facts** (`gate_result`, `verdict_state`, `attribution`,
  `recommends_stronger_model`, `bugs_unverified_present`, and provenance
  `model`/`bug_count`/`mismatch`) are obtained by **re-running `quality_gate.py` over the run's
  final `quality/` artifacts** and reading its structured output. This is deterministic and
  identical to what the run produced — no transcript scraping. Verified against source:
  `quality_gate.py` carries the verdict layer (090v) + run provenance (090w) + `bugs_unverified`
  (090x). To make `provenance.detected_runner` correct, the harness **sets the run's vendor env
  var when it re-runs the gate** — runner detection is env-derived (`_RUNNER_ENV_MARKERS`:
  `CODEX_THREAD_ID`→codex, `COPILOT_AGENT_SESSION_ID`→copilot, `CLAUDECODE`→claude-code; multiple
  set → joined with `+`). This is exactly how those facts were validated in chat (Keto run5).
- **Live-behavior facts** are NOT in the artifacts and so must come from the transcript/stream:
  `phase0_first_probe` (the probe-retry happens live), `banner_rendered`,
  `gitignore_remediation_followed` (did the agent run the real remediation or improvise),
  `blocked`/`stop_reason`. The runner adapter (§G) parses these from its CLI's output.

Each runner adapter normalizes the live-behavior portion into the shape below; the gate-derived
portion is identical across adapters because it comes from re-running the gate, not from the CLI.

Fact object (minimum fields):
- **Phase-0:** `status` (ok/remediable/blocked), `probe_attempts`, `first_probe_ok` (reached ok
  with no repo-root path-mismatch retry — 090t).
- **Operator verdict block:** `verdict_state` (✅ solid / ⚠️ shallow / ❌ failed), `attribution`
  (weak_model / incomplete_verification / none), `recommends_stronger_model` (bool),
  `bugs_unverified_present` (bool — 090x).
- **Provenance line:** `detected_runner`, `selfreport_model_label`, `gate_bug_count`,
  `reported_bug_count`, `provenance_mismatch` (bool — e.g. Keto run5 gate 3 vs reported 0).
- **Gate:** `gate_total`, `gate_result` (`GATE PASSED` / `GATE PASSED WITH CLEANUP NEEDED` /
  `GATE FAILED` — the three-state verdict), `cleanup_gaps` (int).
- **Install surface:** `banner_rendered` (bool), `gitignore_remediation_followed` (bool — no
  improvisation, 090u).
- **Run meta:** `blocked` + `stop_reason`, `exit_code`, `timings`, raw-receipt pointer.

## D. install_channel — per-run, version-pinned enum

| Value | Meaning | Use |
|-------|---------|-----|
| `clone` | `python3 -m bin.install_skill --into <t> --ai-tool <tool>` from `qpb_clone_path` | dev / now |
| `pip-local-wheel` | `uvx`/`pipx` from a locally-built wheel | **pre-publish acceptance** |
| `npm-local-tgz` | `npx` from a locally-built `.tgz` | **pre-publish acceptance** |
| `pip-registry@<version\|latest>` | install from PyPI at a pinned version | post-publish smoke + version comparison |
| `npm-registry@<version\|latest>` | install from npm at a pinned version | post-publish smoke + version comparison |

Pre-publish acceptance MUST use the `*-local` variants (the registry channel can't be tested
until after publish). Version-pinning is what enables release-to-release comparison runs.

## E. Run matrix — per-run axes (all first-class from day one)

`runner` (claude / copilot / codex / cursor) · `mode` (A | B) · `install_channel` (+version) ·
`model` (+ thinking/effort). A case defines identity + prep + expected outcome; a run binds a case
to one matrix point. **Rerun-with-different-axis is just a new run referencing the same case.**

## F. Closed assertion vocabulary — THE CONTRACT (lock first; extend only deliberately)

Run definitions (which Claude may author) and the grader both speak ONLY this vocabulary. Each
assertion maps to a normalized run-fact (§C). If an assertion can't be expressed here, that is a
signal to **extend the vocabulary deliberately**, not to allow free-form assertions.

**Acceptance assertions**

| Assertion | Type | Maps to (fact) |
|-----------|------|----------------|
| `gate_result` | enum PASS\|CLEANUP\|FAIL | gate.gate_result |
| `verdict_state` | enum solid\|shallow\|failed | verdict.verdict_state |
| `attribution` | enum weak_model\|incomplete_verification\|none | verdict.attribution |
| `recommends_stronger_model` | bool (true ONLY for weak_model) | verdict.recommends_stronger_model |
| `phase0_status_ok` | bool | phase0.status==ok |
| `phase0_first_probe` | bool (ok with no repo-root-mismatch retry) | phase0.first_probe_ok |
| `banner_rendered` | bool | install.banner_rendered |
| `gitignore_remediation_followed` | bool (no improvisation) | install.gitignore_remediation_followed |
| `provenance_runner_matches` | bool | provenance.detected_runner vs runner axis |
| `provenance_model_labeled_selfreport` | bool | provenance.selfreport_model_label present+labeled |
| `provenance_bugcount_vs_gate` | enum match\|expect_mismatch | provenance.provenance_mismatch |
| `no_false_pass` | bool | gate vs substantive findings |
| `no_false_fail` | bool | gate vs clean run |
| `bugs_unverified_message_present` | bool | verdict.bugs_unverified_present |

**Security assertions**

| Assertion | Type | Maps to |
|-----------|------|---------|
| `answer_key_cited` | bool (BUGS.md/writeups cite the planted file/func/behavior) | quality artifacts vs case.answer_key |
| `outcome` | enum DETECTED\|PARTIAL\|MISSED\|BLOCKED | security grader; BLOCKED ⇒ N/A |

**F-notes (lock these with the tables):**

- **`verdict_state` and `gate_result` are INDEPENDENT axes — the grader must not cross-couple
  them.** A `GATE PASSED WITH CLEANUP NEEDED` run is exit-0, and its lead verdict line is ✅ solid
  *or* ⚠️ shallow depending on shallow signals — there is no distinct CLEANUP lead state. So
  `gate_result=CLEANUP` can pair with either `verdict_state`, and `verdict_state=failed` does NOT
  imply `gate_result=FAIL`. The fact object keeps them separate; a case may assert both.
- **`no_false_pass` / `no_false_fail` are internal-consistency (tool-correctness) checks, NOT
  expectation-matching** (otherwise they're redundant with asserting `gate_result`). Definitions:
  `no_false_pass` = the gate never reports PASS/CLEANUP while substantive (non-record-keeping)
  FAILs exist; `no_false_fail` = the gate never reports FAIL on a run with zero substantive fails.
  SCHEMA.md pins these precisely.
- **`expected` entry shape (part of locking the contract).** Each acceptance `expected` entry is
  `{ "assertion": <name from the F tables>, "comparator": "==" | "!=" | "in", "value": <expected
  value> }` — e.g. `{"assertion":"verdict_state","comparator":"==","value":"failed"}`,
  `{"assertion":"attribution","comparator":"==","value":"weak_model"}`,
  `{"assertion":"phase0_first_probe","comparator":"==","value":true}`. SCHEMA.md is authoritative
  for this shape and the legal `value` domain per assertion; the grader reads exactly this.

## G. Runner adapters — reuse `bin/run_playbook.py` (verified specifics)

All four CLIs are already coded in `bin/run_playbook.py` — reuse the invocation + output patterns
rather than rebuild. Confirmed against the source (HEAD 2026-05-25):

- Runner flags `--claude / --copilot / --codex / --cursor` at **lines 390–393** (default
  `copilot`).
- Per-runner command construction: `command_for_runner(runner, prompt, model)` at **line 1479**
  (+ `_resolve_runner_command` at 1456, `command_preview` at 1525).
- `--model` override per runner at **line 504** (applied at 1483/1514).
- `copilot_resolver` routing (standalone `copilot` with deprecated `gh copilot` fallback) at
  **line 1517**.
- `run_playbook.py` **is the Mode B harness** — Mode B runs can shell out to / reuse it directly.

An adapter = **(invocation template, output parser → normalized facts (§C), capability flags)**.
Support both modes per runner: **Mode B** reuses `run_playbook.py`; **Mode A** launches the CLI
with the channel-install launch prompt and lets the agent drive Phases 1–6 inline. Parsers must
handle streaming heterogeneity (claude has clean `stream-json --verbose`; others differ), but the
command-construction knowledge already exists in `run_playbook.py`.

## H. Parallel scheduler — per-vendor concurrency caps

Rate limits are **per-vendor**, so cap concurrency per vendor, not globally-serial:

- Per-vendor caps: `anthropic` / `openai` (codex) / `github` (copilot) / `cursor`, default **1**
  each, configurable (e.g. `anthropic: 2`).
- A **global cap** for machine resources.
- The inter-run delay becomes a **per-vendor cooldown**.
- The scheduler launches the next queued run whose vendor has free capacity.

Safe because each run already gets a **pristine worktree** (no shared target tree) and a **receipt
dir as source of truth** (no shared-file races). The manager tracks N in-flight PIDs; the TUI
shows N live.

## Folder layout (split: code in `bin/`, data + receipts in `repos/security-test-cases/`)

**Owner decision (2026-05-25, supersedes the earlier single-folder layout):** the harness Python
lives in **`bin/harness/`** (protected QPB source — worker-built, dual-chat-reviewed, NOT
Cowork-direct), and the case JSON / config / `SCHEMA.md` / receipts live in
**`repos/security-test-cases/`** (Cowork-editable). See the implementation plan
(`QPB_Test_Harness_1.5.7_Implementation_Plan.md`) for the lane/branch/test consequences.

```
bin/                                  ← PROTECTED SOURCE (worker-built); EXCLUDED from the install bundle (§J)
├── harness/                          ← the harness subpackage
│   ├── schema.py                     ← dataclasses, enums, the §F vocabulary + `expected`-entry shape
│   ├── prepare.py                    ← prep policies: security (scrub/leakage) + acceptance (normal)
│   ├── runner.py                     ← adapters; spawn detached run; capture stream; max-duration timeout
│   ├── facts.py                      ← two-sourced run-fact extraction (§C)
│   ├── grade_security.py / grade_acceptance.py ← the two graders (§B, §F)
│   ├── scheduler.py                  ← per-vendor caps + cooldown + global cap (§H)
│   ├── manager.py                    ← daemon: owns queue, schedules, writes outcomes, crash recovery
│   └── tui.py                        ← Textual app (read-mostly client)
└── qpb_harness.py                    ← user-facing entry (queue/launch/TUI); self-describing on no-args

repos/security-test-cases/            ← Cowork-editable data + receipts (NEVER bundled — repos/ is the sandbox)
├── SCHEMA.md            ← authoritative case/run schema + the §F assertion vocabulary (one source of truth)
├── cases.json           ← case registry (type: security_eval | acceptance; INPUTS vs ANSWER KEY/EXPECTED)
├── config.json          ← channels, vendor caps, cooldowns, timeouts, paths
├── .gitignore           ← ignores mirrors/ + bulk receipts; keeps structured receipts
├── mirrors/             ← cached blobless git mirrors per project (gitignored)
├── runs/<case-id>/<run-id>/
│   ├── invocation.json  ← command, axes (runner/mode/channel+version/model), QPB ver, parent SHA, env, times
│   ├── status.json      ← state + PID + heartbeat + exit code + terminal reason
│   ├── facts.json       ← the normalized run-fact object (§C)
│   ├── stream.ndjson    ← raw CLI receipt
│   ├── quality/         ← target's QPB artifacts copied out
│   ├── grading.json     ← verdict/assertions + evidence + reviewed flag + human override
│   └── summary.md       ← human-readable one-pager
├── runs_index.json      ← DERIVED, rebuildable from runs/*/*/status.json
└── control/             ← queue.json · manager.pid · commands.jsonl
```

`<run-id>` = UTC `YYYYMMDDTHHMMSSZ` (QPB run-id convention). The per-run dir is the source of
truth; the index is a cache. **Bundle/import isolation:** `bin/harness/` is excluded from
`_bundle_files()` (verified: that function is an explicit allowlist of bin/ modules, install_skill.py
~181–194, so a new subpackage is excluded by default), and no bundled module — including
`bin/__init__.py` — may import `bin.harness`. A test asserts both (extends `test_publish_safety_090c.py`).

## I. Documented schema (so anyone — or Claude — can generate a run)

`SCHEMA.md` next to the JSON is authoritative for the case/run schema **and** the §F assertion
vocabulary. `ai_context/TOOLKIT.md` + `ai_context/DEVELOPMENT_CONTEXT.md` summarize it and link to
it (one source of truth; TOOLKIT stays navigable). This is what makes *"ask Claude to generate
acceptance tests for version X → get a runnable JSON"* real.

`cases.json` gains a `type` field (`security_eval` | `acceptance`). Security cases keep
`inputs` + `answer_key`; acceptance cases use `inputs` + `expected` (a list of §F `expected`
entries — the `{assertion, comparator, value}` shape pinned in the F-notes, authoritative in
SCHEMA.md).

## J. Ship as release tooling — NOT part of the skill

The harness code lives in **`bin/harness/`** (protected source) but is **explicitly excluded from
`_bundle_files()` and the channel artifacts** — it must never bloat an adopter's install closure.
Two hard requirements, both tested (extending `test_publish_safety_090c.py`): (1) no `bin/harness/`
path appears in the bundle closure manifest; (2) no bundled module — including `bin/__init__.py` —
imports `bin.harness`. The allowlist nature of `_bundle_files()` (install_skill.py ~181–194) makes
(1) the default; (2) is the real discipline to guard. Commit the acceptance/security case JSON + the
small structured receipts (`invocation.json`, `facts.json`, `grading.json`, `summary.md`, the
rebuildable index) as "show the receipts" evidence; gitignore or externalize the raw `stream.ndjson`
(commit it only for canonical acceptance runs) to avoid repo bloat.

## Run lifecycle (state machine)

`QUEUED → PREPARING → RUNNING → <terminal> → (GRADED if terminal == COMPLETED)`

| State | Meaning |
|-------|---------|
| QUEUED | in `control/queue.json`, waiting for vendor capacity |
| PREPARING | prep policy runs (security: worktree→scrub→**leakage gate**→Phase-0 install; acceptance: worktree→docs→Phase-0 install) |
| ABORTED_PREP | a prep step failed (clone/checkout/**leakage non-empty**/install) — run never started |
| RUNNING | CLI subprocess live (PID tracked, heartbeat) |
| COMPLETED | exited 0 and a gate verdict was produced |
| FAILED | nonzero exit / crash / no gate verdict |
| TIMED_OUT | exceeded per-run max-duration → killed |
| BLOCKED | AUP/usage-policy stop in the stream (**not** a missed detection) |
| KILLED | user-cancelled via TUI |

Grading runs only on COMPLETED. For BLOCKED/FAILED/TIMED_OUT/ABORTED_PREP, the verdict is
`N/A (run incomplete)` with the reason — never MISSED, never a false acceptance fail.

## Reproducibility metadata (per run, in `invocation.json`)

QPB version + install channel/version · model + thinking + runner CLI · mode · `repo_url` +
`vulnerable_parent`/target SHA · scrubbed-docs manifest + hash (security) · leakage-gate result ·
full CLI command · cwd · env snapshot · start/end · exit code · terminal state. This is the record
the writeup and the release-comparison cite.

## Manager daemon + TUI

- **Manager (`manager.py`):** single daemon; writes `control/manager.pid` + heartbeat; runs the
  scheduler (§H); consumes `control/commands.jsonl` (enqueue/cancel/reorder/pause/resume);
  prepares→runs→grades each run; crash recovery on restart (RUNNING + dead PID + no terminal →
  `FAILED (orphaned)`).
- **TUI (`tui.py`, Textual, read-mostly):** list of runs/queue with case-id, type, axes, state,
  verdict/outcome, elapsed; **N in-flight rows** highlighted live; drill-in to `summary.md`,
  `facts.json`, tail of `stream.ndjson`, `quality/BUGS.md`, `grading.json`; actions sent as
  commands (enqueue w/ axes, cancel, reorder, pause, **review a grade** → set `human_verdict`,
  `reviewed:true`). Safe to open/close anytime.

## K. Testing — thorough, including the TUI

Full unit coverage of: the engine, the **scheduler** (per-vendor cap logic + cooldown + global
cap), both **prep policies**, both **graders**, the **normalized-fact extractor per adapter**, and
**crash recovery**. **TUI tests:** render a specific screen state (e.g., 3 in-flight runs across
vendors + a completed graded run) and assert the rendered output contains the right elements (run
rows, in-flight markers, verdict/grade, provenance). **Mutation-bite** the graders (e.g., a
mis-attribution or a false PASS must fail a test).

## L. 1.5.7 acceptance integration

Acceptance cases derive from `docs/design/QPB_v1.5.7_Release_Acceptance_Checklist.md` (Tier 0–3).
The **minimum to gate 1.5.7**: the **claude Mode A** path on **local-artifact installs**
(`pip-local-wheel` / `npm-local-tgz` from the freshly-built wheel/tgz) producing the verdict-state
matrix:

- **Run A — ✅ solid** (strong model, small clean repo, real red→green TDD) — the never-seen-live state.
- **Run B — ❌ weak_model** (weak model) → `GATE FAILED` + weak-model attribution + recommends-stronger-model.
- **Run C — honest verdict** on a meatier repo (auth/authz via Codex to dodge the AUP classifier) — no false PASS/FAIL; likely exercises 090x `bugs_unverified`.
- **Run D — ⚠️ shallow** (optional; accept unit coverage if A–C don't yield it).

Generate these as the first acceptance-case set. (Checklist HEAD under test: `980e136`; reference
fixtures: Keto run5, NATS run2 gpt-5.4.)

## M. Build order (dependency sequencing — not an estimate, not a scope cut)

1. **Substrate** (prepare/run/grade engine + receipt dirs + normalized facts) on `claude`.
2. **Acceptance grader + assertion vocabulary**, proven on the 1.5.7 acceptance cases via
   local-artifact installs.
3. **Parallel scheduler** (per-vendor caps).
4. **Manager daemon + Textual TUI** (+ TUI tests).
5. **Broaden runner adapters** to codex/copilot/cursor + Mode B by reusing `run_playbook.py`.
6. **Registry/version-pinned channels** (post-publish) + version-comparison runs.

The `security_eval` cases ride the same engine throughout.

## N. Open items

- **§F assertion vocabulary** — incorporates review round 2: three-state `gate_result`, the
  `verdict_state ⊥ gate_result` independence, the tool-correctness definitions of
  `no_false_pass`/`no_false_fail`, and the `{assertion, comparator, value}` `expected`-entry
  shape. Treat as **locked pending the reviewer's final pass**, then frozen before grader code.
- **Two-sourced fact extraction (§C)** is the load-bearing design choice — gate-derived facts come
  from re-running `quality_gate.py` (vendor env var set), live-behavior facts from the transcript.
  SCHEMA.md/`facts.py` must reflect this split.
- **CWE-200 / information-disclosure** `security_eval` case is a data gap (goauthentik candidate),
  separate from this design.
- Decide whether `stream.ndjson` is committed for canonical acceptance runs or always externalized.
- Confirm the `_bundle_files()` exclusion test lives in the existing bundle-completeness suite.

## O. Cross-platform support (Linux + macOS + Windows)

*Added 2026-06-01 (post-180 Windows-compat work). The harness was originally written POSIX-first;
nine iterations of Windows acceptance testing (instruction 180 + 180-followups-1 through 9)
surfaced eight categories of cross-platform concern that the original audit missed. This section
documents the contract so future maintenance and QPB-on-QPB self-audits catch cross-platform
issues at design-review time, not at operator-fire time.*

### Supported platforms (committed contract)

The harness MUST run end-to-end on:

1. **Linux** — Ubuntu 22.04+ tested manually; Debian-family general.
2. **macOS** — 12+ tested in development; uses BSD-shaped POSIX.
3. **Windows** — 11 tested via operator acceptance fires; PowerShell + Command Prompt; Python
   3.10+ from python.org or Microsoft Store.

Adding a fourth platform (BSD variants, ARM Linux distros, Alpine-musl, etc.) requires running the
audit checklist below against that platform's stdlib variants and extending `bin/harness/_platform.py`
where the existing abstractions don't cover the new platform's idiom.

### Process management: `psutil` (post-182)

The harness routes process-management primitives through `psutil` (harness-only dependency,
declared in `pyproject.toml`'s `[project.optional-dependencies] harness` extra; NOT in the skill
bundle — enforced by `SkillBundleHarnessOnlyDepTests` in `bin/tests/harness/test_platform_compat_180.py`).

- **pid liveness**: `psutil.Process(pid).is_running()` — replaces the pre-182 hand-rolled
  POSIX signal-0 probe / Windows `OpenProcess + GetExitCodeProcess` implementations.
  Post-184 (FINDING-23): the four sibling divergent helpers in `watchdog.py`, `runner.py`,
  `status.py`, and `manager.py` are also consolidated to alias `_platform.pid_alive`.
- **process-tree kill**: `parent.children(recursive=True)` + `proc.kill()` for each — the Windows
  leg now actually kills descendants, not just the leader (fixes the latent bug Andrew observed
  in run `20260601T201924Z`: command windows continued popping up after the "failure" because
  node.exe / MCP / sub-shells were orphaned).
- **exit-code recovery from orphans**: `psutil.Process(pid).wait(timeout)` — recovers the actual
  exit code from processes that aren't direct children of the calling process. Replaces the
  pre-182 hardcoded `exit_code=-1` for orphan-collected runs.
- **recycling-safe identity**: `(pid, psutil.Process(pid).create_time())` tuple. Windows recycles
  pid numbers fast enough for long-running plans to hit a pid that the OS has reassigned to a
  different process; the create_time anchor distinguishes "still our launched process" from
  "different process at the same pid."

`bin/harness/_platform.py` still owns non-process platform shims: filesystem (`get_tmp_dir`,
`get_orchestrator_log_path`), file locks (`acquire_file_lock` / `release_file_lock` — fcntl vs
msvcrt), executable resolution (`resolve_executable` — PATHEXT), subprocess kwargs
(`popen_kwargs_detached` — detach flags), detached spawn (`spawn_detached` — fork vs
CreateProcess), and platform sentinels (`IS_WINDOWS`, signal-constant availability).

stdlib `subprocess.Popen` still owns the launch path. `psutil.Popen` is a wrapper, not a
replacement — stdlib subprocess is correct for launching, psutil is correct for managing
post-launch.

### Windows console-window suppression (post-183)

The harness uses `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` (not the earlier
`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`) as the Windows creationflags for detached
subprocesses. `DETACHED_PROCESS` causes new-console allocation for console apps (flashing UI
artifact during the brief moment between allocation and process termination); `CREATE_NO_WINDOW`
correctly suppresses console-window creation AND propagates the no-window behavior to inherited
child processes — so the AI CLI's downstream children (hooks, node.exe, MCP servers) inherit the
no-window behavior too. The two flags are mutually exclusive per MSDN.

### Cross-platform abstraction seam: `bin/harness/_platform.py`

All platform-conditional logic routes through `bin/harness/_platform.py`. Direct use of
platform-specific symbols (`os.fork`, `signal.SIGHUP`, `fcntl.flock`, `msvcrt.locking`, etc.) in
non-test `bin/*.py` files outside this module is FORBIDDEN unless explicitly annotated
`# Windows-OK: <reason>` (e.g., `sys.executable` is always a full path so direct subprocess use
is safe). The `# Windows-OK` annotation is the explicit-exception escape hatch the source-pin
sweep test in §O.4 accepts.

The module exposes:

- `IS_WINDOWS` — module-level boolean (`sys.platform == "win32"`).
- `get_tmp_dir()` — cross-platform temp dir (POSIX: `/tmp`; Windows: `tempfile.gettempdir()`).
- `get_orchestrator_log_path(run_id)` — auto-detach orchestrator log path.
- `popen_kwargs_detached()` — subprocess kwargs for detaching (POSIX: `start_new_session=True`;
  Windows post-183: `creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP`).
- `spawn_detached(args, log_path, env)` — cross-platform detached spawn (POSIX:
  `fork`+`setsid`+`dup2`; Windows: `subprocess.Popen` with detached creationflags).
- `acquire_file_lock(fp, blocking)` / `release_file_lock(fp)` — cross-platform file lock (POSIX:
  `fcntl.flock`; Windows: `msvcrt.locking`).
- `pid_alive(pid)` — cross-platform liveness probe via `psutil.Process(pid).is_running()`
  (post-182). Pre-182 used hand-rolled `os.kill(pid, 0)` (POSIX) and
  `OpenProcess + GetExitCodeProcess` (Windows). All five harness-side `_pid_alive` / `pid_is_alive`
  helpers (in plan_runner / watchdog / runner / status / manager) are now aliased imports of
  this one canonical function (184 FINDING-23 closes the lesson #28 hole).
- `resolve_executable(name)` — `shutil.which` wrapper that returns the full path with extension
  on Windows (handles PATHEXT for `.cmd` / `.bat` / `.exe`).
- `kill_process_tree(pid, *, force)` — cross-platform forced termination via `psutil`
  (post-182: tree-walks descendants on both platforms; pre-182 the Windows leg killed only the
  leader).
- `process_create_time(pid)` — snapshot start time as Unix-epoch float (psutil); the
  spawn-side capture for recycling-defense identity tuples.
- `pid_alive_with_identity(pid, original_create_time)` — recycling-safe liveness; matches
  `(pid, create_time)` tuple. Falls back to plain `pid_alive` when `create_time is None` for
  pre-182 manifest backward-compat.
- `wait_for_process(pid, timeout)` — recovers actual exit code from orphans via psutil
  (works on non-direct-children, unlike `waitpid`); returns `None` on already-reaped or
  timeout.

### Categories of cross-platform concern (the audit checklist)

When introducing or reviewing code in `bin/`, the following eight categories MUST be checked
against cross-platform compatibility:

1. **Subprocess invocation by bare name** — `subprocess.Popen([cmd, ...])` where `cmd` is a bare
   name (no path). Windows does NOT extension-walk `PATHEXT`; `npm` fails as `npm.cmd` because
   `CreateProcess` looks for a literal `npm` executable. Route through
   `_platform.resolve_executable` for any external CLI tool (`npm`/`npx`/`git`/`claude`/`copilot`/
   `codex`/`cursor`/`node`). `sys.executable` is already a full path; `shutil.which("python")` is
   fine too.

2. **POSIX-only signals** — `signal.SIGHUP`, `SIGUSR1`, `SIGUSR2`, `SIGCHLD`, `SIGPIPE`,
   `SIGTTIN`, `SIGTTOU`, `SIGTSTP`, `SIGWINCH`, `SIGPROF`, `SIGTRAP`, `SIGBUS`, `SIGSYS`,
   `SIGKILL`, `SIGQUIT`, `SIGSTOP`, and others. Accessing the attribute on Windows raises
   `AttributeError` (NOT `OSError`). Must be guarded with `except AttributeError` OR
   `hasattr(signal, "SIGXXX")` OR an `IS_WINDOWS` branch. Pay particular attention to function
   default arguments: `def f(sig=signal.SIGKILL):` evaluates at module-load time and crashes
   Windows imports.

3. **POSIX-only stdlib modules** — `fcntl`, `pwd`, `grp`, `resource`, `termios`, `tty`. A
   top-level `import fcntl` crashes Windows at module-import time even when the call site never
   runs. Must be lazy/conditional inside `_platform.py` helper bodies. Outside `_platform.py`,
   never import these at module scope.

4. **Windows-only stdlib modules** — `msvcrt`, `winreg`. Top-level import crashes POSIX. Must be
   lazy/conditional inside `_platform.py` (or guarded by `if IS_WINDOWS:`).

5. **Hardcoded paths** — `/tmp/`, `/var/`, `/proc/`, `/dev/` are POSIX-only. Route through
   `_platform.get_tmp_dir()` for tempdir use; flag any other POSIX-rooted path against the
   Windows equivalent (`%TEMP%`, `%ProgramData%`, etc.). Also applies to docstring / argparse
   help text — argparse's `%` formatter interprets `%TEMP%` literally and crashes `--help`;
   escape as `%%TEMP%%`.

6. **POSIX-only `os` calls** — `os.fork`, `os.setsid`, `os.setpgid`, `os.setpgrp`, `os.killpg`,
   `os.wait3`, `os.wait4`, `os.chroot`, `os.chown`, `os.ttyname`. Must route through
   `_platform.spawn_detached` / `_platform.kill_process_tree` or be guarded by `IS_WINDOWS`
   branches.

7. **Subprocess kwargs** — `start_new_session=True` (POSIX-only), `preexec_fn=` (POSIX-only),
   `creationflags=` (Windows-only). Route through `_platform.popen_kwargs_detached` which
   returns the right kwargs for the current platform.

8. **Curses / TTY** — `import curses` works on POSIX (stdlib `_curses` C extension); Windows
   Python doesn't ship `_curses` by default. The TUI must `try: import curses` and on Windows
   `ImportError` print an install hint (`pip install textual` recommended; `pip install
   windows-curses` minimum) and fall back to the non-interactive `--dump runs` text renderer.

### Test contract

- **Unit + integration suite MUST pass on all three platforms** (Linux/macOS via developer
  machines; Windows via Andrew's acceptance fire until automated CI exists).
- **Subprocess/fork tests MUST be verified under BOTH `unittest discover` AND `pytest`**
  (methodology lesson from 180-FINDING-1: pytest's collector forks differently from
  `unittest`'s discoverer; a re-entry path that works under one runner can deadlock under the
  other).
- **Source-pin sweep tests in `bin/tests/harness/test_platform_compat_180.py`** catch new
  platform-conditional symbol uses at commit time:
  - POSIX-only signals (inverse-membership check against the Windows-available set
    `{SIGABRT, SIGFPE, SIGILL, SIGINT, SIGSEGV, SIGTERM, SIGBREAK, NSIG}` — anything else needs
    a guard).
  - `start_new_session=True` literals.
  - Hardcoded `/tmp/` / `/var/` / `/proc/` / `/dev/` paths.
  - POSIX-only `os` calls.
  - Top-level POSIX-only / Windows-only module imports.
  Mirror this pattern for any new platform-related abstraction added.
- **Auto-detach UX MUST verify the spawned child is alive AND has produced its post-launch
  marker before declaring success to the operator** (methodology lesson from FINDING-4 + 6: the
  parent's banner is a contract — banner only fires when the child has reached a verifiable
  post-launch state).
- **Launch-failure diagnosability**: any launch path failure must leave four correlated forensic
  records: `manifest.json` `terminal_reason` (compact `<exc-repr> at <file>:<line> in <qualname>
  [last step: <X>]`), `run-NN/launch_error.txt` (full traceback), `run-NN/launch.log` (per-step
  JSON-lines breadcrumbs), and `harness_env.json` (python/platform/env-filtered/module-hashes
  snapshot). FINDING-11 through 17 in the 180 chain established this contract.

### QPB-self-audit responsibility

Future QPB-on-QPB bootstrap runs MUST verify cross-platform support as part of the audit:

- **Phase 1 (Explore)** identifies which categories above are exercised by the source under
  review.
- **Phase 3 (Code Review)** checks each subprocess/signal/path/import site against the eight
  categories. Findings of unguarded POSIX-only symbols in non-test production code paths are
  BUG-class findings (not deferrals).
- **Phase 4 (Spec Audit)** confirms the design contract above is honored by the code.
- **Phase 6 (Gate)** — the source-pin sweep tests are the structural enforcement; any new
  POSIX-only or Windows-only symbol use without a guard/annotation fails the gate.

### Adding a new platform

If a fourth platform is added (e.g., FreeBSD, ARM64 Linux variants, Alpine-musl):

1. Extend `bin/harness/_platform.py` to handle the platform's variants of each abstraction.
2. Run the source-pin sweep tests against the new platform's classification — adjust the
   Windows-available signal frozenset (or add a platform-available frozenset) to cover the new
   platform's available signal set.
3. Add the new platform to the supported list at the top of this section.
4. Update `reference_docs/33_cross_platform_support.md` with the new platform's specifics.

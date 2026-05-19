# "What just happened" — run-summary decision tree

*v1.5.7 UX deliverable. Single source of truth for the mandatory `## What just happened` + `### What to do next` block the agent emits at every agent-driven phase boundary and end-of-run terminal it produces. Adopter feedback that motivated this: a Cursor-Auto-mode run on `virtio-install-test-1.5.7` completed Phases 0-2 + 6 with the gate passing on stubbed Phases 3-5 (zero confirmed bugs), and the chat output was technically honest but buried inside dense code-grade prose — a non-power-user could not see "this run did not actually find bugs because the model is too weak." This file fixes that by making the interpretive layer mandatory and plain-English.*

## Scope and contract

After completing **any** agent-driven boundary below, the agent **must** emit a Markdown-rendered block in chat (as the **last** visible content of the phase or run, after any technical artifact summary):

- A single phase (1, 2, 3, 4, 5, or 6) in Mode A multi-pass operation — covered by States P1 / P2 / P3 / P4 / P5 / B / S / C / G / E below.
- A single-pass (full) run — emits the block at every internal phase boundary AND at end-of-run.
- An iteration round (gap / unfiltered / parity / adversarial) — States I and F.
- A recheck — State R.
- An agent-emitted unrecoverable error during Phase 1-6 — State E.
- The D1 Phase 2 preservation terminal — State G.

**Out of scope (the agent cannot emit the block here because no agent context exists):**
- `aborted_missing_docs` triggered by `--require-docs` against an empty `reference_docs/` — `bin/run_playbook.py` aborts before any Phase 1 LLM call. The structured `ERROR: aborted_missing_docs — …` block written to `quality/PROGRESS.md` is the user-visible surface; there is no agent in the loop to emit a chat block. (See `references/code-only-mode.md` → "Opt-out: `--require-docs`".)
- OS-level interruption (SIGKILL, system crash, terminal disconnect) — the agent is gone before it can write anything. Recovery is via the run-state resume semantics in `references/run_state_schema.md` § "Resume semantics"; when the agent next runs, it emits the block for whatever state the resumed run lands in.

Block shape (mandatory at every in-scope boundary):

```
## What just happened

<1-3 sentences of plain English describing what was completed, what wasn't,
and the honest interpretation of the result. NOT a copy of PROGRESS.md or
BUGS.md — an interpretive layer over them.>

### What to do next

<1-3 sentences naming the logical next step, with the exact command or prompt
to use.>
```

The block is **mandatory at every in-scope boundary**. The agent emits it in chat (not just into `quality/PROGRESS.md`) so it renders as Markdown when the user reads the conversation. The block is the **last** visible content in the phase, so adopters always see it bright at the end of scrollback.

Plain-English means: no QPB-internal jargon without a parenthetical gloss. Adopters reading the block for the first time should understand what happened without having to grep the source.

## Detection logic — how the agent picks which run state applies

The classifier is mechanical from the artifact tree and the run-state log. Apply rules in order; the first matching rule wins.

**Where the run-state log lives.** v1.5.7 D3 centralized log emission moved the canonical path to `<repo_dir>/quality/logs/<run-id>/run_state.jsonl`. For runs invoked with `--logs-flat` (or `QPB_LOGS_LEGACY=1`), the legacy v1.5.6 path `<repo_dir>/quality/run_state.jsonl` is used instead. Resolve via the canonical path first; fall back to the legacy path if absent. (`bin/run_state_lib.resolve_run_state_path` implements this fallback; rules below say "the run-state log" to mean "the path that helper returns.")

| Order | Detection rule (read from disk) | Run state |
|------:|---------------------------------|-----------|
| 1 | `<repo_dir>/quality.gate-failed-*/` exists AND was created during this session | **State G** — Phase 2 generation aborted (D1 preservation fired) |
| 2 | The run-state log shows the last event is `error` with `recoverable: false` AND no `run_end status=success` follows | **State E** — Agent-emitted unrecoverable error during Phase 1-6 |
| 3 | `quality/results/recheck-results.json` exists AND was written during this session | **State R** — Recheck complete |
| 4 | `quality/PROGRESS.md` contains a `^## Iteration: adversarial complete$` heading AND the prior three headings (`gap complete`, `unfiltered complete`, `parity complete`) are also present | **State F** — All four iteration strategies complete |
| 5 | `quality/PROGRESS.md` contains at least one `^## Iteration: <strategy> complete$` heading for any of `gap` / `unfiltered` / `parity` / `adversarial`, but not all four | **State I** — One or more iteration strategies complete |
| 6 | The run-state log shows `phase_end phase=6` AND `quality/results/quality-gate.log` exists AND `quality/BUGS.md` has zero `^### BUG-` headings AND `quality/results/quality-gate.log` contains the literal WARN string `No ### BUG-NNN headings found in BUGS.md` | **State S** — Phases 1-6 all ran, but Phases 3-5 stubbed (pass-process / fail-recall) |
| 7 | The run-state log shows `phase_end phase=6` AND `quality/results/quality-gate.log` contains the literal line `RESULT: GATE PASSED WITH CLEANUP NEEDED` | **State CN** — Phases 1-6 complete; the review ran and the bug findings stand, but the audit trail has record-keeping gaps (089c F15) |
| 8 | The run-state log shows `phase_end phase=6` AND `quality/BUGS.md` has at least one `^### BUG-` heading | **State B** — Phases 1-6 baseline complete with N confirmed bugs |
| 9 | The run-state log shows `phase_end phase=1` AND a `documentation_state state=code_only` event AND no `phase_end phase=2` event yet | **State C** — Phase 1 completed in code-only mode |
| 10 | The run-state log shows `phase_end phase=N` (N ∈ {1, 2, 3, 4, 5}) AND no `phase_end phase=N+1` AND no abort terminal | **State P<N>** — Phase N just completed cleanly (use the matching State P1 / P2 / P3 / P4 / P5 template below) |

Rules 1, 2, 6, 7, and 9 are the load-bearing branches for adopter UX:
- Rule 1 (**State G**) covers the v1.5.7 D1 deliverable's preservation surface so adopters don't think their data is gone.
- Rule 2 (**State E**) covers agent-emitted unrecoverable errors mid-phase so adopters get a useful chat artifact rather than a silent abort.
- Rule 6 (**State S**) is the original Cursor-Auto-mode failure mode this contract was authored to expose. Rule 6 fires BEFORE Rule 8 so a Phase 6 run with zero confirmed bugs is correctly identified as pass-process / fail-recall rather than mis-classified as State B "complete with N=0 bugs."
- Rule 7 (**State CN**) is the 089c F15 adopter-UX branch: when the gate returns `RESULT: GATE PASSED WITH CLEANUP NEEDED`, the review completed and the bug findings are real — only the audit-trail paperwork is incomplete. Rule 7 fires BEFORE Rule 8 so a cleanup-needed run is NOT mis-emitted as a plain State B "all clear" (the adopter must see the cleanup distinction, not a flat PASS). It cannot collide with Rule 6 — State S is the zero-bug stub case, whereas a cleanup-needed run has real findings with record-keeping gaps. (The state letter is **CN**, not **C**: **C** is already assigned to the code-only-Phase-1 framing in Rule 9. Instruction 089c suggested "State C"; that label was taken, so this is **State CN** to avoid the collision.)
- Rule 9 (**State C**) is the code-only-mode-specific framing so adopters who skipped `reference_docs/` get the documented weaker-recall caveat surfaced explicitly. Rule 9 fires only at the Phase 1 boundary; later boundaries in a code-only run use State P<N> (the agent already surfaced the caveat at State C and the run continues with it acknowledged).

## Decision tree — what the block says when

For each run state, use the template prose and adapt the phrasing to the actual artifact counts and timestamps from disk. **Do not invent counts.** If a number isn't in PROGRESS.md / BUGS.md / the run-state log / recheck-results.json, omit it.

### State P1 — Phase 1 only completed (Mode A multi-pass)

```
## What just happened

Phase 1 (Explore) is done. The agent read your codebase, ingested `reference_docs/` if
present, and produced candidate findings in `quality/EXPLORATION.md`. No bugs are confirmed
yet — confirmation happens in Phase 3 (code review).

### What to do next

Continue with Phase 2 by saying `keep going` or `run phase 2`.
```

### State P2 — Phase 2 just completed

```
## What just happened

Phase 2 (Generate) is done. The agent produced REQUIREMENTS.md, QUALITY.md, CONTRACTS.md,
COVERAGE_MATRIX.md, the four `RUN_*.md` review-protocol files, and the functional-test
harness under `quality/`. Still no confirmed bugs — Phase 3 is the first phase that
emits BUG-NNN records.

### What to do next

Continue with Phase 3 (Code Review) by saying `keep going` or `run phase 3`.
```

### State P3 — Phase 3 just completed

```
## What just happened

Phase 3 (Code Review) is done. The agent executed RUN_CODE_REVIEW.md / RUN_INTEGRATION_TESTS.md /
RUN_SPEC_AUDIT.md / RUN_TDD_TESTS.md, and any confirmed defects landed as `### BUG-NNN`
sections in `quality/BUGS.md` with red-phase TDD logs at `quality/results/BUG-NNN.red.log`.

### What to do next

Continue with Phase 4 (Spec Audit + Triage) by saying `keep going` or `run phase 4`.
```

### State P4 — Phase 4 just completed

```
## What just happened

Phase 4 (Spec Audit + Triage) is done. The agent ran the Council-of-Three semantic
audit on each Tier 1/2 REQ's `citation_excerpt` from `quality/requirements_manifest.json`
and wrote per-REQ review verdicts (one row per Council member per REQ) to
`quality/citation_semantic_check.json`. Any REQs whose `reviews[]` array is empty
were flagged as Spec Gaps for Phase 5 reconciliation.

### What to do next

Continue with Phase 5 (Reconciliation) by saying `keep going` or `run phase 5`.
```

### State P5 — Phase 5 just completed

```
## What just happened

Phase 5 (Reconciliation) is done. The agent reconciled the Phase 3 review findings with
the Phase 4 audit, hydrated every BUGS.md entry with its writeup, regression-test patch,
and inline fix diff, and ran `quality_gate.py` to mechanically validate the artifact set.
All FAIL findings from the gate were addressed before this phase closed.

### What to do next

Continue with Phase 6 (Verify) by saying `keep going` or `run phase 6`.
```

### State C — Phase 1 completed in code-only mode (no `reference_docs/`)

```
## What just happened

Phase 1 (Explore) finished, but in **code-only mode** — no documentation was found at
`reference_docs/`. Requirements will be derived from the source tree alone, which
produces weaker bug recall: requirements end up describing what the code already does,
so the spec-vs-code gap mostly disappears (the "derive-from-code" failure mode in
`ai_context/TOOLKIT.md`).

### What to do next

Either (a) add documentation to `reference_docs/` — specs, design docs, RFCs, AI chat
transcripts; see `ai_context/TOOLKIT.md` "Step 2: Provide documentation" — and re-run
from Phase 1; or (b) continue with the weaker-recall limitation explicitly acknowledged
in your downstream report.
```

### State G — Phase 2 generation aborted (D1 preservation fired)

```
## What just happened

Phase 2 (Generate) aborted before producing the full artifact set. The failed
`quality/` directory was preserved at `<repo_dir>/quality.gate-failed-<UTC-timestamp>/`
so you can inspect what the agent produced before the abort. The gate's diagnostic
explains why it rejected the artifacts.

### What to do next

Inspect `quality.gate-failed-*/` (especially `GATE_FAILURE.md`) and the run logs at
`<repo_dir>/quality.gate-failed-*/logs/<run-id>/` (or the legacy flat-log path if
`--logs-flat` was passed) for the gate diagnostic. Common causes: missing
`reference_docs/`, malformed role map, agent skipped a required artifact. Address the
cause and re-run from Phase 1.
```

### State E — Agent-emitted unrecoverable error during Phase 1-6

```
## What just happened

Phase <N> hit an unrecoverable error (`error recoverable=false` event in the run-state
log). The run did NOT complete the phase, and downstream phases will not execute against
the partial output. The error message is in the run-state log — `<repo_dir>/quality/logs/<run-id>/run_state.jsonl`
canonical (v1.5.7 D3), or `<repo_dir>/quality/run_state.jsonl` legacy fallback if
`--logs-flat` / `QPB_LOGS_LEGACY=1` was set; resolve via `bin/run_state_lib.resolve_run_state_path`
per the "Where the run-state log lives" paragraph above. Read the last `error` event in
that file. Any partial artifacts the agent wrote are still under `<repo_dir>/quality/`.

### What to do next

Read the last `error` event in the run-state log to see the failure reason. Address the
underlying cause (missing tool, wrong PYTHONPATH, model rate-limit, etc.) and re-run
from the start of the phase that aborted. If the error is structural (e.g., the project
is genuinely unprocessable in the current mode), consider opening an issue at
github.com/anthropics/quality-playbook with the error block and the project's
characteristics.
```

### State S — Phases 1-6 all ran, but Phases 3-5 stubbed (zero confirmed bugs, gate passes with WARN)

This is the load-bearing state — the one the v1.5.7 UX defect was filed against. Be especially careful to use plain English here.

```
## What just happened

Phases 1-2 produced real artifacts, but Phases 3-5 wrote stubs and **zero bugs were
confirmed**. This is the documented **pass-process / fail-recall** failure mode
(`ai_context/DEVELOPMENT_CONTEXT.md` → "Known agent behavior differences"): the model
running this session wasn't powerful enough to do real three-pass code review and
multi-model spec audit. The gate caught it as a WARN ("No ### BUG-NNN headings found in
BUGS.md", emitted to `quality/results/quality-gate.log`) — that WARN is the signal.

**Gate witness (REQUIRED — do not omit, do not paraphrase):** paste the
final two lines of `quality/results/quality-gate.log` verbatim:

    Total: N FAIL, M WARN
    RESULT: GATE PASSED
       (or: RESULT: GATE PASSED WITH CLEANUP NEEDED — N audit record-keeping gap(s)
        or: RESULT: GATE FAILED — N substantive issue(s) must be fixed)

In this State S case the gate typically shows `0 FAIL` with `M≥1 WARN`
and `RESULT: GATE PASSED` — but a GATE PASSED here does NOT mean a
successful bug-finding run: the no-`### BUG-NNN`-headings WARN is the
pass-process / fail-recall signal. You may NOT report this run as a
successful "complete" / "PASS" baseline. If the `RESULT:` line shows
`GATE FAILED — N substantive issue(s) must be fixed`, the verdict is
FAIL — list the failing checks. (A zero-bug stub run does not reach
`GATE PASSED WITH CLEANUP NEEDED` — that state needs real findings
with record-keeping gaps; if you somehow see it here, emit State CN,
not State S.) If `quality/results/quality-gate.log` is empty or
missing these two lines the gate never ran — re-run it before emitting
this block.

### What to do next

Switch to a more capable model. From a Quality Playbook clone, run
`python3 -m bin.run_playbook --claude --model sonnet <target>` (or `--codex` /
`--copilot` with a current production model). Or continue Mode A here with Claude Code
Sonnet, GPT-5.4+, or similar. Note that Auto-mode in Cursor and other tools tends to
pick a weaker model than the playbook needs.
```

### State CN — Phases 1-6 complete, PASSED WITH CLEANUP NEEDED (089c F15)

The review ran and the bug findings are real and stand on their own — only
the audit trail has record-keeping gaps. Use this state, NOT State B, when
`quality/results/quality-gate.log` ends with `RESULT: GATE PASSED WITH
CLEANUP NEEDED`. (State letter is **CN** because **C** is the code-only
Phase-1 state; instruction 089c said "State C" but that label was taken —
see the classifier prose for Rule 7.) Substitute the real numbers from
`quality/BUGS.md`, `quality/REQUIREMENTS.md`, and the gate output.

```
## Quality Playbook Run Complete — PASSED WITH CLEANUP NEEDED

The Quality Playbook reviewed your code and found N real bugs. Each bug has
reproduction steps and is traceable to a requirement, and TDD verification
confirmed all N (red->green cycles). The findings stand on their own — this
result is NOT a failure.

### Quality findings (complete)
- N bugs confirmed, each with a reproduction and a fix diff
- R requirements derived from the codebase
- Bug -> requirement traceability verified
- TDD verification: N/N red->green cycles

### Audit record-keeping (needs cleanup)
The gate flagged K audit record-keeping gap(s). Typical gaps:
- some bugs are missing their per-bug challenge record
  (the note that explains why each bug matters and why a fix is right)
- a requirement is missing descriptive fields used by future audits
  to find related work
- some requirements need cross-site pattern tags
- the role-map summary is missing its breakdown numbers

The review is done; the bug findings stand on their own. These gaps are
about the audit trail, not about your code's quality.

**Gate witness (REQUIRED — do not omit, do not paraphrase):** paste the
final two lines of `quality/results/quality-gate.log` verbatim:

    Total: N FAIL, M WARN
    RESULT: GATE PASSED WITH CLEANUP NEEDED — K audit record-keeping gap(s)

(If that log is empty or the `RESULT:` line is anything else, this is the
wrong state — re-read the classifier. A `RESULT: GATE FAILED — N
substantive issue(s) must be fixed` line is a real FAIL, not cleanup.)

### Recommended next step

Ask your AI assistant to complete the audit records. The bug findings
will not change — only the record-keeping fills in. Copy-paste this:

  Please complete the audit record-keeping gaps in the quality/ folder
  that the Quality Playbook flagged. Don't change any bug findings or
  requirements — just fill in the missing record fields, add the missing
  challenge records, and add the cross-site pattern tags. The current
  state is the audit trail of what was done; complete it without
  altering it.
```

### State B — Phases 1-6 baseline complete with N confirmed bugs

Substitute the actual bug count `N` from `quality/BUGS.md` (count `^### BUG-` headings).

```
## What just happened

Full baseline run complete. Found N confirmed bugs (writeups in `quality/writeups/`,
patches in `quality/patches/`, TDD verification in `quality/results/`).

**Gate witness (REQUIRED — do not omit, do not paraphrase):** paste the
final two lines of `quality/results/quality-gate.log` verbatim:

    Total: N FAIL, M WARN
    RESULT: GATE PASSED
       (or: RESULT: GATE PASSED WITH CLEANUP NEEDED — N audit record-keeping gap(s)
        or: RESULT: GATE FAILED — N substantive issue(s) must be fixed)

Read the `RESULT:` line and report per the 089c F15 three-state rule:

- `RESULT: GATE PASSED` — the review is complete and every audit
  record is in place. Report a clean run with N confirmed bugs.
- `RESULT: GATE PASSED WITH CLEANUP NEEDED — N audit record-keeping
  gap(s)` — the bug findings are real, reviewed, and stand on their
  own; only the audit trail (missing manifest fields, missing per-bug
  challenge records, missing cross-site pattern tags) is incomplete.
  Do NOT report a flat "all clear" — emit **State CN** instead; it
  walks the adopter through the cleanup.
- `RESULT: GATE FAILED — N substantive issue(s) must be fixed` — the
  run's verdict is **FAIL** regardless of how many bugs you confirmed.
  Say so explicitly and list the failing checks. The agent may
  NOT claim PASS, PASS WITH CLEANUP NEEDED, "complete", or "no
  remaining work" when there are any substantive FAILs.

If `quality/results/quality-gate.log` is empty or missing these two
lines the gate never ran — re-run it before emitting this block.

### What to do next

Read `quality/BUGS.md` for the consolidated bug report. To find more bugs, run
iterations — the recommended cycle is gap → unfiltered → parity → adversarial and
typically adds 40-60% more bugs. Start with `run the next iteration using the gap
strategy`.
```

### State I — One or more iteration strategies complete

Substitute `<strategy>` with the strategy just completed (`gap` / `unfiltered` / `parity` / `adversarial`) — the one named in the most recent `## Iteration: <strategy> complete` heading in `quality/PROGRESS.md` — and `N` with the cumulative confirmed-bug count. `<next>` is whichever strategy comes next per the canonical cycle, or "the next strategy" if you're not certain.

```
## What just happened

Iteration `<strategy>` complete. Total confirmed bugs across baseline + iterations so
far: N.

### What to do next

Run the next iteration: `run the <next> iteration` (or `recheck` if you're done with
iterations and want to verify fixes). Or read `quality/BUGS.md` and start applying
patches.
```

### State F — All four iteration strategies complete

```
## What just happened

Full baseline run plus all four iteration strategies (gap, unfiltered, parity,
adversarial) complete. Found N confirmed bugs total. The four strategies cover the
documented bug classes — additional iterations rarely produce new bugs.

### What to do next

Review `quality/BUGS.md` and apply patches from `quality/patches/`. After fixing the
underlying code, say `recheck` to verify your fixes against the source. The
regression-test patches in `quality/patches/` are portable; you can carry them
upstream when submitting PRs.
```

### State R — Recheck complete

Substitute `M` / `K` / `J` with the FIXED / OPEN / INCONCLUSIVE counts from `quality/results/recheck-results.json`.

```
## What just happened

Recheck verified your fixes. **M bugs FIXED**, K still OPEN, J INCONCLUSIVE. Detailed
results in `quality/results/recheck-results.json` and the plain-English summary in
`quality/results/recheck-summary.md`.

### What to do next

Address the K still-open bugs. Open PRs for the M fixed bugs (the regression-test
patches in `quality/patches/` are portable — adopt them upstream so the maintainer can
verify the fix). After the next fix batch, say `recheck` again.
```

## DO NOT

- **Do not** summarize `quality/PROGRESS.md` verbatim. PROGRESS.md is machine-readable status; this block is interpretive plain English. They are different surfaces.
- **Do not** invent bugs that aren't in `quality/BUGS.md`. Count `^### BUG-` headings; if zero, say "zero confirmed bugs" — do not pad.
- **Do not** omit the block when the chat output is constrained (e.g., near a context limit). The block is the highest-value last output; truncate the technical artifact summary above it if needed, never the block itself.
- **Do not** use QPB-internal jargon without glossing it. "Phase 2 (Generate)" not "Phase 2." "Pass-process / fail-recall failure mode" only with the parenthetical doc pointer. "Role map" not just "the map."
- **Do not** lead with QPB-internal phrasing. The first sentence of "What just happened" should make sense to an adopter reading their first run.
- **Do not** write the "What to do next" sentence without a concrete next prompt or shell command. The whole purpose is to remove "what do I type now?" friction.
- **Do not** rewrite this decision tree inline in SKILL.md or in any phase prompt. Single-source: SKILL.md and phase prompts point at this file; this file owns the templates.
- **Do not** add new run states beyond the thirteen defined here (P1, P2, P3, P4, P5, C, G, E, S, B, I, F, R) without an instruction-authorized scope change. New states queue for v1.6.0+.
- **Do not** invoke this contract for the out-of-scope cases listed in "Scope and contract" above (`aborted_missing_docs` shell abort; SIGKILL; OS crash). Those terminals have no agent in the loop.

## Cross-references

- Contract enforcement at the orchestration spine: `SKILL.md` → "What just happened" section.
- Phase-level emission instruction: each `phase_prompts/*.md` tail line.
- Iteration-prompt emission: `phase_prompts/iteration.md` tail line (loaded by `bin/run_playbook.py::iteration_prompt`).
- Code-only-mode framing: `references/code-only-mode.md`.
- Pass-process / fail-recall doc background: `ai_context/DEVELOPMENT_CONTEXT.md` → "Known agent behavior differences" + `ai_context/TOOLKIT.md` → "Why bug counts depend on agent quality."
- D1 preservation mechanics: `bin/run_playbook.py::_preserve_quality_on_gate_failure` (invoked from `run_one_phase()`) + `ai_context/BENCHMARK_PROTOCOL.md` → "Phase 2 abort preservation (v1.5.7+)."
- D3 centralized log layout (canonical location of the run-state log): `references/run_state_schema.md` § "File locations and ownership" + `ai_context/TOOLKIT.md` → "Centralized run logs (v1.5.7+)."
- Run-state event taxonomy (the events Rules 1-9 read against): `references/run_state_schema.md` § "Per-run events."
- `aborted_missing_docs` shell-abort surface (out of scope here; PROGRESS.md ERROR block is the user surface): `references/code-only-mode.md` → "Opt-out: `--require-docs`" + `references/run_state_schema.md` § "`aborted_missing_docs`."
- Resume semantics after SIGKILL / crash (recovery emits a State P<N> / S / B / G / E / R block once the agent resumes): `references/run_state_schema.md` § "Resume semantics."

## Provenance

Authored v1.5.7 (instruction 037, 2026-05-14) as the closure of the Cursor-Auto-mode adopter-UX defect. Hardened v1.5.7 (instruction 038, 2026-05-14) after a codex focused review surfaced six findings — the v1.5.7 D3 run-state-log path was inconsistent with the canonical location, the `iteration_log.json` artifact didn't exist, the State S detector pointed at the wrong file (`quality/gate_output.txt` not a real artifact; the canonical gate output is `quality/results/quality-gate.log` with the literal WARN string `No ### BUG-NNN headings found in BUGS.md`), the State Pn fallback didn't have explicit P2-P5 templates so the phase prompts referenced templates that didn't exist, the single-pass State C wording could be misread as applying past the Phase 1 boundary, and the contract claimed "every run" without acknowledging the agent-less abort cases. Round 1 fix-up added explicit P2-P5 templates, added State E (agent-emitted unrecoverable error), reordered rules so State S correctly fires before State B, narrowed Rule 8 to Phase 1 only, and added the out-of-scope clarification for `aborted_missing_docs` / SIGKILL / OS crash.

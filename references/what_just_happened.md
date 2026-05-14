# "What just happened" — run-summary decision tree

*v1.5.7 UX deliverable. Single source of truth for the mandatory `## What just happened` + `### What to do next` block the agent emits at every phase boundary and at the end of every run. Adopter feedback that motivated this: a Cursor-Auto-mode run on `virtio-install-test-1.5.7` completed Phases 0-2 + 6 with the gate passing on stubbed Phases 3-5 (zero confirmed bugs), and the chat output was technically honest but buried inside dense code-grade prose — a non-power-user could not see "this run did not actually find bugs because the model is too weak." This file fixes that by making the interpretive layer mandatory and plain-English.*

## Contract

After completing **any** of:

- A single phase (1, 2, 3, 4, 5, or 6) in Mode A multi-pass operation
- A single-pass (full) run
- An iteration round (gap / unfiltered / parity / adversarial)
- A recheck

the agent **must** emit, as the **last** output of the phase or run, a Markdown-rendered block of this shape in chat:

```
## What just happened

<1-3 sentences of plain English describing what was completed, what wasn't,
and the honest interpretation of the result. NOT a copy of PROGRESS.md or
BUGS.md — an interpretive layer over them.>

### What to do next

<1-3 sentences naming the logical next step, with the exact command or prompt
to use.>
```

The block is **mandatory**. The agent emits it in chat (not just into `quality/PROGRESS.md`) so it renders as Markdown when the user reads the conversation. The block is the **last** visible content in the phase, so adopters always see it bright at the end of scrollback.

Plain-English means: no QPB-internal jargon without a parenthetical gloss. Adopters reading the block for the first time should understand what happened without having to grep the source.

## Detection logic — how the agent picks which run state applies

The classifier is mechanical from the artifact tree and `quality/run_state.jsonl` events. Apply rules in order; the first matching rule wins.

| Order | Detection rule (read from disk) | Run state |
|------:|---------------------------------|-----------|
| 1 | `<repo_dir>/quality.gate-failed-*/` exists AND was created during this session | **State G** — Phase 2 generation aborted (D1 preservation fired) |
| 2 | `quality/results/recheck-results.json` exists AND was written during this session | **State R** — Recheck complete |
| 3 | `quality/iteration_log.json` or `quality/run_state.jsonl` shows `iteration_end strategy=adversarial` AND the prior three iterations (`gap`, `unfiltered`, `parity`) all show `iteration_end` events | **State F** — All four iteration strategies complete |
| 4 | `quality/run_state.jsonl` shows at least one `iteration_end` event for any of `gap` / `unfiltered` / `parity` / `adversarial`, but not all four | **State I** — One or more iteration strategies complete |
| 5 | `quality/run_state.jsonl` shows `phase_end phase=6` AND `quality/BUGS.md` has at least one `^### BUG-` heading | **State B** — Phases 1-6 baseline complete with N confirmed bugs |
| 6 | `quality/run_state.jsonl` shows `phase_end phase=6` BUT `quality/BUGS.md` has zero `^### BUG-` headings AND the gate's verdict file (`quality/gate_output.txt` or `quality/INDEX.md::gate_verdict`) shows the "no BUG-NNN headings" WARN | **State S** — Phases 1-2 done, Phases 3-5 stubbed (pass-process / fail-recall) |
| 7 | `quality/run_state.jsonl` shows `phase_end phase=1` AND a `documentation_state state=code_only` event AND no `phase_end phase=2` event yet | **State C** — Phase 1 completed in code-only mode |
| 8 | `quality/run_state.jsonl` shows `phase_end phase=1` AND no `phase_end phase=2` event yet | **State P1** — Phase 1 only completed (Mode A multi-pass) |
| 9 | Any other phase boundary with a clean `phase_end phase=N` event and no abort | **State Pn** — Phase N just completed (use the State P1 template with the phase number substituted, plus an interim "next step is Phase N+1" instruction) |

Rules 6 and 7 are the load-bearing additions for adopter UX:
- Rule 6 (**State S**) is the original Cursor-Auto-mode failure mode this contract was authored to expose.
- Rule 7 (**State C**) is the code-only-mode-specific framing so adopters who skipped `reference_docs/` get the documented weaker-recall caveat surfaced explicitly.

## Decision tree — what the block says when

For each run state, use the template prose and adapt the phrasing to the actual artifact counts and timestamps from disk. **Do not invent counts.** If a number isn't in PROGRESS.md / BUGS.md / iteration_log.json / run_state.jsonl, omit it.

### State P1 — Phase 1 only completed (Mode A multi-pass)

```
## What just happened

Phase 1 (Explore) is done. The agent read your codebase, ingested `reference_docs/` if
present, and produced candidate findings in `quality/EXPLORATION.md`. No bugs are confirmed
yet — confirmation happens in Phase 3 (code review).

### What to do next

Continue with Phase 2 by saying `keep going` or `run phase 2`.
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

### State S — Phases 1-2 done, Phases 3-5 stubbed (zero confirmed bugs, gate passes with WARNs)

This is the load-bearing state — the one the v1.5.7 UX defect was filed against. Be especially careful to use plain English here.

```
## What just happened

Phases 1-2 produced real artifacts, but Phases 3-5 wrote stubs and **zero bugs were
confirmed**. This is the documented **pass-process / fail-recall** failure mode
(`ai_context/DEVELOPMENT_CONTEXT.md` → "Known agent behavior differences"): the model
running this session wasn't powerful enough to do real three-pass code review and
multi-model spec audit. The gate caught it as a WARN ("no `### BUG-NNN` headings") —
that WARN is the signal.

### What to do next

Switch to a more capable model. From a Quality Playbook clone, run
`python3 -m bin.run_playbook --claude --model sonnet <target>` (or `--codex` /
`--copilot` with a current production model). Or continue Mode A here with Claude Code
Sonnet, GPT-5.4+, or similar. Note that Auto-mode in Cursor and other tools tends to
pick a weaker model than the playbook needs.
```

### State B — Phases 1-6 baseline complete with N confirmed bugs

Substitute the actual bug count `N` from `quality/BUGS.md` (count `^### BUG-` headings).

```
## What just happened

Full baseline run complete. Found N confirmed bugs (writeups in `quality/writeups/`,
patches in `quality/patches/`, TDD verification in `quality/results/`).

### What to do next

Read `quality/BUGS.md` for the consolidated bug report. To find more bugs, run
iterations — the recommended cycle is gap → unfiltered → parity → adversarial and
typically adds 40-60% more bugs. Start with `run the next iteration using the gap
strategy`.
```

### State I — One or more iteration strategies complete

Substitute `<strategy>` with the strategy just completed (`gap` / `unfiltered` / `parity` / `adversarial`) and `N` with the cumulative confirmed-bug count. `<next>` is whichever strategy comes next per the canonical cycle, or "the next strategy" if you're not certain.

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
- **Do not** add new run states beyond the eight defined here without an instruction-authorized scope change. New states queue for v1.6.0+; the eight defined states cover every Mode A / single-pass / iteration / recheck terminal we ship in v1.5.7.

## Cross-references

- Contract enforcement at the orchestration spine: `SKILL.md` → "What just happened" section.
- Phase-level emission instruction: each `phase_prompts/*.md` tail line.
- Iteration-prompt emission: `phase_prompts/iteration.md` tail line (loaded by `bin/run_playbook.py::iteration_prompt`).
- Code-only-mode framing: `references/code-only-mode.md`.
- Pass-process / fail-recall doc background: `ai_context/DEVELOPMENT_CONTEXT.md` → "Known agent behavior differences" + `ai_context/TOOLKIT.md` → "Why bug counts depend on agent quality."
- D1 preservation mechanics: `bin/run_playbook.py::_finalize_quality_layout` + `ai_context/BENCHMARK_PROTOCOL.md` → "Phase 2 abort preservation (v1.5.7+)."
- D3 centralized log layout: `references/run_state_schema.md` + `ai_context/TOOLKIT.md` → "Centralized run logs (v1.5.7+)."

## Provenance

Authored v1.5.7 (instruction 037, 2026-05-14) as the closure of the Cursor-Auto-mode adopter-UX defect. Prior to this file, the agent's end-of-phase output was implicit (each phase prompt mentioned a closing summary in different words). This file canonicalizes the contract and gives the agent unambiguous templates so the failure modes adopters most often hit (especially **State S** — pass-process / fail-recall on weak models) get surfaced bright instead of buried.

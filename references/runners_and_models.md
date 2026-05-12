# Runners and Models — adopter background

*v1.5.7 Deliverable 6e. Stable conceptual reference for the four AI
runners QPB supports + why the Council-of-Three exists.
Deliberately omits a model-availability matrix; runtime model
knowledge is the orchestrating LLM's job, not this document's.*

## Why this document exists

QPB invokes external AI runners to execute phase prompts (Phase 1-5)
and to launch the Council of Three (Phase 4 audit). Adopters new to
QPB ask three recurring questions:

1. **Which runner should I use?** (`claude-cli`, `gh copilot`,
   `codex-cli`, `cursor-cli`)
2. **Why does QPB ship with a Council of Three rather than relying on
   a single reviewer?**
3. **How do I override the default Council roster?**

This document answers each at the conceptual level. It does NOT list
which specific model identifiers each runner supports at any given
date — that's intentionally absent because vendor availability is
volatile (gh copilot silently dropped gemini-2.5-pro support during
the v1.5.6 model-comparison sweep; codex-cli's model lineup shifted
twice in the same quarter). The orchestrating LLM has runtime
knowledge of current model availability; this document carries the
stable conceptual reference instead.

## The four runners

QPB dispatches LLM work through one of four runner CLIs. All four are
external tools that wrap a vendor's chat / completion API behind a
shell-friendly interface.

### `claude-cli` (Anthropic, single-family)

Single-family runner from Anthropic. Authenticates with an
Anthropic API key. Scope: Claude family models only (Opus, Sonnet,
Haiku across versions). QPB's `--claude` flag selects this runner.

Install: see Anthropic's claude-cli documentation. Authentication is
API-key-based via env var or a long-lived auth file.

### `gh copilot` (GitHub, multi-family)

Multi-family runner from GitHub. Distributed as a `gh` CLI extension
(`gh extension install github/gh-copilot`). Scope: spans multiple
model families that GitHub Copilot exposes — Anthropic Claude family,
OpenAI GPT family, occasionally Gemini / other vendors when
available. The exact set is opaque to QPB; the runner accepts model
identifiers as opaque strings and returns errors for unknown ones.
QPB's `--copilot` flag selects this runner. Default runner.

Install: `gh extension install github/gh-copilot`. Authentication
piggybacks on `gh auth` (GitHub login).

### `codex-cli` (OpenAI, single-family)

Single-family runner from OpenAI. Scope: OpenAI's GPT family
(including `codex` variants). QPB's `--codex` flag selects this
runner.

Install: per OpenAI's codex-cli documentation. Authentication via
OpenAI API key.

### `cursor-cli` (Cursor / Anysphere, multi-family)

Multi-family runner from Cursor (Anysphere). Distributed via Cursor's
CLI extension (cursor-cli 3.1+). Scope: multiple model families
mediated through Cursor's runtime selection. QPB's `--cursor` flag
selects this runner.

Install: per Cursor's CLI documentation. Authentication via Cursor's
account login flow.

## Why the Council of Three

The Council-of-Three is QPB's Phase 4 audit mechanism. Three
independent AI reviewers vote on each Tier 1/2 requirement's
citation_excerpt (per `schemas.md` §9 + invariant #17). Why three,
and why model-family diverse?

### Why three (not four, not five, not one)

One reviewer is overreach risk: a single model's blind spots become
the audit's blind spots. Two reviewers can deadlock 1-1, leaving the
gate unable to compute a majority verdict. Three reviewers produce
2-of-3 majorities for every disagreement, and the marginal
information one additional reviewer (going to four or five) provides
falls off sharply — they tend to agree with the existing majority.
Three is the smallest n where every vote resolves; the gate's
invariant #17 is built around this.

### Why model-family diversity matters

Different model families have different training data, different
RLHF objectives, and therefore different blind spots. When three
reviewers from the SAME family disagree, their disagreement is
within one perspective; when they disagree across families, the
disagreement is genuinely cross-perspective. The Council's default
roster combines two Anthropic Claude variants (Opus + Sonnet — same
family but different size class and training stage) with one OpenAI
GPT variant. That's three distinct perspectives at the family level.

The 2-of-2 degradation path (when one reviewer becomes unavailable;
see "Council resilience" below) is acceptable BECAUSE the remaining
two are still cross-family — Claude + GPT, not two GPTs. If the
degradation fell to a single reviewer, the cross-family check would
collapse and the audit would be back to one-perspective overreach
risk. Hence Phase 6's hard-fail at 1-of-3 / 0-of-3.

### Why two-of-three is enough

The Council's vote is 2-of-3 majority per invariant #17. A unanimous
3-of-3 vote is stronger evidence but not required; 2-of-3 with one
dissent is the canonical "majority verdict + flagged dissent"
pattern. The gate records all three votes; downstream Lever
Calibration analysis can revisit dissent patterns over time.

## How to override the Council roster

QPB's default Council roster is defined at
`bin/council_config.py::DEFAULT_COUNCIL_MEMBERS`. Three override
mechanisms exist (in resolution order, most specific first):

1. **CLI flag** (highest precedence): `--council-roster <m1,m2,m3>`
   (planned for v1.5.7 Phase 6c — pending the config-file persistence
   layer).
2. **Per-operator config file** (`~/.qpb/config.yaml`,
   `council_members:` field — planned for v1.5.7 Phase 6c).
3. **Built-in default** (lowest precedence): the
   `DEFAULT_COUNCIL_MEMBERS` tuple in `bin/council_config.py`.

Each override mechanism accepts a list of three model-identifier
strings. The strings are opaque to QPB — the runner interprets them.
Unknown identifiers (typos, models the runner doesn't support)
produce a startup warning when v1.5.7 Phase 6c availability detection
runs; the actual model probe happens at Phase 4 Council launch.

The runtime active roster is surfaced via the cluster-050 Phase 4
banner: when Phase 4 starts, the runner emits a "Phase 4 — Council
of Three" banner naming the active roster strings (read
programmatically from `council_config.council_members()`). Adopters
should consult that banner to confirm the active roster at any given
run.

## Council resilience (Phase 6b — planned)

When the launch infrastructure detects that one Council member is
unavailable (model identifier not recognized by the runner; auth
failure; network timeout), Phase 6b will degrade gracefully to a
2-of-2 vote rather than hard-failing the entire run. The remaining
two reviewers are still cross-family per the rationale above; the
2-of-2 path is documented as acceptable degradation. A
`council_degraded` event is emitted to `run_state.jsonl` so
downstream analysis can identify runs that ran with degraded
composition.

When TWO or THREE members are unavailable, Phase 4 hard-fails. The
failure-recovery template (Phase 6d) is emitted to stderr + the
runner log + a `council_failure_recovery.md` file under the run's
log directory, giving the operator and downstream LLM the
information they need to identify which runner / which model
identifier was unrecognized, and how to override the roster.

This document is updated when Phase 6b lands.

## Pointer to canonical Council infrastructure

- `bin/council_config.py` — canonical roster source. Update this
  module to change the active default roster.
- `bin/council_semantic_check.py` — Layer-2 semantic-check assembler
  used by the Phase 4 audit.
- `phase_prompts/phase4.md` — agent-facing Phase 4 prompt including
  Council launch instructions.
- `schemas.md` §9 + §10 invariant #17 — Council audit schema and
  gate validation rules.
- `docs/design/QPB_v1.5.7_Design.md` Deliverable 6 — design rationale
  for the v1.5.7 Council resilience work.

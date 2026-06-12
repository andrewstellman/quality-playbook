# Staging note — standalone harness doc suite (NOT shipped from QPB)

These four files (`README.md`, `AGENTS.md`, `DEVELOPMENT_CONTEXT.md`,
`TOOLKIT.md`) are the **root documents of the future standalone harness
repo**, staged here ahead of extraction (umbrella tracker item 9) so that
extraction is a *move*, not a writing project.

**They are not part of the QPB plugin and are not installed by anything.**
They live under `plugins/quality-playbook-harness/standalone-docs/` only
until the harness core is extracted to its own repository; at that point
they move to that repo's root (and `DEVELOPMENT_CONTEXT.md`/`AGENTS.md`
reference `docs/REQUIREMENTS.md`, which is `docs/design/QPB_Harness_Requirements.md`
travelling along as the repo's founding requirements doc).

## Name: resolved — `wakecycle`

The product name was decided by the operator on 2026-06-12: **`wakecycle`**
(selection record in `docs/design/QPB_v1.5.9_Design.md` Part 2, decision 1).
Availability was verified natively before the cascade (instruction 013): PyPI
(both `wakecycle` and the dash-normalized form PyPI treats as equivalent),
npm, the GitHub org/user, and GitHub repos are all free; the web sweep found
only non-dev neighbors (the
generic "sleep-wake cycle" term, a music track, a university cycling
program) — no software product, package, or dev tool holds the name.
**Verdict: CLEAN.** The full sweep is recorded in
`runner/1.5.9/outputs/013-wakecycle-verification-and-cascade.md`.

The name-placeholder that these drafts used has been cascaded out:
**lowercase `wakecycle`** for package names, CLI commands, repo references,
identifiers, and file paths; **capitalized `Wakecycle`** for prose
sentence-initial and title usage — never a camel-cased, hyphenated, or
underscored form. **Extraction is unblocked.**

## Conventions in these drafts

- Commands, flags, fields, and behaviors are written against the **shipped
  v1.5.9 code** (`bin/qpb_harness_tick.py`, `bin/harness_ticker.py`,
  `bin/harness_heartbeat.py`, `bin/harness_demo_worker.py`, the harness
  plugin's SKILL/BOOTSTRAP/STATE_MACHINE/schemas/example plan), not from
  memory. At extraction the script names lose their `qpb_`/`harness_`
  prefixes and become the `wakecycle` package's console entry points
  (`wakecycle`, `wakecycle-ticker`, `wakecycle-heartbeat`); the docs already
  use those entry-point names with the current script paths noted where a
  reader needs to run them today.
- Capability claims are labeled **VERIFIED** (evidence-linked) vs
  **DESIGNED** (unverified) per NFR-12. No DESIGNED capability is stated as
  if verified.
- Spec traceability: claims cite `FR-NN` / `NFR-NN` / `UC-N` from the
  requirements doc (`docs/design/QPB_Harness_Requirements.md`).
- The QPB **vendored copy keeps its own identity** — the
  `quality-playbook-harness` plugin and the `qpb_harness_tick.py` /
  `harness_*.py` scripts are NOT renamed. The naming boundary is: standalone
  = `wakecycle`; QPB vendored = unchanged, with a lineage note added at
  extraction time.

## What is deliberately NOT here (later tracker items)

The extraction move itself; packaging files (`pyproject.toml` /
`package.json` — item 10); GitHub repo creation (operator); edits to QPB's
own `ai_context/` orientation docs. These drafts are the writing, done early.

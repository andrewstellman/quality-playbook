# Staging note — standalone harness doc suite (NOT shipped from QPB)

These four files (`README.md`, `AGENTS.md`, `DEVELOPMENT_CONTEXT.md`,
`TOOLKIT.md`) are the **root documents of the future standalone harness
repo**, staged here name-free ahead of extraction (umbrella tracker item 9)
so that extraction is a *move*, not a writing project.

**They are not part of the QPB plugin and are not installed by anything.**
They live under `plugins/quality-playbook-harness/standalone-docs/` only
until the harness core is extracted to its own repository; at that point
they move to that repo's root (and `DEVELOPMENT_CONTEXT.md`/`AGENTS.md`
reference `docs/REQUIREMENTS.md`, which is `docs/design/QPB_Harness_Requirements.md`
travelling along as the repo's founding requirements doc).

## Conventions in these drafts

- **`{{NAME}}`** is the product-name placeholder. The product name is
  undecided (operator deadline: before first publish). Every place the name
  belongs — title, `pip install {{NAME}}`, `npm install {{NAME}}`, the CLI
  entry points `{{NAME}}` / `{{NAME}}-ticker` — uses `{{NAME}}`. A single
  find-replace finishes the docs at naming time. In prose the system is
  called **"the harness."**
- Commands, flags, fields, and behaviors are written against the **shipped
  v1.5.9 code** (`bin/qpb_harness_tick.py`, `bin/harness_ticker.py`,
  `bin/harness_heartbeat.py`, `bin/harness_demo_worker.py`, the harness
  plugin's SKILL/BOOTSTRAP/STATE_MACHINE/schemas/example plan), not from
  memory. At extraction the script names lose their `qpb_`/`harness_`
  prefixes and become the `{{NAME}}` package's console entry points; the
  docs already use the `{{NAME}}` entry-point names with the current script
  paths noted where a reader needs to run them today.
- Capability claims are labeled **VERIFIED** (evidence-linked) vs
  **DESIGNED** (unverified) per NFR-12. No DESIGNED capability is stated as
  if verified.
- Spec traceability: claims cite `FR-NN` / `NFR-NN` / `UC-N` from the
  requirements doc (`docs/design/QPB_Harness_Requirements.md`).

## What is deliberately NOT here (later tracker items)

The extraction move itself; packaging files (`pyproject.toml` /
`package.json` — item 10); the chosen name; edits to QPB's own
`ai_context/` orientation docs. These drafts are the writing, done early.

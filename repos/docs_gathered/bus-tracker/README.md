# bus-tracker Documentation Collection

This directory contains the curated specification material for the `bus-tracker` benchmark target: a small real-time NYC bus arrival tracker that calls the MTA Bus Time SIRI API. It was built in a single Cowork session on 2026-04-10 using Claude, and it is used in QPB as a deliberately tiny target for quick parallel `--full-run` exercises.

## What's in this collection

The documentation is organized as **one verbatim README** plus **six topical spec docs** that extract and consolidate the design decisions from the original build chat. The raw chat itself is preserved for provenance but not staged into `formal_docs/`.

### Topical docs (the Phase-1 intake)

| File | Topic | Size |
|---|---|---|
| `01_project_readme.md` | Verbatim `README.md` from the repo | ~2.4 KB |
| `02_siri_api_endpoint.md` | SIRI StopMonitoring endpoint, URL construction, response shape, sort order | ~5.0 KB |
| `03_api_key_resolution.md` | CLI → env → file precedence, missing-key error, `.api_key` path semantics | ~3.5 KB |
| `04_config_schema.md` | `config.json` top-level and per-stop schema, format rules, fatal-error cases | ~4.7 KB |
| `05_walk_time_gating.md` | 4-state buffer machine, hardcoded thresholds (0/2/5), CLI-vs-web parity | ~4.4 KB |
| `06_cli_and_web_modes.md` | CLI one-shot vs `--web` dashboard, port 5555, 30 s refresh, stdlib-only constraint | ~6.5 KB |
| `07_error_handling.md` | Fatal startup errors, upstream structured errors, semantic-vs-empty ambiguity | ~6.0 KB |

Each topical file is structured the same way:

1. **Source line** — which code paths / docs / chat sections the content comes from.
2. **Topic coverage** — concrete design decisions, values, and code behavior.
3. **Spec-auditor focus** — explicit bullets for QPB Phase 4/5 checks.
4. **What's NOT in scope** — out-of-scope clarifications so reviewers don't hallucinate missing features.

### Provenance files

| File | Role |
|---|---|
| `INDEX.md` | Per-file behavioral summary for quick navigation |
| `README.md` | This file |
| `sources.md` | Where each document came from; duplication findings |
| `_raw/project_chat_history.md` | Full 2026-04-10 Cowork build chat (preserved, not staged) |

The `_raw/` subdirectory is **deliberately excluded from `formal_docs/` staging**. `stage_formal_docs.py` iterates `docs_gathered/<repo>/` with `if not entry.is_file(): continue`, so subdirectories and hidden files are skipped. The raw chat remains available for manual inspection but doesn't bloat Phase 1's context.

## Why the structure changed on 2026-04-21

The original collection contained `02_project_chat_history.md` — the full 121 KB, 4,556-line Cowork chat pasted verbatim. That file turned out to be **~50% duplicated** (lines 1–1262 repeat as lines 1263–2524) and, more importantly, dominated Phase-1 and Phase-2 token cost on a repo whose actual source is ~500 lines of Python.

The 2026-04-21 `bus-tracker-1.5.0` full-run took 55 minutes for the main phases — disproportionate to the project size. A chunk of that is plausibly the huge, redundant chat file being re-read across phases. This curation replaces the chat with six focused topical docs totaling ~30–35 KB, while preserving the raw chat under `_raw/` for manual reference.

## Why bus-tracker is a benchmark target

- **Tiny.** Single Python file (~17 KB, ~491 lines), standard library only, one config file, one README.
- **Owned end-to-end by the QPB author.** Andrew built this on 2026-04-10 in a single Cowork session, so the full design conversation is available as a genuine Tier 1/2 input — not reconstructed after the fact.
- **Real external API surface.** Talks to the MTA SIRI API, so there are real behavioral specs to audit against (route filter format, stop-id format, arrival-time prediction semantics, etc.).
- **Two interaction modes.** CLI and HTTP dashboard — gives QPB two surfaces to explore without a lot of code.
- **Good divergence-model target.** Explicit decisions that are easy to cross-check against the source: the "no pip install" constraint, default port 5555, 30-second refresh cadence, `walk_minutes`-based gating with hardcoded 0/2/5 thresholds, `.api_key` fallback.

Not in the default benchmark sweep — this target exists specifically for fast parallel `--full-run` exercises and v1.5.x development smoke-testing, not for sign-off evidence.

## Last updated

2026-04-21 (restructured from single-chat to six topical docs)

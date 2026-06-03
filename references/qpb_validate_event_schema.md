# `bin/qpb_validate.py` `event=` line schema

`bin/qpb_validate.py` (the Phase 0 install validator) emits one
structured line per event to stdout. Agents are instructed to paste
these verbatim into chat so the run-nonce witness contract (§3.4)
can be cross-referenced. This document is the stable contract for
adopters who pattern-match those lines.

## Line grammar

Every line has the shape:

```
event=<name> nonce=<run-nonce> <field>=<value> <field>=<value> ...
```

- `event=` is always first; `nonce=` is always second (the run-nonce
  disk-witness stamp — §3.4). Remaining fields follow in a
  deterministic per-event order.
- Values are escaped (whitespace/`=` safe) by `_escape_value`.

## Events and their fields

| `event=` | Required fields (beyond `event` + `nonce`) | Notes |
|---|---|---|
| `invocation_context` | `location`, `root` | `witness` present on the main (non-early-refusal) path |
| `platform_detected` | `kind`, `shell` | |
| `target_resolved` | `target` | plus `markers` (multi-marker refusal path) OR `marker` + `ai_tool` (main path) |
| `package_managers` | `brew`, `apt`, `dnf`, `winget`, `choco` | each `yes`/`no` |
| `install_hygiene_check` | `path`, `kind`, `status`, `detail` | A-20 stale-quality |
| `closure_check` | `path`, `kind`, `status`, `detail` | INSTALL_CLOSURE |
| `scaffolding_check` | `path`, `kind`, `status`, `detail` | INSTALL_SCAFFOLDING |
| `environment_check` | `path`, `kind`, `status`, `detail` | INSTALL_ENVIRONMENT |
| `remediation_suggestion` | `tool`, `finding`, `severity`, `command`, `rationale`, `verify_with` | one per finding |
| `validation_complete` | `status`, `findings` | `status` ∈ {`ok`,`remediable`,`blocked`}; `ts` (ISO-8601) present on the main paths. THE line adopters pattern-match (`event=validation_complete status=ok`). |
| `info` | `event=info` + context-specific fields | non-finding informational lines (e.g. bash-unavailable, §6.5) |

## Backward-compatibility policy

> Within a minor version, field names are stable and the set of
> `event=` names is stable. New fields may be added in a minor
> version. Removals and renames require a deprecation cycle
> (announced in CHANGELOG one release before the change). Adopters
> consuming these lines via pattern-matching
> (`event=validation_complete status=ok`) can rely on field names;
> adopters consuming via positional parsing or strict whitelisting
> should also pin the version they were written against.

This contract is mechanically pinned by
`bin/tests/test_qpb_validate_event_schema.py` — the set of event
names this doc documents must equal the set
`bin/qpb_validate.py` actually emits, and every
`validation_complete` emission must carry the `status` + `findings`
fields adopters depend on.

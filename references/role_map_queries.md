# Role-map query cookbook

The Phase 1 role map at `quality/exploration_role_map.json` has a top-level
`files` array (NOT a `.roles` object). Each file record is `{path, role,
size_bytes, rationale}`, plus `skill_prose_reference` for `skill-tool` entries.
Roles are taxonomy values defined in `bin/role_map.py::ROLE_DESCRIPTIONS` —
that file is the canonical list. This cookbook does NOT enumerate roles inline
because the cookbook would drift if the taxonomy evolves; the discovery query
at the bottom of this file reads the live role set from a real role map.

The full schema is documented at `schemas.md` §11.1 (`Phase-1 Role Map`).

## Canonical queries

All source-code file paths:

```
jq -r '.files[] | select(.role == "code") | .path' quality/exploration_role_map.json
```

Source files filtered by extension (example: `.c`):

```
jq -r '.files[] | select(.role == "code") | .path' quality/exploration_role_map.json | grep -E '\.c$'
```

All test file paths:

```
jq -r '.files[] | select(.role == "test") | .path' quality/exploration_role_map.json
```

All skill-tool paths with their prose references:

```
jq -r '.files[] | select(.role == "skill-tool") | "\(.path)\t\(.skill_prose_reference)"' quality/exploration_role_map.json
```

Count files by role:

```
jq -r '.files | group_by(.role) | map({role: .[0].role, count: length})' quality/exploration_role_map.json
```

Total bytes by role:

```
jq -r '.files | group_by(.role) | map({role: .[0].role, bytes: ([.[] | .size_bytes] | add)})' quality/exploration_role_map.json
```

## Anti-patterns (DO NOT use)

These are the wrong-guess paths agents have constructed when querying the
role map from intuition rather than the schema. Each one is wrong — they
return empty results, or error depending on the jq invocation. The
empty-result case is the dangerous one, because downstream tooling
typically consumes the empty output without noticing:

- `.roles.source[]` — `.roles` does not exist in the schema. The role map
  has a top-level `.files`, not a `.roles` keyed-by-role object.
- `.roles.code[]` — same root cause; `.roles.<name>` is not the schema.
- `.files.code[]` — `.files` is an array, not an object. You cannot key
  into it by role name; filter with `select(.role == "code")` instead.
- `.files[] | select(.role == "source")` — there is no `"source"` role.
  The implementation-code role is `"code"` (see
  `bin/role_map.py::ROLE_DESCRIPTIONS`).

## Discovery — what's in the role map?

If you don't remember the schema, peek at the top first. This returns the
schema version, provenance, total file count, and the distinct roles present,
all in one query. Use it to ground subsequent queries:

```
jq '. | {schema_version, provenance, files_count: (.files | length),
         roles: (.files | [.[] | .role] | unique)}' quality/exploration_role_map.json
```

The `provenance` field tells you HOW the file enumeration was produced.
`bin/role_map.py::VALID_PROVENANCE` is the canonical list; the values you
will encounter in practice are:

- `git-ls-files` — Phase 1 enumerated via `git ls-files` (preferred path,
  respects `.gitignore` automatically).
- `filesystem-walk-with-skips` — fallback for non-git targets; Phase 1
  walked the filesystem with explicit skips for the disallowed prefixes.
- `exclude-filtered` — emitted when the runner auto-recovered a too-large
  role map by filtering out vendored/build/cache content via the
  deterministic in-scope predicate (v1.5.6 cluster 049+; the filter does
  NOT shell out to git).
- `unknown` — legacy role maps written before `provenance` was required.

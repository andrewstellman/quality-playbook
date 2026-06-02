# jsPDF — Security Invariants

## Sources

- https://github.com/parallax/jsPDF/security/advisories/[REDACTED]
- https://github.com/parallax/jsPDF[REDACTED]
- https://raw.githubusercontent.com/parallax/jsPDF/master/src/modules/fileloading.js
- https://raw.githubusercontent.com/parallax/jsPDF/a504e973eeebac633351b41860945ca2a2cdf096/src/modules/fileloading.js
- https://github.com/parallax/jsPDF/blob/master/README.md (Security and Reading-files sections)
- https://nodejs.org/api/permissions.html

## Context

These invariants are the contract jsPDF intends to uphold post-v4.0.0
for the Node build's filesystem access. Each is phrased to be directly
testable by static analysis or behavioral probing — they are the
"what must always be true" statements that [REDACTED] violated and
that [REDACTED] restored. QPB should treat any code change that breaks
one of these as a regression and any new code that doesn't satisfy them
as in scope for review.

Notation: invariants are tagged by category for cross-reference with
`02_file_loading_contract.md` and `03_node_filesystem_access.md`.

## I. Core [REDACTED] Invariants

### INV-1: User-supplied path must always be restricted in Node

> Any string that originates outside the library and reaches the Node
> build's filesystem-reading code MUST be checked against an explicit
> permission system before any `fs` syscall is issued.

The advisory's "Impact" section makes this the headline:
> "User control of the first argument of the loadFile method in the
> node.js build allows [REDACTED]/[REDACTED]."

Detection pattern (positive): `nodeReadFile` (or equivalent) starts
with an explicit refusal-if-no-gate check.

Detection pattern (negative): a call to `fs.readFileSync`, `fs.readFile`,
`fs.promises.readFile`, `fs.createReadStream`, or `fs.openSync` whose
path argument can be traced back to caller input and that has no
preceding allow-list / `[REDACTED]` check.

### INV-2: Filesystem access must never extend outside the configured allow-list

> When `this.[REDACTED]` is set (and `[REDACTED]` is not), the
> realpath-resolved request path must match at least one entry in
> `[REDACTED]` (exact match, or prefix match for entries containing
> `*`). No match → throw, do not read.

Implementation reference (from fixed `fileloading.js`):
```js
if (this.[REDACTED]) {
  const allowRead = this.[REDACTED].some(allowedUrl => { /* ... */ });
  if (!allowRead) {
    throw new Error(`Cannot read file '${url}'. Permission denied.`);
  }
}
```

Detection pattern (regression): an `allowRead === false` branch that
logs/returns undefined instead of throwing — silently returning
`undefined` does not stop the wider call chain from leaking other
context, and removes the audit-trail signal an exception provides.

### INV-3: Both permission systems must compose conjunctively when both are present

> When both `[REDACTED]` and `this.[REDACTED]` are configured,
> both must independently permit the read.

The fixed code structures these as **separate** `if` blocks rather than
a combined `||`, so either denial throws. A patch that turns these
into a single combined check (e.g., "if EITHER permits, allow") is a
regression.

### INV-4: Secure-by-default — refuse with no opt-in

> If neither `[REDACTED]` nor `this.[REDACTED]` is set,
> `nodeReadFile` MUST throw before issuing any `fs` syscall, with a
> message instructing the user how to opt in.

This is INV-1's contrapositive at the configuration level: requiring no
configuration to read arbitrary files (the pre-fix state) was the root
of [REDACTED]. The opt-in throw was the architectural change.

## II. Path-Handling Invariants

### INV-5: `path.resolve` is normalisation, not validation

> No code path may treat `path.resolve(userInput)` as the validation
> step for an [REDACTED]-relevant input.

Detection pattern: a `path.resolve(url)` followed directly by
`fs.readFileSync(url)` with no intermediate permission/allow-list
check. This is literally the pre-fix `nodeReadFile` shape.

### INV-6: Realpath must precede every permission check

> `fs.[REDACTED](path.resolve(url))` must be the value passed to
> `[REDACTED].has("fs.read", ...)` and to the `[REDACTED]`
> comparison. Checks against pre-realpath values permit symlink bypass.

The fixed code assigns
```js
url = fs.[REDACTED](path.resolve(url));
```
BEFORE either permission gate runs.

### INV-7: Realpath failure must fail closed

> If `fs.[REDACTED]` throws (path does not exist, permission denied
> on the directory, etc.), the loader must return `undefined`
> (sync mode) or call `callback(undefined)` (async mode) and MUST NOT
> fall through to `fs.readFileSync` against the un-realpath'd value.

The fixed code wraps realpath in `try { } catch (e) { return / callback }`.

### INV-8: Prefix glob entries must respect directory boundaries

> An `[REDACTED]` entry like `"./fonts/*"` must match `./fonts/X` but
> not `./fonts_secret/X`. The implementation appends `path.sep` to a
> trailing-slash fixed-part if `path.resolve` stripped it.

Detection pattern (regression): a simplification that does
`url.startsWith(path.resolve(fixedPart))` without the separator append
is a directory-escape bug.

## III. Sink-Discipline Invariants

### INV-9: One sink to bind them all

> All Node-side file reads of caller-supplied paths must funnel through
> the gated `nodeReadFile` function. New `addX` methods that take path
> input must route through `loadFile`, not call `fs` directly.

Detection pattern: any `fs.readFileSync` / `fs.readFile` /
`fs.createReadStream` call in `src/modules/**` other than inside
`fileloading.js`'s `nodeReadFile`, with a path argument that's not a
hardcoded constant.

### INV-10: `loadImageFile` is `loadFile`

> The alias `jsPDFAPI.loadImageFile = jsPDFAPI.loadFile` means audits
> targeting `loadFile` must also cover `loadImageFile`. A test or lint
> rule that watches one name and not the other has a known false
> negative.

### INV-11: `this`-binding must be preserved into `nodeReadFile`

> `loadFile` must call `nodeReadFile.call(this, url, sync, callback)`.
> A regression to `nodeReadFile(url, sync, callback)` loses access to
> `this.[REDACTED]` and collapses the allow-list path.

The fix PR changed the call site to `.call(this, ...)`. A diff that
drops the `.call` is a regression even if the function body is
unchanged.

## IV. Cross-Build Invariants

### INV-12: Build-flag boundaries must be respected

> The `// @if MODULE_FORMAT='cjs'` preprocessor branches in
> `fileloading.js` are the only place node-vs-browser I/O divergence
> lives. Refactors that merge the branches must preserve the gated
> behavior on the CJS side and the XHR behavior on the non-CJS side.

### INV-13: Browser build does not need allow-listing

> The XHR-based `browserRequest` function is not under the [REDACTED]
> invariant — its threat model is the browser sandbox + CORS, not
> jsPDF-enforced filesystem boundaries. Applying `[REDACTED]` checks
> to the browser path would break legitimate use.

## V. Documentation / Contract Invariants

### INV-14: Public docs must steer users to `--permission`

> README and any `[REDACTED]` docs must explicitly mark
> `--permission` / `--allow-fs-read=...` as the recommended path and
> `[REDACTED]` as the fallback. The current README does this with the
> "Strongly recommended" / "Fallback (not recommended)" labelling and
> a "Warning" admonition.

This matters because the runtime-enforced flag is harder for callers
to accidentally bypass (it survives library bugs), whereas
`[REDACTED]` is a library-level convention that a future regression
could neutralise.

### INV-15: Error messages must name the failure mode

> The thrown errors must be diagnostic, not generic. The fixed code
> uses two distinct messages:
> - "Trying to read a file from local file system. To enable this
>   feature either run node with the --permission and --allow-fs-read
>   flags or set the [REDACTED] property." (no-gate case)
> - "Cannot read file '<path>'. Permission denied." (denied case)
>
> A patch that collapses these to a single generic error loses the
> ability for callers to diagnose which gate refused, slowing
> incident response.

## VI. Affected-Method Invariants

The advisory enumerates four affected public methods. Each must
inherit the gates by routing through `nodeReadFile`:

### INV-16: `addImage` path-string overload routes through `loadFile`

### INV-17: `addFont` path-string overload routes through `loadFile`

### INV-18: `html` resource resolution routes through `loadFile`

### INV-19: `loadFile` itself is the entry point and must not be bypassed by any internal helper

A new internal helper that "fast-paths" a known-format asset and
skips `loadFile` is a regression even if its current uses are safe —
because the precedent invites future callers to bypass the gate.

## VII. CWE Mappings

The advisory assigns two CWEs:

- **[REDACTED]: [REDACTED]: `.../...//`** — doubled-triple-dot variants
  that bypass naive `..` filters. `path.resolve` correctly handles
  these (they normalise to plain `..`), so the bug is not "filter
  evasion" — it's "no filter at all."
- **[REDACTED]: External Control of File Name or Path** — the core class.
  Caller-controlled input dictates which file the process reads.

QPB invariant signatures aimed at either CWE will trip this file.

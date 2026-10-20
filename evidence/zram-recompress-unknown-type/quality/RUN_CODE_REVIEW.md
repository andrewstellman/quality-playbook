# Code Review Protocol: zram

## Bootstrap (Read First)

Before reviewing, read:
1. `quality/QUALITY.md`
2. `quality/REQUIREMENTS.md`
3. `Documentation/admin-guide/blockdev/zram.rst`
4. `docs_gathered/zram-community-development-history.md`
5. `docs_gathered/zsmalloc-design.md`
6. `drivers/block/zram/zram_drv.c`
7. `drivers/block/zram/zcomp.c`

## Pass 1: Structural Review

Read `drivers/block/zram/zram_drv.c`, `zcomp.c`, and touched backend files for correctness defects only.

### Guardrails

- Line numbers are mandatory.
- Read function bodies, not just names.
- Grep before claiming a feature is missing.
- Use `QUESTION` if intent is unclear.
- Do **not** include style or refactor comments.

### zram-specific focus while staying structural

- Any path that returns without completing a bio.
- Any slot transition that frees storage before new ownership is secured.
- Any sysfs handler that mutates state without the right init or lock guard.
- Any backing-device or recompression path that can silently drop work on allocation failure.

### Output format

```markdown
## Pass 1: Structural Review

#### drivers/block/zram/zram_drv.c
- **Line NNN:** BUG / QUESTION / INCOMPLETE ...
```

## Pass 2: Requirement Verification

Verify the code against these priority REQs:

- REQ-002 through REQ-009 for sysfs and writeback control
- REQ-010 through REQ-015 for recompression and data-path behavior
- REQ-018 for reset/remove lifecycle

For each reviewed REQ, report:

```markdown
#### REQ-NNN: [title]
**Status**: SATISFIED / VIOLATED / PARTIALLY SATISFIED / NOT ASSESSABLE
**Evidence**: file:line — code quote
**Analysis**: ...
**Severity**: ...   # only when violated
```

## Pass 3: Cross-Requirement Consistency

Compare these shared concepts:

1. **Initialization freeze** — REQ-002, REQ-004, REQ-006, REQ-007
2. **Slot-state machine** — REQ-009, REQ-011, REQ-012, REQ-013, REQ-014, REQ-015
3. **Backing-device accounting** — REQ-007, REQ-009, REQ-016
4. **Lifecycle teardown** — REQ-001, REQ-002, REQ-018

Report:

```markdown
#### Shared Concept: [name]
**Requirements**: REQ-X, REQ-Y
**Consistency**: CONSISTENT / INCONSISTENT
**Code evidence**: ...
**Analysis**: ...
```

## Combined Summary

Create a table:

| Source | Finding | Severity | Status | Closure |
|--------|---------|----------|--------|---------|
| Pass 1 | ... | ... | BUG / QUESTION | `quality/test_regression.py::...` or exemption |
| Pass 2, REQ-NNN | ... | ... | VIOLATED | ... |
| Pass 3, REQ-X vs REQ-Y | ... | ... | INCONSISTENT | ... |

End with:
- Total findings by pass
- Overall assessment: **SHIP IT / FIX FIRST / NEEDS DISCUSSION**

## Closure mandate

Every confirmed BUG must produce a regression test in `quality/test_regression.py` using `unittest.expectedFailure` and a docstring citing the finding.

### Alignment check

For each regression test:
1. Confirm the finding's cited function and line range.
2. Confirm the test inspects that exact code path.
3. Confirm the expected failure asserts **desired** behavior, not the current broken behavior.

## Adversarial stance with documentation

Treat `Documentation/admin-guide/blockdev/zram.rst` and `docs_gathered/` as prosecution evidence. If the docs promise behavior that the code fails to provide, that is a finding, not an excuse.

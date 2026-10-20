# Spec Audit Protocol: zram

## The Definitive Audit Prompt

Give the following prompt unchanged to three independent strong code-reading models:

---

**Context files to read:**
1. `quality/QUALITY.md`
2. `quality/REQUIREMENTS.md`
3. `Documentation/admin-guide/blockdev/zram.rst`
4. `docs_gathered/zram-community-development-history.md`
5. `docs_gathered/zsmalloc-design.md`
6. `drivers/block/zram/zram_drv.c`
7. `drivers/block/zram/zcomp.c`
8. `drivers/block/zram/backend_zstd.c`
9. `drivers/block/zram/backend_lzo.c`

**Task:** Act as the Tester. Compare the code in `drivers/block/zram/` against the specifications above.

**Requirement confidence tiers:**
- **formal** — `Documentation/admin-guide/blockdev/zram.rst`, `Kconfig`
- **inferred** — requirements derived from current code behavior or gathered design history

**Rules:**
- ONLY list defects.
- For every defect, cite file and line number(s).
- Grep before claiming missing.
- Read function bodies, not just signatures.
- Classify each finding: MISSING / DIVERGENT / UNDOCUMENTED / PHANTOM.
- If the finding targets an inferred requirement, mark it `NEEDS REVIEW`.

**Project-specific scrutiny areas:**
1. Read every `*_store()` handler that can change on-disk or in-memory layout. Do any documented pre-init-only knobs stay mutable after init?
2. Read `read_from_bdev_async()` and the discard path in `zram_bio_discard()`. Are there any branches that fail to complete or fail to error a bio?
3. Compare writeback docs to `writeback_store()`, `scan_slots_for_writeback()`, and `zram_writeback_complete()`. Do selector syntax and rollback/accounting match?
4. Compare recompression docs to `recompress_store()` and `recompress_slot()`. Are threshold, idle, huge, and incompressible semantics aligned?
5. Compare zsmalloc size constraints to `zram_write_page()` and `write_incompressible_page()`. Does the code reliably avoid >`PAGE_SIZE` allocations for stored objects?
6. Check whether exported stats fields and debug letters match documentation.

**Output format:**

```markdown
### drivers/block/zram/zram_drv.c
- **Line NNN:** [MISSING / DIVERGENT / UNDOCUMENTED / PHANTOM] [Req: tier — source] Description.
  Spec says: ...
  Code does: ...
```

---

## Pre-audit docs validation

`docs_gathered/` was present during generation. Spot-check results before trusting audit confidence:

1. **Validated true:** `compressed_writeback` is pre-init-only (`zram_drv.c:552-569` matches docs).
2. **Validated true:** incompressible-page fallback stores raw `PAGE_SIZE` objects (`zram_drv.c:2269-2272`, `2200-2238`).
3. **Known inaccuracy:** docs list `-EAGAIN` for concurrent recompress/writeback, but `zram_drv.c` contains no `-EAGAIN` return; operations are serialized by `dev_lock` instead.
4. **Known inaccuracy:** docs describe `invalid_io` as a tracked counter, while `io_stat_show()` currently emits a literal `0`.

Findings that rely primarily on those inaccurate doc claims should be downgraded to `NEEDS REVIEW`.

## Running the Audit

1. Run the definitive prompt with three independent strong models.
2. Save each report to `quality/spec_audits/YYYY-MM-DD-[model].md`.
3. Merge them into a triage report at `quality/spec_audits/YYYY-MM-DD-triage.md`.

## Triage Process

Record council status:

```markdown
## Council Status
- Model A: Fresh report received
- Model B: Fresh report received
- Model C: Fresh report received
```

Then classify merged findings:

| Confidence | Found By | Action |
|------------|----------|--------|
| Highest | 3/3 | Fix or update spec |
| High | 2/3 | Verify and treat as likely real |
| Needs verification | 1/3 | Run a verification probe |

For each confirmed finding, categorize it as:
- Spec bug
- Design decision
- Real code bug
- Documentation gap
- Missing test
- Inferred requirement wrong

## Verification probe

If audits disagree on what the code does, run a read-only probe focused on that exact claim and cite the decisive line numbers in the triage report.

## Fix execution rules

- Group fixes by subsystem (`sysfs`, `writeback`, `recompress`, `block I/O`)
- Never batch all findings into one mega-fix prompt
- Every confirmed code bug needs a regression test entry in `quality/test_regression.py`

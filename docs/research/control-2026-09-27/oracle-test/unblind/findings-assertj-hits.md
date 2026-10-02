# Hits: assertj

| ID | Reports that include it as a finding | Reports that mention it but do not report it |
|---|---|---|
| assertj-01 | opus-run01 | — |
| assertj-02 | sonnet-run01 | — |
| assertj-03 | sonnet-run01 | opus-run01 |
| assertj-04 | opus-run01, sonnet-run01 | — |
| assertj-05 | opus-run01 | — |

## Deduplication judgement calls

- sonnet-run01 Defect 2 bundled (a) the base-class check accepting 0 while its message says "greater than zero" and (b) `byLessThan(0, unit)` failing for identical values. Split into assertj-03 and assertj-02: changing the message alone does not change (b), and adding a strict check only to the less-than constructor does not change the message the within-offset path shows.
- opus-run01's "Checked and not reported" says `TemporalUnitOffset` says "should be greater than zero" while it accepts 0; counted as a mention for assertj-03 only. It does not discuss the `byLessThan(0)` behaviour, so it is not counted for assertj-02.
- opus-run01 finding 2 covers both `equals` and `hashCode` ignoring `unit`; kept as one row (assertj-01) because the observable behaviour is equality of offsets with different units, with a consistent hash.
- Both reports mention the `Percentage.withPercentage` javadoc `@throws NullPointerException` note as documentation-only and not reported. No report lists it as a finding, so it has no row.
- The checkout has no `.git` directory, so the pinned commit is taken from the task, not verified locally (same for otel).

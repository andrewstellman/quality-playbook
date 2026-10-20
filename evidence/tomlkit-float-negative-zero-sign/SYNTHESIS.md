# Synthesis: tomlkit-float-negative-zero-sign (BUG-022)

Panel 1 (2026-10-02, full roster, 15 reviewers; O-roles on Opus 5.5, executors and S-roles on Sonnet 5.5). Reviewed commit b05050c and the first PR.md (kept in `rev0/`).

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tomlkit-float-negative-zero-sign | S | S | S | S | S | S | F | S | F | F | S | S | S | S | F |

No REJECT, no DROP. Nobody asked for a change to the source line. O3 swept 7,540 operation cases and O2 3,960: the fix changes only outputs that were `+-0.0`.

Findings that had to change, and what was done:

- **Summary about twice as long as the merged fixes it sits beside** (O5, S3, O1). Rewritten from 239 to about 150 words: the "results render as before" list, the pass count and the spec paragraph are gone; "Fix:" is folded into the cause.
- **Repro looks contrived** (O5, O4, O3, O2). `x = +0.0` times `-1` replaced by `x = -1.5` times `0`, which needs no zero or `+` in the file. Parent re-ran it on base and fixed.
- **Notes line says the same thing twice; tool name and URL repeated** (O5, S3, O1, S8). Shortened; URL removed. Kept true of the file as it stands (agent-drafted). The operator rewrites the Summary and then changes the Notes line; see REVIEW.md.
- **Model line cannot be checked from the packet** (O5, S7, S8). Shortened to the three names; REVIEW.md says where they come from.
- **Test** (S2 required one of: a comment on the Integer block, or a split; S2, S3, O5: the "used to render" comment narrates history). The test now starts from `a = -1.5` times `0` to match the PR repro, the first comment is removed, and the Integer block has the comment `# Integer true division also goes through Float._new.` The flip back to `+0.0` stays (S4's mutation run shows it catches an over-fix). Commit amended to d59cfe9 (message example updated to match); red, green, revert, suite and lint re-run by the parent.

Not adopted:

- **O1, S8 (optional): replace the first-person disclosure sentence in the commit with an `Assisted-By:` trailer.** The operator's standing rule is no trailers; the sentence stays.
- **S2 (optional): add a parse-back assertion and a `-0.0 * 1` case.** S4 judged more cases padding for a one-line fix.

Known and left out on purpose: `Integer.__pow__` with a negative exponent can still write `+-0.0` through `Integer._new` (O1, O3). It is a different defect (an `Integer` item holding a float) and the PR text claims nothing about it.

Side-effect rule: O1 to O5 and S5 found nobody hurt. The only output that changes was unparseable before.

## Round 2 (focused re-review of commit d59cfe9 and the rewritten PR.md)

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| tomlkit-float-negative-zero-sign | S | S | – | – | – | – | S | – | S | S | – | – | – | S | – |

All six re-reviewers: SHIP (high). Both executors confirm the packet patch applies to a clean 0518af2 with `git am` and gives the fixed clone's tree (860e0eb). O5 swept 7,175 operation cases: 270 differ, every one `+-0.0` becoming `-0.0`. S2 mutated the source line three ways and the test caught each.

Text fix applied after round 2: `tomlkit/items.py:879` now reads "`tomlkit/items.py:879` on master" (S7: the fix moves the line to 880).

Not adopted (optional): wrapping the commit's disclosure line at 72 columns (O5); it is the prescribed sentence and a change would need another executor round. A shorter Notes line (O5); the current one is accurate.

Operator gate raised by O5: the Notes line says the agent drafted the text, and the maintainer has said the summary must come from a human. See REVIEW.md, "Things to know before submitting".

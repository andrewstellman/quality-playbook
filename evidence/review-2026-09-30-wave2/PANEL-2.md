# Focused re-review: four code-revised fixes + one side-effect check (2026-10-01)

The first panel (PANEL.md, SYNTHESIS.md, raw reviews in /sessions/kind-zealous-edison/mnt/QPB/evidence/review-2026-09-30-wave2/) asked for changes. They have been made. Your job: check the changes are right, nothing new broke, and apply Andrew's rule.

**Andrew's rule (new, binding):** do not submit any fix whose side effects on existing users are bad. A fix that is correct per the spec but can hurt existing users in a way they would not expect is dropped. For every item, name each behaviour change for existing users and judge: acceptable / bad enough to drop. Be concrete (who is affected, what happens to them, how likely).

## Materials
- /tmp/w2review2/packets/<ID>/: fix.patch (the revised commit), PR-DRAFT.md, CHANGES-AFTER-PANEL.md (what the reviser says was done), WHERE.txt (worktree; base = HEAD~1; never modify it).
- The first panel's findings for each item: SYNTHESIS.md bullet + grep the raw reviews for the id.
- Citable docs: /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/<repo>/reference_docs/cite/.
- Experiments: `git clone -q <worktree> /tmp/w2review2/scratch/<your-id>/<ID>`; delete when done. Write only /tmp/w2review2/out/<your-id>.md. Never push, post, or write under /sessions/.../mnt/QPB. Never fabricate; paste output verbatim.

## Disk (critical)
`/sessions` is 100% full: always `export TMPDIR=/tmp/w2review2/scratch/<your-id>/tmp HOME=/tmp/home` (mkdir it) and `PIP_NO_CACHE_DIR=1`. `/` has ~600 MB: check `df -m / | tail -1`; stop building below 300 MB. No pydantic or javalin builds.

## Toolchains
- cobra: `export PATH=/tmp/go/bin:$PATH GOPATH=/tmp/gopath GOCACHE=/tmp/gocache; go test ./...`
- setuptools: `cd <tree> && PYTHONPATH=<tree> /tmp/w2fix/st-venv/bin/python -m pytest <tests> -p no:cacheprovider` (don't pip install into st-venv).
- addressable: `cd <tree> && GEM_PATH=/tmp/addressablev/gems ruby -I lib -I /tmp/addrstub /tmp/addressablev/gems/bin/rspec spec/addressable/<file>_spec.rb`

## Items
| ID | What the first panel asked | Revision claimed |
|---|---|---|
| cobra-016 | extra slice-flag duplicate; undisclosed `--out=x` toComplete change; fold block; mention #2259; doc quote | stop detection via the `--` probe, flags parsed twice as on base; disclosed; folded; #2259 named; quote trimmed |
| st-004 | drop untested content-type reset; annotations; comment the metadata pop; point at the maintainer comment in #4183 | all four done |
| addr-011 | colon segment raised InvalidURIError; quadratic regex; path assigned once; commit wording; #126 quote | `./` prefix for empty or colon segment + spec; rpartition; if/elsif/else; wording; verbatim quote |
| addr-032 | hoist regexp, file's hex spelling, comment; more specs; state the behaviour change | constant ALLOW_RESERVED_ENCODE_MAP; specs for %zz, %2, lowercase hex, explode list; one PR line |
| st-024 | (text only) | SIDE-EFFECT CHECK ONLY: `include` lines with `**` now recurse, so existing MANIFEST.in files can pull hidden dirs, venv/, node_modules/ into sdists. Is that bad enough to drop under Andrew's rule? Measure it on a realistic project layout. |

## Roster (you are exactly one)
- EXEC-A, EXEC-B: for cobra-016, st-004, addr-011, addr-032: red (test only on base, read the failure text), green, revert-source, touched test file + full suite for the repo (cobra `go test ./...`, addressable full rspec, setuptools test_apply_pyprojecttoml.py + test_manifest.py). EXEC-A also re-times addr-011: target `http://example.com/` + 30000 a's + `/` routed from the same with `?q=1`, base vs fixed. EXEC-B: 3 edge inputs per item of your own choosing, base vs fixed. Table at the end.
- O2 SECURITY, O3 CORRECTNESS, O4 NOT-A-BUG (Opus): your first-panel charter (see PANEL.md) applied to the revised code, plus the side-effect rule on all five.
- S1 READABILITY-CODE, S2 READABILITY-TESTS, S4 QA, S5 COMPAT (Sonnet): same, your charter + the side-effect rule.

## Output (/tmp/w2review2/out/<your-id>.md, also returned as text)
For each of the five IDs:
### <ID>
Verdict: SHIP | FIX-REQUIRED | DROP (side effect) | REJECT
Side effects: each behaviour change for existing users → acceptable / bad, with who and how likely.
Findings: numbered, with file:line or quote.
Under ~80 lines total.

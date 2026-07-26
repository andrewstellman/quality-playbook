VERDICT: FIX-REQUIRED

# Round-4 closure audit — self-Council verification of `3ef3a7e`

**Scope:** commit `3ef3a7e` ("close the self-Council findings (round 3)") against the three blocking
findings B-2, B-3, B-4 and the P2 mutation E3 that `round3_closure.md` left open. Branch `1.6.0`,
repo `/Users/andrewstellman/Documents/QPB`. Per charter I did not re-litigate anything rounds 2 and
3 marked CLOSED.

**Method:** everything below was executed, nothing is taken from the commit message. I ran the full
suite at clean HEAD; mutation-bit five separate checks in `quality_gate.py` (the `if not functional:`
guard, the mandatory-part tuple, both `_render_blank_fences` call sites, and the intro-prose and
terminal-period checks) with a `shutil.copy2` pristine snapshot, a scoped `__pycache__` purge and a
byte-comparison restore between each; built an independent probe harness driving
`check_render_contract` over synthesized documents; staged eight manifest mutations against the real
`ManifestUnchangedInvariantTests`; and swept all 105 archived trees under `repos/` and `metrics/`
across three builds (`39cc939`, `a95dcb5`, `3ef3a7e`) via git worktrees.

**Headline:** all three round-3 blocking findings are genuinely closed this time, and the bites
demonstrably fire — I verified each by execution rather than by reading the commit message, which is
what round 3 warned about. The commit message's mutation-evidence table is accurate in every
particular I checked. But the B-4 fix was applied at the two *call sites* while leaving the
underlying `_RENDER_FENCE_RE` unchanged, and that regex is backtick-only and requires a closing
pair. So round 3's B-4 document reproduces verbatim with `~~~` instead of ` ``` ` — **FAIL=0 WARN=0,
thirteen PASS lines**, on a completely flat requirement list. That is the sixth bypass, in the same
defect class, and it also re-opens the R-3 false-positive direction that round 2 closed.

---

## Summary table

| Round-3 item | Status |
|---|---|
| **B-2** — re-point the flat-shape bite at an intro-prose fixture | **CLOSED** (bite fires; 3 tests red) |
| **B-3** — `_fires` bite per mandatory part + AUDIT rows | **CLOSED** (bite fires; 3 `test_mp1_*` red) |
| **B-4** — blank fences before structure detection | **CLOSED for backtick fences only** |
| **B-5 (new)** — `~~~`, unclosed and 6-backtick fences bypass identically | **NEW — BLOCKING** |
| Assertion strength audit | 4 weak assertions remain, all pre-existing, all still biting — **P3** |
| Mutation E3 (swap two `functional_section` labels) | **CLOSED** (detected, 6 failures) |
| Mutation E4 (field *deletion* undetected) | **FOUND — P2** |
| Full suite green (2527) | **CONFIRMED** (OK, skipped=13) |
| Three regenerated fixtures FAIL=0 WARN=0 | **CONFIRMED** (and genuinely evaluated) |
| Archived sweep, gate exit-code flips | **CONFIRMED** zero (`a95dcb5` → HEAD: zero diffs at all) |
| Fixture inputs SHA-256 unchanged | **CONFIRMED** (by mtime; see caveat) |
| Tree clean at end | **CONFIRMED** |

---

## Verified closures

### B-2 — the re-pointed test: **CLOSED**

`git show --stat 3ef3a7e` confirms `bin/tests/test_render_contract_v160.py` **was** modified this
time (158 lines changed). The flat-shape fixture is now a class-level `_FLAT_DOC` constant whose
`## Requirements` section carries this intro prose:

> "This section lists every requirement derived for testproj, in the order the derivation produced
> them. No further organization was attempted, which is exactly the shape the render contract exists
> to reject."

That is ~190 characters against the 40-character `section_intro_ok` threshold. The fixture also
carries all three mandatory parts and two REQs, so the singleton and intro-prose checks are silent
and the *only* thing wrong with it is the flat bucket — which is precisely what round 2 asked for.

**Bite, executed.** Deleted the entire ten-line `if not functional:` FAIL block (`quality_gate.py`
:7248-7257), purged `__pycache__`, ran the full suite:

```
Ran 2527 tests in 77.703s
FAILED (failures=3, skipped=14)
```

The three red tests are exactly the three the commit message names:

```
FAIL: test_mp2_reqs_outside_any_functional_section_fires (MandatoryPartTests)
FAIL: test_mp2_flat_requirements_heading_cannot_bypass_section_discipline (RenderContractFalsePositiveTests)
FAIL: test_mp3_fenced_code_block_headings_do_not_synthesize_structure (RenderContractFalsePositiveTests)
```

Restored from the pristine snapshot; module back to `OK`, `git status --porcelain` empty. Where
round 3 got the whole suite green with this guard deleted, it now goes red in three places. Closed.

### B-3 — the mandatory-part bites: **CLOSED**

**Bite, executed.** Replaced the check tuple with `()`:

```
FAIL: test_mp1_missing_actors_and_roles_fires
FAIL: test_mp1_missing_traceability_appendix_fires
FAIL: test_mp1_missing_use_cases_fires
FAIL: test_mp3_fenced_code_block_headings_do_not_synthesize_structure
FAILED (failures=4)
```

All three `test_mp1_*` tests are red, as charged. Restored; back to `OK`.

`RENDER_CONTRACT_AUDIT` now carries MP-1, MP-2 and MP-3 rows, and the size guard
`test_audit_table_size_matches_known_defect_classes` is updated from 7 to 10 with a comment
explaining why. I confirmed the sweep has real teeth rather than just counting rows:
`test_every_audit_row_has_a_mutation_bite_test` derives the prefix `test_mp1_` / `test_mp2_` /
`test_mp3_` from each row's defect id and requires a matching method somewhere in the module — which
is why the new tests had to be renamed, exactly as the commit message describes. Closed.

### B-4 (backtick fences) — **CLOSED**

Round 3's demonstrated fenced-heading document now scores **FAIL=4 WARN=0**, with all three
mandatory-part FAILs and the `no functional section` FAIL firing. Both call sites are bitten
independently:

| Mutation | Result |
|---|---|
| `structure_text = text` (revert structure detection to raw) | `test_mp3_fenced_code_block_headings_do_not_synthesize_structure` **red** |
| `_RENDER_REQ_HEADING_RE.finditer(text)` (revert REQ detection to raw) | `test_mp3_req_headings_inside_a_fence_are_not_counted` **red** |

Both restored and re-verified green. The fix also correctly moved `_render_overview_body`,
`_render_classify_sections` and the section-body slicing onto `structure_text`, and
`_render_blank_fences` is length-preserving so the offsets in `bounds` stay valid — I checked that,
since a non-length-preserving blank would have silently corrupted the per-section REQ counts.

### Mutation E3 — **CLOSED**

`test_manifest_sections_match_the_rendered_sections` was replaced by
`test_each_req_renders_under_the_section_its_record_names`, which walks the document tracking the
most recent level-2 heading and checks each REQ against its record. Staged against the real
invariant class:

```
*** PASSES (undetected) ***    failures=  0  control: unmutated
DETECTED                       failures=  6  E3: swap two functional_section labels
DETECTED                       failures= 26  E4a: prefix-negate every CoS
DETECTED                       failures= 32  E4b: reverse references order
```

E3 is detected. As a bonus, round 3's residual-risk CoS prefix-negation case (E4a) is now caught too.

---

## BLOCKING — B-5. The sixth bypass: `_RENDER_FENCE_RE` is backtick-only and requires a closing pair

The charter asked me to hunt for a sixth bypass, noting the worker has missed one at each of three
rounds. There is one, and it is round 3's B-4 with two characters changed.

`3ef3a7e` fixed B-4 by routing the *call sites* through `_render_blank_fences`. It did not touch the
regex that function delegates to:

```python
_RENDER_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
```

Three things are wrong with it, and each is independently sufficient to reproduce B-4 in full:

1. **It only knows backticks.** `~~~` is a standard CommonMark fence — and it is specifically what
   you use when the fenced content itself contains backticks, which a REQUIREMENTS.md quoting
   markdown routinely does.
2. **It requires a closing pair.** An unterminated fence blanks nothing, so every heading after it
   is counted — while a real markdown renderer treats the entire remainder of the document as code.
3. **It is not line-anchored and not fence-length-aware.** Six backticks match as an *empty* fence
   (` ``` ` + `.*?` + ` ``` ` consumes the run itself), leaving the body raw.

### Demonstrated — the tilde variant

Round 3's exact B-4 document with ` ```markdown ` / ` ``` ` replaced by `~~~markdown` / `~~~`. Flat,
undifferentiated REQ list; no actors, no use cases, no traceability appendix, no section structure:

```
*** BYPASS ***   FAIL=0 WARN=0  S1 tilde fence
[Render Contract]
  PASS: REQ IDs sequential in document order (REQ-001..REQ-002)
  PASS: no tool-contract REQs in REQUIREMENTS.md (0 tool-contract REQ(s) in the manifest)
  PASS: Overview section present
  PASS: Actors & roles section present
  PASS: Use cases section present
  PASS: Traceability appendix section present
  PASS: all 1 functional section(s) carry intro prose
  PASS: no degenerate singleton functional sections
  PASS: no derivation internals in the rendered document
  PASS: all 2 REQ titles within 120 characters
  PASS: no REQ title carries a terminal period
  PASS: generator stamp matches skill version (v1.6.0)
  PASS: coverage-and-gaps statement present in the Overview
```

Thirteen PASS lines, FAIL=0 WARN=0 — the same output round 3 recorded for the backtick version,
including the same four PASS lines it called out by name. The entire §5.2 architecture is again
satisfied by four lines inside one fence.

### The full probe matrix

| Shape | Result |
|---|---|
| `~~~markdown` … `~~~` | **FAIL=0 WARN=0 — BYPASS** |
| `~~~` (bare, no info string) … `~~~` | **FAIL=0 WARN=0 — BYPASS** |
| unclosed ` ```markdown ` (no closer) | **FAIL=0 WARN=0 — BYPASS** |
| six-backtick fence | **FAIL=0 WARN=0 — BYPASS** |
| four-backtick fence | FAIL=4 — correctly rejected |
| 4-space-indented backtick fence | FAIL=4 — correctly rejected |
| fence nested inside a fence | FAIL=4 — correctly rejected |
| CRLF + backtick fence | FAIL=4 — correctly rejected |

### It also re-opens R-3, in the false-positive direction

This is the part I want to flag hardest, because it is a live regression risk on *conforming*
documents rather than an evasion. Round 2 closed R-3 by blanking fences before the internals scan.
That fix is also backtick-only, so a conforming REQUIREMENTS.md that quotes a `~~~` block gets
spurious FAILs:

| Probe | Result |
|---|---|
| clean doc + `~~~markdown` fence quoting `### REQ-099: An example REQ.` | **FAIL=2** (sequentiality breaks) |
| clean doc + `~~~markdown` fence quoting `<!-- cluster: heterogeneous -->` | **FAIL=1** (internals "leaked") |
| control: same two, in a backtick fence | FAIL=0 — correct |

So the gap is not merely "a flat document can sneak through"; it is also "a good document that uses
the other standard fence syntax is failed for quoting an example." Round 3 rated the backtick
version blocking for three reasons — no deliberate evasion required, it defeats the checks that are
the substance of the commit, and the fix is small. All three hold here, and the false-positive
direction is an additional argument the backtick version did not have.

### Suggested fix, validated

A single line-anchored, fence-length-aware, both-delimiter regex closes all four bypass shapes while
leaving real headings intact. I prototyped and verified this:

```python
_RENDER_FENCE_RE = re.compile(
    r"^(?P<f>`{3,}|~{3,})[^\n]*\n.*?(?:^(?P=f)`*~*[ \t]*$|\Z)",
    re.DOTALL | re.MULTILINE,
)
```

Against the seven fence shapes above it hides the quoted `## Actors` in all seven (backtick-3,
tilde-3, bare tilde, unclosed, four-backtick, six-backtick, nested), and on a control document with
real headings outside the fence it leaves exactly `['Real One', 'Real Two']` standing. It is
length-preserving under the existing `_render_blank_fences` substitution, so offsets stay valid.
Note this changes `re.DOTALL`-only to `DOTALL|MULTILINE`; `_RENDER_FENCE_RE` has one other consumer
(the internals scan), which is the same fix and wants it too.

**Required:** widen `_RENDER_FENCE_RE`, and pin at minimum the tilde and unclosed shapes with tests
under the existing `test_mp3_*` naming so the AUDIT sweep accepts them.

---

## P2 — Mutation E4: field *deletion* is undetected across every per-record check

As charged, I looked for an E4 that still passes. The E3 fix guards label *swaps* but not label
*absence*, because every per-record comparison skips a record whose field is missing
(`if rec is None or not rec.get("functional_section"): continue`):

```
*** PASSES (undetected) ***    failures=  0  E4c:  drop functional_section on EVERY record
*** PASSES (undetected) ***    failures=  0  E4c2: blank every functional_section to ""
*** PASSES (undetected) ***    failures=  0  E4c3: drop functional_section on ONE record
*** PASSES (undetected) ***    failures=  0  E4d:  drop title on ONE record
```

The single-record deletion is the minimal evasion and is the one that matters: a manifest can drop
one REQ's section label — or its title — and the invariant stays fully green. This is pre-existing
rather than introduced by `3ef3a7e` (the old set-based comprehension had the same `if r.get(...)`
guard), and it is the mirror image of the swap defect: round 3's fix asks "does the field agree with
the render?" but never asks "is the field there at all?". A field-presence assertion over the
records — cheap, since `_load_json` is already in hand — closes the whole family at once. Not
blocking; it is the same P2 class round 3 assigned to E3.

## P3 — Four assertions are still substring-weak, though all four currently bite

Round 3 found a bite that passed because its assertion matched both branches. I audited every
`assertIn` in both new modules by capturing the clean all-PASS output and checking each asserted
substring against it. **All three MP assertions the worker tightened are genuinely discriminating** —
`no Actors & roles section`, `no Use cases section`, `no Traceability appendix section` and
`no functional section` appear nowhere in the PASS text. The tightening was done correctly.

Four older assertions still match their own PASS message:

| Test | Assertion | Matching PASS line |
|---|---|---|
| `test_c1_fires_when_tool_req_rendered_into_product_spec` | `"tool-contract REQ"` | `PASS: no tool-contract REQs in REQUIREMENTS.md …` |
| `test_c3_fires_on_missing_section_intro_prose` | `"intro prose"` | `PASS: all 2 functional section(s) carry intro prose` |
| `test_c6_fires_on_terminal_period` | `"terminal period"` | `PASS: no REQ title carries a terminal period` |
| `test_f1_warns_when_gaps_statement_absent` | `"coverage-and-gaps statement"` | `PASS: coverage-and-gaps statement present in the Overview` |

I did not stop at reading them. I neutered the intro-prose and terminal-period checks and both tests
went red:

```
FAIL: test_c3_fires_on_missing_section_intro_prose
FAIL: test_c6_fires_on_terminal_period
FAILED (failures=2)
```

They survive because the companion `assertGreaterEqual(fails, 1)` does the discriminating — no other
check fires on those particular fixtures. So this is latent, not live: the assertions carry no
information today, and the tests would silently stop discriminating the moment any co-firing FAIL
were introduced into those fixtures. That is exactly how round 3's mp3 bite failed. All four are
pre-existing, none were introduced by `3ef3a7e`, and none is blocking. Tighten them to the FAIL
phrasing in the same pass as B-5.

---

## No new regressions

- **Full suite at clean HEAD:** `Ran 2527 tests in 78.756s — OK (skipped=13)`. Matches the commit
  message's 2527 exactly.
- **Three regenerated fixtures:** chi, express and virtio each **FAIL=0 WARN=0**, and each with 15
  PASS lines — I checked the exit path, not just the counts, so none is version-skipped or inert.
- **Archived sweep, 105 trees under `repos/` and `metrics/`:**

  ```
  39cc939 (pre-work baseline):  (-1,-1) × 105   [check_render_contract does not exist]
  a95dcb5:                      (0,0) × 100,  (0,1) × 5
  3ef3a7e (HEAD):               (0,0) × 100,  (0,1) × 5

  a95dcb5 -> HEAD diffs:            0
  baseline -> HEAD FAIL flips:      0
  ```

  `a95dcb5` → HEAD is **byte-identical across all 105 trees** — not merely no FAIL flips, no WARN
  changes either. The five WARN trees are round 3's known INFO→WARN five, unchanged. I confirmed the
  baseline's `-1` is genuine and not a harness artifact: `hasattr(quality_gate,
  "check_render_contract")` is `False` at `39cc939`, so the pre-work baseline has no exit code to
  flip by construction, and round 3's `d8d4229` column already established the harness has
  discriminating power. **Zero gate exit-code flips.**
- **Fixture inputs at `repos/{chi,express,virtio}-1.5.8`:** unchanged. Caveat on method — `repos/` is
  untracked, so there is no git baseline to diff against and no recorded SHA anywhere in the tree; I
  could not verify the commit message's SHA-256 claim against a stored value. I verified it a
  different way, and the evidence is stronger: all six files carry mtimes of **2026-06-19 17:59–18:01**,
  a full month before this work began (`71b1a81`, 2026-07-19 20:46), so they were not written during
  any of the four commits under review. Current digests recorded for future rounds:

  ```
  chi/REQUIREMENTS.md              c426df065a8c01a52af09fcd982d634ef8070fb7d6c5dcfa1fe3702b03b1f387
  chi/requirements_manifest.json   0775cfde823cf8383fabf76d0a599ae3aa8386b94d0920f341f9fdcafd5a392b
  express/REQUIREMENTS.md          9709a9d410205a82698394b7398d87b154b497e17fc072c85bb3d63e4c0b3b26
  express/requirements_manifest.json 48ae45e91a246604b4fe08f14796091fe3d27ea26b1fd272b9b7e69285cb1390
  virtio/REQUIREMENTS.md           e11e2b255220ec371ab6b3ef307c72248aed3dceeaaa6d279fb48a6c0d52cb08
  virtio/requirements_manifest.json b810c53866261fad59665927caf39538a8c62d5cd02de268e5dfa429a991b3c8
  ```
- **Tree clean:** `git status --porcelain` empty; all three touched files byte-identical to the
  pristine snapshot (`filecmp.cmp(shallow=False)`); both scratch worktrees removed and pruned; HEAD
  still `3ef3a7e`.

---

## What is genuinely good here

The verify-before-claim failure round 3 called out did not recur. Every claim in this commit
message that I tested held up — the three-item mutation table is accurate down to the individual
test names, the suite count is right, and the fixture and archive claims are right. That is the
specific thing round 3 said was broken, and it is fixed.

The B-3 work is better than what was asked for: the AUDIT sweep derives its expected test-name
prefix from the defect id, so the new rows *forced* the tests to be renamed before the suite would
go green. The worker recorded that in the commit message as "the sweep enforcing its own contract,
which is the point of it" — that is the right instinct, and it means MP-1..MP-3 cannot rot the way
the original three checks did.

Most valuable of all is the paragraph recording that mutation 3 initially did *not* fire because
`assertIn("Actors & roles", out)` also matches `PASS: Actors & roles section present`. The worker
hit round 3's exact defect class, noticed it, fixed all four instances, and wrote down the general
lesson. My independent audit of every assertion in both modules confirms those four are now
genuinely discriminating. That is a real internalization of the finding rather than a patch to the
literal thing that was reported.

## What went wrong, said plainly

The B-4 fix was applied one layer too shallow. The worker correctly identified that structure
detection and the internals scan had diverged, and routed every consumer through
`_render_blank_fences` — good, and the two bites prove it. But the shared regex those consumers all
delegate to was never examined, and it recognizes exactly one of the two fence syntaxes CommonMark
defines. So round 3's document, with `~~~` for ` ``` `, produces the identical thirteen-PASS FAIL=0
output on the identical flat requirement list.

The pattern across four rounds is now legible and worth naming: each round's fix has been correct
about the *mechanism it was shown* and has stopped at the boundary of the demonstration. Round 2 was
shown four heading shapes and pinned four heading shapes. Round 3 was shown a backtick fence and
pinned backtick fences. The fix that ends this loop is not another shape-specific patch — it is to
ask, once, what the full grammar of the construct is and cover it, which for fences means both
delimiters, variable run lengths, line anchoring, and the unterminated case.

---

## Required before SHIP

1. **B-5** — widen `_RENDER_FENCE_RE` to cover `~~~` fences, unterminated fences and fence runs
   longer than three characters, line-anchored. The validated candidate is in the B-5 section above.
   Verify in both directions: the four bypass documents must FAIL, and the two `~~~` false-positive
   probes (quoted `### REQ-099`, quoted `<!-- cluster: … -->`) must return to FAIL=0. Pin at least
   the tilde and unclosed shapes with `test_mp3_*` tests, and confirm each goes red with the widened
   regex reverted.

## Recommended in the same pass (none blocking)

2. **E4** — add a field-presence assertion over the manifest records so that deleting
   `functional_section` or `title` on a single record is detected; the four probes above are ready
   to use as bites.
3. **P3** — tighten the four substring-weak assertions (`"tool-contract REQ"`, `"intro prose"`,
   `"terminal period"`, `"coverage-and-gaps statement"`) to their FAIL phrasing, as was already done
   correctly for the three MP assertions.
4. Record the fixture-input SHA-256 digests (listed above) somewhere tracked, so the "still
   SHA-256 identical" claim is verifiable against a stored baseline rather than inferred from mtimes.
5. Round 3's items 5 and 6 (N-3 guide note on the 47-tree cliff; the F-1 PASS message that says
   "in the Overview" when the statement came from a dedicated `## Coverage and gaps` section) appear
   not to have been actioned. Both were advisory then and remain so; carrying them forward.

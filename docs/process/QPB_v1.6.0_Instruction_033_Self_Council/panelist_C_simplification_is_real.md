# Panelist C — charter (c): *simplification is real, not relabeled*

## VERDICT: SHIP (3 NITs, all documentation, all with verified replacement text)

Instruction 033, branch `1.6.0`. Python 3.14.6.
Round 1 `268959e` · round 2 `55768d5` · **round 3 `00713e2` (final)**.
Suite at `00713e2`, unmutated: **3041 tests, 3 errors** (the 3 known environmental
ones), 16 skipped. Tracked tree byte-identical at the end of all three rounds;
every mutation applied serially, `__pycache__` purged between runs, restored from
`shutil.copy2` snapshots.

Charter: *"deleted machinery is gone not renamed, one channel actually replaces
four, the cache is removed not hidden, and consent semantics survive the removal."*

---

# ROUND 3 — review of `00713e2`. SHIP.

## The five round-2 findings, verified fixed by execution

`scratchpad/panelC/probe_r3.py`:

| finding | probe | result |
|---|---|---|
| **D-1** "this module writes…" | `hasattr(dc,'Path')`/`hasattr(dc,'os')`; `classify_documents` return type | `False, False`; returns `dict` — and the docstring now attributes the write to `reference_docs_ingest` ✅ |
| **D-1** "reads it back nowhere" | poisoned `classification_manifest.json` (`{"POISONED": true}` + a forged tier-1 promotable record), then re-ran `classify_reference_docs` | record came back `default-tier4`; the forgery changed nothing ✅ |
| **D-1** stdlib-only sentence restored | read | restored verbatim, and it is true ✅ |
| **D-2** "NO CLASSIFICATION PATH WRITES EITHER" | ran `classify_documents` + `classify_reference_docs` + `ingest` on a fresh tree | `classification_reads.json` absent, `qpb_decisions.txt` absent ✅ |
| **D-2** the named exception | then called `record_operator_decision` | `qpb_decisions.txt` created — the docstring names exactly the right writer ✅ |
| **D-3** cite/ shim paragraph | `cite/contract.go` and `cite/spec.md`, then a `background` line | flagged doc `operator-confirmation-required` + `refused_promotions`; clean doc `operator-authoritative`; revocation → `operator-background` ✅ |
| **D-5** trailing whitespace | line-by-line `rstrip` compare across revisions | `c429811` 0 → `55768d5` 2 → `00713e2` **0** ✅ |

(My round-2 D-5 probe reported 86 hits at `00713e2`; that was my error, not the
code's — `[ \t]` inside a POSIX ERE bracket is the literal set `{space, backslash,
t}`, so it was matching every line ending in `t`. The Python `rstrip` count above
is the authoritative one and it is 0.)

## The parity guard: works in both directions, and I found its edge

This is the piece I most wanted to check, since you rated it above the five fixes.
Pristine: `test_classification_gate_v160` 18 tests, OK.

* **Bite E — a fact the gate warns on, dropped from the disclosure.** Replaced the
  disclosure's `unread` condition with `if False:`. Parity test **FAILS**:
  `AssertionError: '' is not true : disclosure is silent about unread_count while
  the gate warns`, with the subtest naming `fact='unread_count'`.
* **Bite F — a fact the disclosure renders, dropped from the gate.** Replaced the
  gate's `refused_promotions` condition with `if False:`. Parity test **FAILS**:
  `AssertionError: 0 not greater than or equal to 1 : gate is silent about
  refused_promotions` (plus 2 pre-existing gate tests). Both directions confirmed
  independently of your B47/B48.
* **Bite G — the edge.** I wired a *new* fact (`stale_read_count`) into the gate
  only, taught the disclosure nothing, and did not extend the parity list. Full
  module: **18 tests, OK.** The guard is only as good as its hand-written
  enumeration, and the case it misses is precisely the instruction-034 shape it
  exists to prevent.

That last one has a verified 3-line fix that adds no shipped parts — derive the
list from the gate's own source instead of trusting it to be maintained:

```python
import inspect, re
src = inspect.getsource(quality_gate.check_classification_manifest)
consulted = (set(re.findall(r'manifest\.get\(\s*"([a-z_]+)"', src))
             | set(re.findall(r'get_str\(\s*manifest\s*,\s*"([a-z_]+)"', src)))
self.assertEqual(consulted - {label for label, _ in facts}, set(),
                 "the gate consults a manifest key this parity list does not cover")
```

Run against the bitten gate it reports
`NOT covered by the parity list: ['stale_read_count']` and fails; against the
pristine gate the two sets are equal. See **N-1**.

## N-1 (NIT) — the parity guard's fact list is hand-maintained

Reproduction: bite G above (new gate fact, list not extended → 18 tests OK). Fix:
the five lines quoted above, verified to catch it and to pass clean at `00713e2`.

## N-2 (NIT) — the D-4 fix introduced two clauses that are false when the model actually read the document

The backstop clause now reads: *"It assigns no GENRE — the record's ``category``
stays empty … — and it never demotes anything the model judged."* With a live read
in play, both halves come apart:

```
bare CVE doc            -> tier 4 operator-confirmation-required  category None
CVE doc + MODEL SAID 1  -> tier 4 operator-confirmation-required  category 'specification'
   model judged tier 1; record is tier 4
```

`category` does *not* stay empty — it stays whatever the model wrote, because the
backstop simply does not touch it. And the record is tier 4 while the model said
tier 1, so the backstop plainly does override the model's tier downward. The
*intent* is right and the behaviour is right; the sentence over-claims in the one
case that matters. Suggested: *"It assigns no GENRE — it never writes ``category``,
so whatever the model read the document to be survives on the record — and it makes
no classification: it withholds citation, producing a tier-4, non-promotable record
in its own queue regardless of the tier the model assigned."*

## N-3 (NIT) — the rewritten `cite/` docstring contradicts itself on "floor", four lines apart

`classify_reference_docs`'s docstring now says *"the backstop is not a floor"* and
then, two lines later, *"when None, the floor still runs and floor-passed docs
default to Tier 4"*; its summary line still reads *"classify all reference docs over
the deterministic floor."* Five occurrences of "floor" in a docstring whose new
paragraph exists to say the thing is not one. Also one 100-column line where the
parenthetical runs into the `llm_classifier` sentence. Fix: finish the substitution
— *"classify all reference docs over the hard-signal backstop"* in the summary, and
*"when None and no reads artifact exists, the backstop still runs and unread docs
default to Tier 4"* below; start `llm_classifier` on its own line.

## Why this ships

Everything remaining is a clause in a comment with replacement text I have verified.
Nothing behavioural is outstanding: across three rounds every load-bearing claim in
the module now matches what the code does under execution, the three deletions left
no reader, the parity guard catches drift in both directions, and the suite is
3041/3-environmental with the tree clean. A fourth blocking round over subordinate
clauses would itself be the failure mode this charter names — effort growing without
correctness growing.

## Complexity, final

| revision | code | branches | consts | raw lines |
|---|---|---|---|---|
| `c429811` pre-033 | 1071 | 195 | 56 | 2298 |
| `268959e` round 1 | 1340 (+269) | 283 (+88) | 72 (+16) | 3017 (+719) |
| `55768d5` round 2 | 1330 (+259) | 280 (+85) | 70 (+14) | 3025 (+727) |
| **`00713e2` final** | **1329 (+258)** | **280 (+85)** | **70 (+14)** | **3042 (+744)** |

**Net against pre-033: +24.1% code, +43.6% decision branches, +14 module constants,
+32.4% raw lines.** The three review rounds moved executable size by −11 lines and
−3 branches while adding +25 raw lines of accurate description — which is the right
trade and also, precisely, the shape of the finding.

---

# ROUND 2 — review of `55768d5`

## What I was asked to check

**(1) Does the rewritten module docstring match the code?** I checked it against
behaviour rather than reading it (`scratchpad/panelC/probe_docstring.py`). **The
decision model it describes is correct — every one of the seven ordering claims
passes.** Two sentences at the end of it do not match the code, and one sentence I
flagged in round 1 survived the fix. All three are documentation; all three are
one-line.

**(2) Did the three deletions leave a reader?** No. Verified below.

## Verified: the docstring's model is right

| docstring claim | probe | result |
|---|---|---|
| "Not a filename, not an extension, not a document's own say-so" | prose `upstream_notes.thrift`; self-claiming `.md` | both `tier 4 operator-confirmation-required` ✅ |
| 0. operator demotion outranks everything | `background` line on a valid `.proto` | `tier 4 operator-background` ✅ |
| 1. backstop runs FIRST | advisory renamed `api.proto` | `operator-confirmation-required`; Lane A never reached ✅ |
| 2. Lane A parses; a tier-3/4 read still demotes it | genuine proto; then same proto + model tier 4 | `tier 1 contract lane content-validated`; then `tier 4 llm` ✅ |
| 4. operator promotion of a flagged doc must NAME the signal | unnamed vs named reason, via `qpb_decisions.txt` | refused; then `tier 1 operator-authoritative` ✅ |
| 5. Lane B cited + disclosed `unconfirmed` | model read tier 1 | `lane model-read`, `confirmation unconfirmed` ✅ |
| 6. "the manifest distinguishes" read-as-context from nobody-read | one doc read tier 4, one not read | `llm` vs `default-tier4`, `unread_count 1` ✅ |
| "WHAT IS DELETED … not hiding under another name" | `hasattr` sweep over all 15 named symbols + the 3 ingest loaders | all absent ✅ |

That is the substance of the rewrite and it is sound. The front door now describes
the shipped module.

## D-1 (FIX-REQUIRED) — the new docstring's last sentence is false: this module writes nothing

> *"This module writes ``quality/classification_manifest.json``, which is an
> OUTPUT…"*

`doc_classification.py` performs **no filesystem operation of any kind**:

```
$ grep -nE "write_text|open\(|Path\(|\.mkdir|json\.dump|io\.|os\." .../doc_classification.py
$ echo $?
1
>>> hasattr(dc, "Path"), hasattr(dc, "os")
(False, False)
>>> type(dc.classify_documents([("reference_docs/s.md", SPEC)], generated_at="X"))
<class 'dict'>
```

It imports `hashlib`, `inspect`, `json`, `re`, `dataclasses`, `datetime`, `typing`,
`xml.etree` — no `pathlib`, no `os`. `classify_documents` **returns a dict**;
`reference_docs_ingest.classify_reference_docs` (line 1117) writes the file.

The half of the sentence that matters — *"an OUTPUT: regenerated every run and read
back by nothing"* — is true and worth keeping. The subject is wrong. And the fix
**deleted a true sentence to make room for it**: the old docstring's closing line,
*"This module is deliberately dependency-free (stdlib only) so it is trivially
bundle-portable and unit-testable without the rest of the harness,"* was accurate,
load-bearing for the bundle story, and is now gone.

**Fix.** *"The classification manifest ``quality/classification_manifest.json`` —
written by ``reference_docs_ingest`` from what this module returns — is an OUTPUT:
regenerated every run and read back by nothing. This module itself touches no files
and imports only the standard library, so it stays bundle-portable and
unit-testable on its own."*

## D-2 (FIX-REQUIRED) — "Neither is written by a run" is false, and it undercuts its own argument

> *"WHAT PERSISTS BETWEEN RUNS: the operator's confirmed decisions
> (``reference_docs/qpb_decisions.txt``), and the agent's per-document reads
> (``quality/classification_reads.json``). **Neither is written by a run** — that is
> what keeps the second from being the cache again."*

```
qpb_decisions.txt existed before record_operator_decision: False; after: True
```

`record_operator_decision` (`reference_docs_ingest.py:819`) writes
`qpb_decisions.txt`, and it is called **during a run** — the phase-1 guide's own
step 3 shows the agent invoking it at the end-of-Phase-1 review. The reads file is
likewise written during a run: the guide says *"write your reads, then run the
ingest."* So as written, both fail the test the sentence sets.

This matters more than a wording slip, because the sentence is the load-bearing
argument for why the reads file is not the cache — and if *"not written by a run"*
were the criterion, **the reads file would fail it too.** The property that actually
holds, and that the code enforces, is narrower and stronger: *no classification path
writes either file.* `classify_documents`, `classify_reference_docs` and `ingest`
never write them (round 1: grep finds no writer; pinned by
`test_ingest_never_writes_the_read_file`). The only writers are an operator relaying
consent through `record_operator_decision`, and the agent recording a read it
actually performed.

**Fix.** *"Neither is written by classification. No code path in this module or in
``ingest``/``classify_reference_docs`` writes either file — the decisions file is
written only by ``record_operator_decision`` relaying an explicit operator
instruction, and the reads file only by the agent that did the reading. That is what
keeps the second from being the cache again: a run never persists its own verdict."*

## D-3 (FIX-REQUIRED) — the round-1 C-2 site that survived the fix, and it is behaviourally false

`classify_reference_docs`'s docstring (`reference_docs_ingest.py:999-1001`) got its
"Reuses a prior manifest" sentence corrected, but the sentence two lines above it —
which my round-1 C-2 table flagged as *"false on both counts"* — is unchanged:

> *"``cite/`` placement is honored as an explicit operator pre-classification (it
> promotes past the implementation floor, exactly like the sidecar — but never past
> the advisory floor)."*

Verified false by execution:

```
cite/contract.go -> tier 4  operator-confirmation-required  promotable False
refused_promotions: ['reference_docs/cite/contract.go']
=> cite/ placement promotes past the implementation floor: False
```

`cite/` placement now seeds an `operator-authoritative` decision whose reason is
`CITE_MIGRATION_REASON`, which names no signal, so a backstop-flagged `cite/`
document is **refused** — the opposite of the documented behaviour. "The sidecar" is
a deleted channel, and "the floor still runs" in the next sentence names a deleted
concept (it is the backstop).

**Fix.** *"``cite/`` placement is a one-release migration shim: it pre-seeds the one
operator channel with a labelled, revocable ``authoritative`` entry, which a later
``background`` line supersedes. Because the seeded reason names no signal, a
``cite/``-placed document carrying a CVE/GHSA identifier, an advisory URL or source
code is REFUSED and listed in ``refused_promotions`` — placement is not an
acknowledgment. When ``llm_classifier`` is None and no reads artifact exists, the
backstop still runs and unread docs land at Tier 4."*

## D-4 (NIT) — "assigns no genre and no tier" is imprecise about the record

The backstop clause says it *"assigns no genre and no tier and never demotes."* The
record it produces carries `tier: 4, promotable: False`:

```
CVE doc -> tier 4 operator-confirmation-required  promotable False  category None
```

The *operator-facing* claim holds — `category` is genuinely `None`, and the show
gives these their own **"I need your word on these before I quote them"** section
rather than listing them as background. But a reader of the record sees a tier. The
phrasing is inherited from the pre-existing backstop comment block and the guide, so
it is not new; the rewrite was the moment to make it exact. Suggest: *"assigns no
genre and never decides that a document is background — its record sits at tier 4
only in the sense of 'not being quoted yet', in its own queue."*

## D-5 (NIT) — two trailing-whitespace lines introduced

`git show 55768d5 | grep -nE "^\+.*[ \t]+$"` → 2 hits, both docstring continuation
lines (in `_accepts_hints` and `classification_disclosure`). No lint gate catches
them; cosmetic.

## Verified: the three deletions left no reader

* **`_WSDL_NAMESPACES`** — zero references anywhere in the tree.
* **`_OPERATOR_RULES`** — only its own tombstone comment plus two historical process
  documents (`outputs/030…`, `Instruction_030_Self_Council/synthesis.md`), which are
  correctly historical records and should not be edited.
* **The `unwired → wired-ok` upgrade branch** — no test asserted the transition
  (`grep CLASSIFIER_WIRED_OK bin/tests/*.py | grep -i "unwired|upgrade|refin"` →
  nothing). Round 1 proved it unreachable by enumeration and by a `raise` bite that
  the full suite did not notice.

Full suite at `55768d5`: **3040 tests, 3 errors** — identical to the round-1
baseline. A deletion commit that moves no number is the right shape.

## Verified: the C-7 fix is load-bearing, not just relocated

The point of C-7 was that the leg had to *exercise* the gate. Bite D — replacing
`quality_gate.check_classification_manifest`'s unconfirmed-count condition with
`if False:` — now **fails** `test_read_and_judge_033` (1 failure) as well as
`test_classification_gate_v160` (2 failures). Under the pre-fix leg it could not
have: that leg only called `classification_disclosure`, which a gate change cannot
affect. The test now catches a silently-disarmed gate.

## On `classification_disclosure`: keep it, as you did

I agree with the call, and I'd add one thing. Your reasons check out — the gate
deliberately re-derives (`quality_gate.py:8062`: *"the gate does not import the
classifier module"*), and the Overview / Stage-1 legs invariant 8 names were never
wired, which predates 033. Deleting it would delete the eight tests that pin the
disclosure *wording*, and those are the pins that caught instruction 032's
Panelist-B R6-3 finding. A stated residual in the docstring is the right resolution
for a gap you are not closing under this instruction.

The one thing that is now unpinned is **drift between the two renderings.** I
checked: they currently cover the same seven facts, so there is no drift today — but
instruction 033 added five facts to both copies by hand, and nothing would have
noticed if it had added them to only one. A single parity test (every manifest key
the gate warns on has a `classification_disclosure` clause, and vice versa) closes
that for the cost of one test and zero shipped parts. Recommended, not required.

## C-4 and C-6: declines accepted

**C-4** — accepted, and your reason is better than my finding. `code_heavy` does land
on the record either way, an embedding caller may supply a three-argument callable,
and "the agent read the document itself and needs no prompting" is the right account
of why the shipped path skips it. Recorded in `_accepts_hints`'s docstring where a
reader meets it. That is the correct disposal of an inert-but-intentional part: name
it, don't delete it, don't leave it silent.

**C-6** — accepted on the reasoning I gave you. Threading a decision's reason through
the classifier to change one sentence is exactly the kind of part this layer should
stop growing, and the shim seeds `operator-authoritative` so the two cases are
genuinely identical at that point in the record. Both readings tell the operator
something true. Revisit when `cite/` retires and the seed goes with it.

## Complexity, re-measured at `55768d5`

| revision | code | branches | module consts |
|---|---|---|---|
| `c429811` pre-033 | 1071 | 195 | 56 |
| `268959e` round-1 HEAD | 1340 | 283 | 72 |
| `55768d5` round 2 | **1330** | **280** | **70** |

Net against pre-033: **+259 code (+24.2%), +85 branches (+43.6%), +14 constants.**
The deletion commit moved the needle by −10 code / −3 branches / −2 constants, which
is the honest size of the dead machinery — small, as expected. It does not change
the finding, and C-1 was never a code obligation.

---

# Closing statement for the Council synthesis — charter (c), final

*(Written at round 3, `00713e2`. This is the version for the synthesis.)*

Instruction 033's premise was that an accreted mechanical-classification tower would
be replaced by the model's read. Measured across the four steps and twelve fix-up
commits, that is **half true, and the half that is true is the half that matters to
the operator.**

What is genuinely simpler is the surface a human touches: **three operator-authored
override files collapsed to one** (verified — the superseded three are dead, each
raises a conversion note, and `cite/` is a real revocable shim rather than a
permanent fifth channel), and **ten floor rules reduced to seven**, with the three
that encoded genre judgments — advisory, implementation, background-name — gone
along with the `_SPEC_NAME_TOKENS` filename tables that were approximating a read
from filenames. Those deletions are real: I checked every named symbol and none has
reappeared under another name.

What is not simpler is the machine. The layer is **+24% code and +44% decision
branches** against its pre-033 baseline, and the two steps the instruction bills as
*"the simplification"* are the two largest positive rows in the table: replacing the
genre floors with the read cost +119 code and +43 branches; collapsing four channels
into one cost +74 and +15. Step 4 — removing the cache — is the only step that made
anything smaller, and the Council's own eleven fix-up rounds added back more than it
removed. The rule-ish vocabulary a reader must hold went from 10 to 15; the manifest
doubled its top-level keys; one persisted machine-judgment input (the cache) was
retired and another (`classification_reads.json`) took its place.

So the honest sentence is: **the mechanical genre tower was replaced by a
provenance-and-disclosure tower of larger size.** That is not a failure. Three-lane
provenance, the `unconfirmed` status carried end-to-end, the named-signal
confirmation, and loud unread/refused/awaiting accounting are things the predecessor
did not do at all, and none of them is free. Consent survived the collapse intact —
content-keyed, live-file, operator-authored-only, forgery-proof, named-signal, all
four mutation-bitten — and the read artifact cannot substitute for any of it, because
the boundary is structural at the call site rather than a promise.

The instruction's real recurring defect was never complexity. It was **claims that
outlived their referents**: a module docstring that survived four steps and ten
review rounds still advertising the extension carve-out step 1 closed; five comments
describing a cache step 4 deleted; a test leg named for a gate it did not exercise;
an invariant naming a consumer with no caller. Every one read as coverage, and every
one was found by asking the code rather than reading it.

And then the fix for that finding introduced two more of the same, in the same file,
one round later — and the fix for *those* introduced a third. That is not
carelessness; it is the actual half-life of a description. The lesson worth carrying
out of 033 is the method, not the count: **a claim in a comment is untested code, and
the moment you write a true one you have created a future false one.** The only
durable answers are the ones that cannot drift — a guard derived from the source it
guards, a test that exercises the consumer it is named for, a deletion. That is why
the parity guard is worth more than the five fixes it shipped beside, and why its one
remaining weakness is that its fact list is still hand-written (N-1).

**Final word on the measurement.** The table is not an indictment and should not be
published as one. Read it as the price list. Closing a reproduced publish-gate
exploit cost +43 code and +11 branches; replacing filename tables with a read that
carries its own provenance cost +119 and +43; collapsing four operator channels into
one cost +74 and +15; deleting the cache returned −61 and −16. Nobody gets to spend
the first three and book the fourth's sign. What the instruction bought is real and
was not previously purchasable at any price — a citation that says which lane it came
from and whether a human ever looked at it — and what it cost is a machine a quarter
larger with 44% more branches to hold. Both belong in the output, in that order.

The claim I would let the release make is narrow and true: **the operator's surface
got simpler and the machine's did not.** Three override files became one; ten floor
rules became seven; the filename tables that guessed at genre are gone and nothing
took their place. That is the whole of the simplification, it is the part an adopter
touches, and it is worth having said plainly rather than sold as more.

---

# ROUND 1 — review of `268959e` (findings and disposition)

Retained for the record. Numbers and reproductions unchanged.

## The measurement

Non-blank, non-comment, non-docstring **code** lines and `if`/`ifexp`/`bool-op`
**decision branches**, via `ast` + `tokenize` over `git show <rev>:<path>`
(`scratchpad/panelC/steps.py`):

| revision | doc_cls code | br | ingest code | br | **TOTAL code** | **TOTAL br** | delta |
|---|---|---|---|---|---|---|---|
| `c429811` pre-033 base | 629 | 116 | 442 | 79 | **1071** | **195** | — |
| `44c58a8` step 1 Lane-A parse | 671 | 127 | 443 | 79 | 1114 | 206 | +43 code, +11 br |
| `aba49ef` step 2a read+lanes | 791 | 170 | 442 | 79 | 1233 | 249 | **+119 code, +43 br** |
| `ea47b4a` step 2b prompt | 791 | 170 | 442 | 79 | 1233 | 249 | +0, +0 |
| `094f9ac` step 3 one channel | 803 | 174 | 504 | 90 | 1307 | 264 | **+74 code, +15 br** |
| `f87c87f` step 4 cache removed | 749 | 159 | 497 | 89 | 1246 | 248 | **−61 code, −16 br** |
| `268959e` round-1 HEAD | 801 | 181 | 539 | 102 | **1340** | **283** | **+94 code, +35 br** |

Raw file lines 2296 → 3015 (+31%); comment-only lines 514 → 796 (+55%).

| | pre-033 | round-1 HEAD |
|---|---|---|
| module-level constants (both files) | 56 | 72 |
| module-level functions (both files) | 45 | 55 |
| `RULE_*` identifiers | 10 | 7 |
| lane / confirmation / backstop constants | 0 | 8 |
| → rule-ish concepts a reader must hold | **10** | **15** |
| `classification_playback` statuses | 6 | 8 |
| classification-manifest top-level keys | 7 | 14 |
| operator-authored input files | **3** | **1** |
| machine artifacts persisted | 2 | 3 |
| machine artifacts that are **inputs** | 1 (cache) | 1 (`classification_reads.json`) |

Name diff: `doc_classification.py` removed 12 constants / 4 functions, added 24 / 10.
`reference_docs_ingest.py` removed **0** constants / 3 functions, added 4 / 7 — so
"four channels collapse to one" netted +4 constants and +4 functions in the module
that owns them.

## Round-1 findings and disposition

| id | finding | disposition at `55768d5` |
|---|---|---|
| **C-1** (FIX) | the simplification claim is unsupported by measurement | accepted; discharged in the output document, table taken verbatim |
| **C-2** (FIX) | six production sites document deleted machinery as live; the 58-line module docstring was **byte-identical to pre-033** | fixed for 5 of 6 sites; **one survives — see D-3**; two new false claims introduced — **D-1, D-2** |
| **C-3** (FIX) | 5 dead symbols + 1 unreachable branch reading as coverage | `_WSDL_NAMESPACES`, `_OPERATOR_RULES` and the `unwired → wired-ok` branch deleted, no reader left (verified); `classification_disclosure` kept as a stated residual — **agreed** |
| **C-4** (NIT) | inert genre-hint layer unreachable by the shipped classifier | declined with the reason recorded in `_accepts_hints` — **accepted** |
| **C-5** (NIT) | guide said "the read happens IN the run, every run" vs pinned cross-run reuse | guide reworded — verified |
| **C-6** (NIT) | a confirmed `cite/` doc still renders as placement | declined with the reason recorded in `_review_reason` — **accepted** |
| **C-7** (NIT) | the "gate WARN" test leg asserted on a function no gate calls | fixed and **proven load-bearing** by bite D |

## Round-1 verification that still stands

* **Three superseded channels dead** — a corpus carrying `qpb_authoritative.txt` /
  `qpb_promote.txt` / `qpb_advisory_rescue.txt` with a live promotion leaves both
  targets at `tier 4 operator-confirmation-required`, each raising `conversion_note`
  + `legacy_control_files`.
* **`cite/` is a real shim** — seeds `operator-authoritative tier 1`, the show labels
  it *"that folder is going away next release"*, a later `background` line
  supersedes it → `tier 4 operator-background`, 0 `FORMAL_DOC` records.
* **A read cannot manufacture consent** — an entry with `tier: 1` plus hostile extras
  (`operator_decision`, `advisory_rescue`, `sidecar_promote`, `promotable`,
  `floor_rule`) on a CVE doc and a `.go` file leaves both at
  `operator-confirmation-required`, `citable_count 0`.
* **Bite A** (content-key stripped from the operator decision) — a wrong-sha
  promotion goes `tier 4 default-tier4` → `tier 1 operator-authoritative`; caught by
  2 tests. On a flagged doc it changes nothing, because `advisory_rescues` is
  independently content-keyed — defence in depth.
* **Bite B** (`names_every_signal` → `return True`) — unnamed promotion goes
  `tier 4 …refused` → `tier 1 operator-authoritative, refused: None`; caught by
  9 tests. The instruction-025 speed-bump survives in kind.
* **Bite C** (`raise` in the `unwired → wired-ok` branch) — full suite unchanged at
  3040/3, confirming the branch unreachable.

---

## Artifacts

`/private/tmp/claude-501/…/scratchpad/panelC/` — `steps.py`, `measure.py`,
`names.py`, `probe_stale_read.py`, `probe_channels.py`, `probe_E.py`,
`probe_docstring.py` (round 2), and the `.pristine` snapshots.

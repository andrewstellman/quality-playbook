# Output — instruction 033: simplify the sources/classification layer

**Status: complete. Unanimous SHIP from all three self-Council charters.**

Branch `1.6.0`. Four implementation steps (`44c58a8`, `aba49ef`, `ea47b4a`,
`094f9ac`, `f87c87f`) plus sixteen Council commits (`17a4fcc` … `081ffbd`).

**Suite: 3041 tests, 0 failures, 17 skipped. Python 3.14.6.** Three errors are
environmental — `test_channel_install_e2e_090b` (×2) and
`test_full_build_publish_path_090f`, all venv / console-script install — and I
verified them failing at `f87c87f` in a clean detached worktree before attributing
them elsewhere. Nothing else fails.

---

## Read this first: the instruction's premise did not hold

The instruction's stated purpose is to *replace an accreted mechanical-classification
tower*. Panelist C was asked to measure that claim rather than confirm it, and told
plainly that a finding of "partly illusory, with numbers" was worth more than a
confirmation. It measured every step commit:

| revision | code | branches | delta |
|---|---|---|---|
| `c429811` pre-033 | 1071 | 195 | — |
| step 1 — Lane A parse validation | 1114 | 206 | +43, +11 |
| step 2 — read-and-judge, three lanes | 1233 | 249 | **+119, +43** |
| step 3 — one channel replaces four | 1307 | 264 | **+74, +15** |
| step 4 — cache removed | 1246 | 248 | **−61, −16** |
| HEAD (+13 fix-ups) | **1329** | **280** | **+258 (+24.1%), +85 (+43.6%)** |

Step 4 is the only negative row. The two steps billed as "the simplification" are
the two largest positive ones. I re-measured independently with a different branch
definition and got +24.9% code / +39.3% branches over the same files — the absolute
counts move with what you call a branch, the direction does not. **No counting rule
makes this a shrink.**

C's closing reading, which I've adopted rather than argued down:

> The table is a price list, not an indictment. Closing the publish-gate exploit cost
> +43/+11; the read-with-provenance cost +119/+43; one channel from four cost +74/+15;
> deleting the cache returned −61/−16. Nobody spends the first three and books the
> fourth's sign. The claim the release should make is narrow and true — **the
> operator's surface got simpler and the machine's did not**.

What genuinely shrank is the surface a user touches: **three override files to one,
ten floor rules to seven**, filename tables gone with nothing in their place.

My own reading is that the *premise* was wrong, not the execution. A mechanical genre
classifier is deterministic and never has to say who decided or whether anyone
looked. A model's read needs a channel, content keying, provenance, disclosure,
unread accounting and a confirmation path — none of which the old design needed, and
none of which it could have provided. The trade is real. The label is not.

**This has a consequence beyond wording:** the design doc's §8a framing says the
tower gets *replaced*. Left uncorrected, the next instruction inherits a baseline
that was never true, authored by someone with no reason to re-measure. Correcting
§8a is a design decision and is not mine to make — flagged, not actioned.

---

## Step-by-step: before, after, and the test that holds it

### Step 1 — Lane A becomes a parse, not an extension

**Before:** a `.proto` / `.wsdl` / `.thrift` / `.d.ts` / IDL **extension** made a
document an authoritative contract, citable with no read and no operator. **After:**
`contract_content_validation` parses; the extension only *routes* to Lane C.

Test: `bin/tests/test_lane_a_parse_validation_033.py` (49 tests).

```
[1] prose in upstream_notes.thrift   -> tier=4 rule=operator-confirmation-required promotable=False
[2] "we support openapi: 3.1" prose  -> tier=4 rule=default-tier4
```

Both were `tier=1 promotable=True` before. The exploit and the F1 signature-in-prose
bypass are closed, and neither is silently background — [1] is routed to the operator.

**F2 per-format, all five anchorless formats, both content directions:**

```
svc.thrift       tier=4 rule=operator-confirmation-required promotable=False
schema.graphql   tier=4 rule=operator-confirmation-required promotable=False
schema.graphqls  tier=4 rule=operator-confirmation-required promotable=False
api.idl          tier=4 rule=operator-confirmation-required promotable=False
types.d.ts       tier=4 rule=operator-confirmation-required promotable=False
```

Never auto-cited, never silently background, promotable by the operator.

### Step 2 — read-and-judge replaces the genre floors, three lanes wired

**Before:** advisory / implementation / background-**name** floors plus
`_SPEC_NAME_TOKENS` / `_NON_SPEC_NAME_TOKENS` filename tables decided genre. A
prefix match had pinned `issue_tracker_api_spec.md` — a real spec — to unrescuable
background. **After:** the model reads the document; the mechanical layer keeps only
a hard-signal backstop that assigns no genre and answers one question — *may this be
cited without asking?* — with one answer, no.

Test: `bin/tests/test_read_and_judge_033.py` (17 tests).

**Lane B `unconfirmed`, end to end:**

```
tier=1 lane=model-read confirmation=unconfirmed unconfirmed_citable_count=1
show carries "That was my own call — tell me if I've got it wrong."  -> True
the word "unconfirmed" reaches the operator                          -> False
```

Cited, disclosed, and never in jargon.

### Step 3 — one override channel replaces four

**Before:** `qpb_promote.txt`, `qpb_advisory_rescue.txt`, `qpb_authoritative.txt` and
`cite/` placement asked the same question four ways. **After:** one content-keyed,
operator-authored `reference_docs/qpb_decisions.txt`; `cite/` survives one release
as a labelled revocable shim; the three superseded files are surfaced loudly and not
applied.

Test: `bin/tests/test_one_override_channel_033.py` (21 tests).

**Round-trip, named signal, live revocation:**

```
no decision              -> rule=operator-confirmation-required
reason "yes use it"      -> REFUSED at write time (names no signal)
reason names CVE-2024-43796 -> rule=operator-authoritative tier=1
line deleted             -> rule=operator-confirmation-required   (revoked)
```

### Step 4 — the reproducibility cache is removed

**Before:** content-keyed `prior_records` reuse, plus the guards that existed only
because of it. **After:** every run re-reads and re-derives; what persists is the
operator's consent.

Test: `bin/tests/test_no_cache_033.py` (10 tests).

**The forgery half — a hand-written prior manifest is simply overwritten:**

```
forged manifest claiming tier 1 llm -> rule=operator-confirmation-required tier=4 (ignored)
```

---

## Where the read lives (the Council's largest finding)

Step 4 removed `prior_records` — which was the only channel by which the agent's read
entered a run. What remained was a Python callable that **no production caller
supplies**. Lane B, the central mechanism of this instruction, could not produce a
byte-citable record in the shipped flow: ingest-then-read leaves the formal manifest
empty because the record is created during ingest; read-then-ingest has the ingest
regenerate the manifest and destroy the read.

Reproduced on real corpora before accepting it: re-ingesting `repos/chi-1.6.0` took
`FORMAL_DOC` from two Tier-1 records to **zero** with `zero_citable` true; express
and virtio the same, and virtio's document is `virtio-spec-behavioral-contracts.md`
— the case §8a names as the motivation for the classification review itself.

Closed with `quality/classification_reads.json`, agent-authored per run. Because the
instruction requires the read's location to be *specified* but does not legislate its
form, and step 4 had legislated on what may persist, **I put the options to the
operator rather than deciding alone**; they chose this shape.

Why it is not the cache step 4 deleted — as tests, not claims
(`bin/tests/test_read_channel_033.py`, 25 tests):

1. **No classification path writes it** — not `classify_documents`, not
   `classify_reference_docs`, not `ingest`. This is the distinguisher. "Content-keyed"
   is not: *the deleted cache was content-keyed too*, and that was its defining
   feature.
2. A document with no matching entry is **unread and loud**, never quietly defaulted.
3. Content-keyed, so a read applies only to the bytes it was made against.
4. A read is a judgment, not a permission: `read says tier 1` on a CVE document still
   yields `rule=operator-confirmation-required tier=4`.

Verified end to end: **chi 2→2, express 1→1, virtio 1→1** across a re-ingest, each now
carrying `lane=model-read` / `confirmation=unconfirmed` — strictly better than
pre-033, which cited those same corpora with no provenance at all.

---

## Every kept consumer still works

`zero_citable` + the zero-authoritative banner; `classification_review`'s reason maps
(golden-render equality, regenerated and reviewed line by line); `_formal_tier`
read-never-relitigate; per-document isolation (byte-identical records with a hostile
sibling present); byte-verification untouched — the entire 033 diff contains not one
line of `_build_record_from_text`, `_citation_excerpt`, the sha computation or the
`role` emission; code still the Tier-3 fallback; the UX plain-language contract, with
no internal label reaching the operator.

**Newly loud:** five advisory gate WARNs (`unconfirmed_citable_count`,
`awaiting_confirmation_count`, `unread_count`, `refused_promotions`,
`conversion_note`). These did not exist — the provenance reached the show and
stopped, so a headless run grounded entirely on the model's own unconfirmed read
passed the gate in silence.

---

## Defects found and fixed

**Eight during implementation**, all mine, all caught by tests rather than review:
a sidecar that could launder a CVE advisory; a forged prior manifest that could
launder Lane C; the fix for that destroying a legitimate promotion; a guard keyed to
one rule when two applied; a refusal notice lost when sections moved; a reason
claiming "its file extension" after the extension arm was deleted; an isolation test
that could not fail; a plain `authoritative` clearing an implementation-source signal.

**Twenty-two more from the Council**, each reproduced before being accepted. The full
list with reproductions is in
`docs/process/QPB_v1.6.0_Instruction_033_Self_Council/synthesis.md`.

### The patterns, which matter more than the individual defects

**1. A check or claim keyed to something whose meaning moved out from under it.**
The dominant pattern. Five of the eight implementation defects; a security gate keyed
to a *rendered display string*; a comment justifying a correct line with a reason
that had stopped applying; and the module docstring — 58 lines, **byte-identical to
pre-033** after four steps and thirteen fix-up rounds, still advertising the
`.d.ts`/IDL carve-out that step 1 exists to close.

And the sharpest instance: **the fix for that docstring introduced two more of the
same, and the fix for those introduced a third.** Not carelessness — the half-life of
a description. The durable answers are the ones that cannot drift.

**2. An expectation that cannot fail.** An isolation test whose corpus made the
property vacuous; an empty acknowledgment token passing the named-signal gate by
having nothing to name; a test asserting the "gate WARN" leg against a function no
gate calls — so the gate could have been disarmed entirely and it would still have
passed. It nearly was.

**Three test names in this Council asserted properties their bodies did not check,
two of them mine.** A test name is a claim like any other.

**3. A guard correct on one arm and absent on its sibling.** Found four times, and it
moved each time: advisory vs sidecar keying; the JSON vs YAML `info` bar; a
per-document skip against per-format anchors; and finally the handoff *between* arms
confusing "no" with "not mine". Panelist A's formulation: *when a guard has more than
one arm, the finding is usually not in an arm, it's in the difference between them.*

**4. A unit-tested seam no test ever traverses.** B-1's lesson: the tests were
thorough, adversarial and mutation-bitten, and tested the *function* by handing it a
callable no production caller supplies. A suite that exercises every unit and never
exercises the path the product takes reports health right up to the point a user
finds the hole.

### Mutation discipline

48 bite executions on the implementation side, both clauses each time. **Five
escaped, and each escape was worth more than the bites that landed:** two proto
anchors that every test input indented together; a per-arm test that only exercised
one arm (whose escape revealed a branch no test could distinguish, leading to its
deletion); a branch decided from one parse and re-derived from another; an unread
file becoming a whole-corpus classifier error; and a digest-normalisation guard.

The guard-of-guards was found decayable too: the gate/disclosure parity test's fact
list was hand-written, so panelist C wired a new fact into the gate alone and the
test passed. It now derives the list from the gate's own source.

---

## Remaining release items

1. **The design doc's §8a framing** describes 033 as replacing the tower. The
   measurement says otherwise. Correcting it is a design decision — flagged, not
   actioned.
2. **`classification_disclosure` has no production caller.** The gate leg is real but
   deliberately re-implemented (the gate must not import the classifier); the Overview
   and Stage-1 playback legs invariant 8 names were never wired — a gap predating 033.
   Recorded as a stated residual in the function's own docstring.
3. **`cite/` retires next release**, taking its seeded-decision shim with it.
4. **Six stated residuals** are recorded in `synthesis.md` §5, each also carried in
   the code rather than only in a commit message.

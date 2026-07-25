# Instruction 033 self-Council — synthesis

**Verdict: unanimous SHIP.** Three charters, twelve review rounds, sixteen commits
(thirteen numbered fix-ups plus three follow-ups) on top of the four
implementation steps.

| panelist | charter | rounds | outcome |
|---|---|---|---|
| A | promotion is un-bypassable-by-content-alone | 5 | SHIP |
| B | no regression / demotion-free | 4 | SHIP |
| C | simplification is real, not relabeled | 3 | SHIP |

Suite at close: **3041 tests, 0 failures.** Three errors are environmental
(`test_channel_install_e2e_090b` ×2, `test_full_build_publish_path_090f` — venv /
console-script install), verified pre-existing at `f87c87f` in a clean detached
worktree. Full verdict files, with every round retained, are in
`runner/quality-playbook/reviews/033_self_council/`.

---

## 1. The headline finding: the instruction's premise did not hold

Panelist C was asked to measure the claim rather than confirm it, and was told
explicitly that a finding of "partly illusory, with numbers" was more valuable than
a confirmation. It measured code lines (blank/comment/docstring stripped via `ast` +
`tokenize`) and decision branches at every step commit:

| revision | code | branches | delta |
|---|---|---|---|
| `c429811` pre-033 | 1071 | 195 | — |
| step 1 — Lane A parse validation | 1114 | 206 | +43, +11 |
| step 2 — read-and-judge, three lanes | 1233 | 249 | **+119, +43** |
| step 3 — one channel replaces four | 1307 | 264 | **+74, +15** |
| step 4 — cache removed | 1246 | 248 | **−61, −16** |
| `76c9d29` HEAD (+13 fix-ups) | **1329** | **280** | **+258 (+24.1%), +85 (+43.6%)** |

Step 4 is the only negative row. The two steps the instruction bills as "the
simplification" are the two largest positive ones.

*These are panelist C's figures, produced by its own script.* Re-measuring
independently with a different branch definition gives 1124 → 1404 code
(**+24.9%**) and 234 → 326 branches (**+39.3%**) across the same two files. The
absolute counts depend on what one calls a branch; the direction and the order of
magnitude do not, and both measurements agree that the layer grew by roughly a
quarter in code and by appreciably more in branching. No counting rule makes this a
shrink.

**C's characterisation, adopted verbatim:** the mechanical genre tower was replaced
by a larger provenance-and-disclosure tower. Its closing statement is the fairest
reading available, and the release should make this claim and no wider one:

> The table is a price list, not an indictment. Closing the publish-gate exploit
> cost +43/+11; the read-with-provenance cost +119/+43; one channel from four cost
> +74/+15; deleting the cache returned −61/−16. Nobody spends the first three and
> books the fourth's sign. The claim the release should make is narrow and true —
> **the operator's surface got simpler and the machine's did not**.

What genuinely shrank is the only surface a user touches: **three override files to
one, ten floor rules to seven**, and the filename tables gone with nothing in their
place.

The honest reading is that the premise, not the execution, was wrong. A mechanical
genre classifier is deterministic and needs to say nothing about who decided or
whether anyone looked. Replacing it with a model's read requires a channel, content
keying, provenance, disclosure, unread accounting and a confirmation path — none of
which the old design needed, all of which it structurally could not provide. The
trade is real; the label "simplification" is not.

---

## 2. Findings that changed the shipped behaviour

Twenty-two findings were fixed across the three charters. These are the ones that
changed what the product does, each reproduced independently before being accepted.

### Promotion (charter A)

- **A-1 — operator consent leaked to swapped bytes.** The implementation arm keyed
  promotion on the *path* while the advisory arm one line above keyed it on
  *content*. An operator who approved `contract.py` had approved the path, so
  replacing the file's bytes inherited the promotion. Both arms are now `(path, sha)`.
- **A-2 — a quotation was read as the document's own format.** A `grpc-tutorial.md`
  whose fenced `proto` block held a syntax line and a message block validated as
  protobuf and was published as an authority — and the model *could not demote it*,
  because Lane A was implemented as "cited in every mode, no override". §8a rule 2
  has no Lane A carve-out. Both halves fixed.
- **R2-1 — the root cause behind A-2.** The first fix addressed one *shape*. Five
  further inputs still reached `tier=1 rule=contract`: an indented Markdown block, a
  reST `.. code-block:: proto`, an unclosed fence, a mismatched fence, and a column-0
  version line in prose. The reST case is structural — reST has no fences at all, so
  a scrubber can never reach it, and `.rst` is the benchmark corpus's own format.
- **A-3 — the document chose its own acknowledgment token.** The evidence an operator
  had to name was recovered by re-parsing the *rendered* detail string, so an advisory
  URL containing apostrophes yielded the token `e` and the reason "reviewed, it is
  fine" cleared a security gate. Evidence now travels as data.
- **R4-1 — a per-*document* skip against per-*format* anchors.** The fence-scrub
  carve-out was keyed on the file's extension while the protobuf arm ignores the
  filename entirely, so a deny-listed name switched the scrub off for arms unrelated
  to it. `grpc-tutorial.yaml` and `.json` came straight back to Tier 1.
- **R5-1 — "no" confused with "not mine."** The JSON arm returned the same `None` for
  "not my format" and "my format, rejected", so the YAML arm validated what the JSON
  arm had just refused, reaching a Tier-1 `FORMAL_DOC` end to end.

### Regression (charter B)

- **B-1 — Lane B was unreachable in the shipped flow.** The central mechanism of the
  instruction could not produce a byte-citable record. Step 2 made classification the
  model's read; step 4 removed `prior_records`, which was the only channel by which
  that read entered a run; what remained was a Python callable that **no production
  caller supplies**. There was no ordering that worked: ingest-then-read leaves the
  formal manifest empty because the record is created during ingest, and
  read-then-ingest has the ingest regenerate the manifest and destroy the read.
  Reproduced on real corpora — re-ingesting `repos/chi-1.6.0` took `FORMAL_DOC` from
  two Tier-1 records to zero with `zero_citable` true; express and virtio the same,
  and virtio's document is `virtio-spec-behavioral-contracts.md`, the case §8a names
  as the motivation for the classification review itself.

  Closed with `quality/classification_reads.json`, an agent-authored per-run artifact
  — the shape the operator chose when the options were put to them, since the
  instruction requires the read's location to be specified but does not legislate its
  form, and step 4 had legislated on what may persist. Verified end to end: chi 2→2,
  express 1→1, virtio 1→1, each now carrying `lane=model-read` /
  `confirmation=unconfirmed` — strictly better than pre-033, which cited those same
  three corpora with no provenance at all.
- **B-4 — the disclosure reached the show and stopped.** Step 2 requires the
  `unconfirmed` provenance to flow manifest → show → gate WARN → Stage-1 playback. A
  headless run whose entire grounding rested on the model's own unconfirmed read
  passed the gate in silence. Five advisory WARNs added.
- **B-2 — a dead allow-list entry that read as coverage.** WSDL 2.0 renamed its root
  element from `definitions` to `description`, so listing its namespace while
  requiring a `definitions` root made the entry unreachable. The test pinned the
  fiction, asserting a combination no real document has.
- **B2-1 — a bad read aborted the run and left a stale manifest.** An out-of-range
  integer tier escaped as a bare `ValueError` from a call site outside the
  classifier's try/except: not an `IngestError`, so the CLI printed a traceback
  instead of its diagnostic; the message named neither file nor document; and both
  manifests kept the previous run's contents, leaving a byte-citable record on disk
  with `generated_at` unchanged while the run appeared to fail.
- **B3-1 — the counter measured the wrong thing.** `unread_count` counted
  `default-tier4`, which is *untiered*, not unread — and the guide creates that
  difference on purpose ("if it could be the spec but you cannot tell,
  `candidate-spec` says exactly that"). An agent following its instructions was
  counted as never having looked, and the gate said "never read … background by
  default rather than by judgment" about a record whose own reason read *"I read all
  of it and still cannot tell."*

### Simplification (charter C)

- **C-2 — the front door had drifted furthest.** `doc_classification.py`'s 58-line
  module docstring was **byte-identical to pre-033** after four steps, thirteen
  fix-up rounds and +410 lines to that file. It still advertised the extension
  carve-out making `.d.ts`/IDL files auto-citable — the exact exploit step 1 exists
  to close — plus the deleted sidecar and the deleted cache. Five further sites
  repeated the cache claim, two of them verbatim the "ninth defect" the step-4 commit
  says it had already corrected in the guide.
- **C-3 — step 4 orphaned a branch and nothing noticed.** The `unwired → wired-ok`
  status upgrade was reachable only while the cache existed; with no classifier,
  `_classify` cannot emit `RULE_LLM` at all. Two dead constants went with it. An
  unreachable branch passes every test.

---

## 3. Four defect patterns

Each was found repeatedly, by different panelists, on different code.

### 3.1 A check or claim keyed to something whose meaning moved out from under it

The dominant pattern, and the one that survived the longest. Instances: five of the
eight implementation defects; the guide describing three deleted channels; a security
gate keyed to a *display string* (A-3); a comment justifying a correct line with a
reason that had stopped applying (R5-2); the module docstring (C-2); and — most
instructively — **the fix for C-2 introduced two more of the same, and the fix for
those introduced a third.**

C's reading is the right one: that is not carelessness, it is the half-life of a
description. The durable answers are the ones that *cannot* drift.

### 3.2 An expectation that cannot fail

An isolation test whose corpus made the property vacuous; an empty acknowledgment
token that passed the named-signal gate by having nothing to name; a test asserting
the "gate WARN" leg against a function no gate calls, so the gate could have been
disarmed entirely and the test would still have passed — it nearly was.

**Three test names in this Council asserted properties their bodies did not check,
two of them ours.** A test name is a claim like any other, and the only way to find
out is to execute the claim rather than read it.

### 3.3 A guard correct on one arm and absent on its sibling

Found four times, and it *moved* each time: advisory vs sidecar keying (A-1); the
JSON vs YAML `info` bar; a per-document skip against per-format anchors (R4-1); and
finally the handoff *between* arms confusing "no" with "not mine" (R5-1).

Panelist A's formulation, worth keeping:

> When a guard has more than one arm, the finding is usually not in an arm, it's in
> the difference between them.

### 3.4 A unit-tested seam that no test ever traverses

B-1's own lesson, in B's words:

> The tests weren't weak; they were thorough, adversarial and mutation-bitten. They
> tested the *function* by handing it a Python callable that no production caller
> ever supplies. The defect lived in the seam between two individually-correct
> components, and only running the flow the prompt documents, end to end, on a real
> corpus, found it. A suite that exercises every unit and never exercises the path
> the product takes will report health right up to the point a user finds the hole.

---

## 4. Method notes

- **Mutation bites, both clauses.** A bite counts as evidence only when the mutation
  is proven to change behaviour *and* the unmutated source is proven green on the
  identical invocation. 48 bite executions were run on the implementation side across
  the thirteen fix-ups; the panelists ran their own in addition (A reported 34 across
  five rounds, B and C smaller batches per round). The per-round counts are in the
  verdict files; only the implementation-side figure is first-hand here.
- **Escaped bites were the highest-value events.** Five escaped and each exposed a
  genuine hole a green suite had hidden: B9/B10 (both proto anchors indented in every
  input, so relaxing either alone changed nothing); B21/B22 (a per-arm test that only
  ever exercised one arm — and B22's escape is what revealed the RAML branch was
  untestable, leading to its deletion); B28 (a branch decided from one parse and
  re-derived from another, so mutating it was unobservable); B36 (an unread file
  becoming a whole-corpus classifier error, with no test pinning the status); B2-5 (a
  digest-normalisation guard, false-negative-shaped).
- **The guard that guards the guards.** The parity test between the gate and the
  disclosure was itself found decayable: its fact list was hand-written, so C wired a
  new fact into the gate alone and the test passed. It now derives the list from the
  gate's own source — reproduced here, where C's bite fails with "the gate reads
  manifest keys this parity test does not exercise".
- **Panelists must run sequentially** (the 032 lesson) — parallel panelists corrupt
  each other's from-disk snapshots.
- **Never race a backgrounded suite against your own mutations.** Panelist B produced
  a phantom failure this way and caught it itself.

---

## 5. Stated residuals

Carried deliberately, each recorded in the code rather than in a commit message:

1. The design's own two (§8a residuals): a valid-but-hostile contract decoy
   auto-cites; demotion is safe for integrity, not availability.
2. Protobuf files that legally omit `syntax`, and the 2023 `edition = "…"` form —
   both fall to Lane B rather than being dropped.
3. `classification_disclosure` has no production caller. The gate leg is real but
   deliberately re-implemented (the gate must not import the classifier); the Overview
   and Stage-1 playback legs invariant 8 names were never wired — a gap predating 033.
4. The last good manifests survive any `IngestError`; inherent to that path.
5. Cross-run reuse of the read artifact — real, chosen, pinned, and safe for the
   reason the code now leads with: **no classification path writes it.**
6. A `cite/`-placed document the operator also confirms explicitly renders as
   placement. Distinguishing the two would mean threading a decision's reason through
   the classifier to change one sentence; declined on charter C's own logic. Revisit
   when `cite/` retires next release.

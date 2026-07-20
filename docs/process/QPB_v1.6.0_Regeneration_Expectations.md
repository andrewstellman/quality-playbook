# v1.6.0 — regeneration expectations for the disjunctive acceptance clauses

*Written 2026-07-20 (instruction 002 item 5). Source: the Slice-1 readability
Council synthesis, Finding 2 (`Quality Playbook/Reviews/QPB_v1.6.0_Slice1_Readability_Council_Synthesis.md`).
Rule that prevents recurrence: `references/phase2_generation_guide.md` §
"One required behavior per requirement — no disjunctive acceptance", and the
matching rule in `bin/skill_derivation/prompts/pass_a_section.md`.*

## What this file is, and is not

**These are expectations for a future regenerated run. They are NOT edits to
the fixtures.**

`bin/tests/fixtures/render_contract_v160/{chi,express,virtio}/quality/REQUIREMENTS.md`
are snapshots of what the pipeline actually produced. Hand-polishing them would
turn the Feature C acceptance oracle into a test of hand-written exemplars that
no pipeline generates — the oracle would then pass while the pipeline still
emitted the defect. The fix for every row below lives at the **source** (the
generation guide and the Pass A prompt, both landed in instruction 002 item 1),
and is verified by regenerating, never by patching the artifact.

So this file exists to make the next regeneration **checkable against a written
expectation** rather than re-litigated from scratch. When a run regenerates
these three targets, diff its output against the "expected resolved form"
column. A row that still reads like the "current text" column means the
prompt-level rule did not take, which is a finding about the rule — not an
invitation to edit the document.

## Why these five

All nine readability-Council panelists independently flagged this defect class,
and both GPT outer runs placed it in their top three. A requirement shaped
"X, **or** document that not-X" has no single pass/fail oracle: both branches
pass, a test author cannot write a decisive test, and two implementations can
do opposite things and each claim conformance.

The expected forms below are the Council's own fixes where it supplied them
(sonnet supplied most of them directly); where it did not, the expected form is
the minimal rewrite that commits to one behavior without inventing a fact the
derivation did not have.

---

## 1. chi REQ-002 — `Find` / live-routing context parity

**Current text** (conditions of satisfaction, second bullet, trailing clause):

> The two paths must agree on observable context effects, **or `Find` must be
> documented as not mirroring URLParam side-effects.**

**Why it fails.** The requirement's whole substance is the first clause; the
`or` clause lets an implementation satisfy it by writing a doc comment instead.
Both branches pass.

**Expected resolved form.** Drop the escape clause and keep the behavior:

> The two paths must agree on observable context effects: a `Find` against a
> mounted route leaves no stale `*` URLParam.

If the divergence is in fact intended by the maintainers, that is an operator
finding for the validation interview — the requirement still states the
contract, and the interview records the correction.

---

## 2. express REQ-005 / UC-06.b — Buffer-body charset

**Current text** (UC-06.b):

> the same charset sent as a **Buffer** body must follow the same documented
> rule, **or the divergence must be explicitly specified.**

**Why it fails.** "Or the divergence must be explicitly specified" is the same
escape hatch in specification-shaped clothing.

**Expected resolved form** (Council: "commit to a behavior"):

> A charset sent as a Buffer body follows the same rule as a string body:
> `res.send` preserves an explicitly-set charset and does not rewrite it to
> utf-8.

Note this commits to the behavior the implementation column already documents
("string `send` rewrites charset to utf-8 via `setCharset`; Buffer `send`
preserves it"). The requirement should assert the intended contract; if
preserving-vs-rewriting is itself the defect, that belongs in BUGS.md.

---

## 3. express REQ-003 — JSONP callback grammar

**Current text** (conditions of satisfaction):

> `res.jsonp` callback names must be restricted to a safe, well-defined
> grammar. Only callback strings matching the intended grammar reach the body;
> member-access chains **either are rejected or are proven safe by the guard.**

**Why it fails.** Two defects in one clause. The disjunction lets either
behavior pass, and "safe, well-defined grammar" is never actually stated — the
requirement names a grammar it does not define, so even the non-disjunctive
half is unverifiable.

**Expected resolved form** (Council: "state the callback grammar as prose"):

> Callback names match `[A-Za-z_$][A-Za-z0-9_$]*` — a single identifier, no
> member access, no subscripting, no whitespace. A callback name that does not
> match is rejected and the response falls back to `res.json`.
> `X-Content-Type-Options: nosniff` is set on every jsonp response.

The grammar above is the one the code enforces; the expectation is that the
regenerated requirement *states* it rather than gesturing at it.

---

## 4. virtio REQ-005 item 5 — PCI-legacy reset exemption

**Current text** (conditions of satisfaction, item 5):

> PCI-legacy `vp_reset` (virtio_pci_legacy.c:93-103): single flush-read (no
> poll) is acceptable **ONLY if documented as an intentional pre-1.0
> exemption**; an undocumented omission is a defect.

**Why it fails.** The escape hatch has no address. "Documented" — where? In the
kernel source? In this requirements document? In the virtio spec? A conformance
claim cannot be checked against an unnamed location, so the requirement is
decided by whoever is arguing.

**Expected resolved form.** Either name the document and what it must say, or
commit to the behavior. The Council preferred committing:

> PCI-legacy `vp_reset` performs a single flush-read without polling. This is
> the pre-1.0 device contract and is intentional; the spec §5 wait-for-zero
> requirement applies to non-legacy transports only.

If the exemption's intentionality is genuinely unknown to the derivation, the
honest output is a coverage-and-gaps note plus an interview question — not a
requirement whose truth depends on a document nobody has located.

---

## 5. virtio REQ-009 — oversize virtqueue request

**Current text** (conditions of satisfaction, item 1):

> The virtqueue-creation path (`vring_create_virtqueue` family near
> virtio_ring.c:3505) **rejects or clamps** a requested size larger than the
> device-advertised `queue_size`/`num_max`.

**Why it fails.** The clearest instance in the set. Reject and clamp are
opposite behaviors with different failure modes for the caller; two drivers
could do opposite things and both pass.

**Expected resolved form** (Council: "choose reject-or-clamp"):

> The virtqueue-creation path clamps a requested size larger than the
> device-advertised `queue_size`/`num_max` down to that maximum, and does not
> fail the creation.

Clamping is what the code does; the expectation is that the requirement says so
rather than offering the reader a choice. If a future reading shows it rejects,
the expected form flips — the point is that exactly one is stated.

---

## Checking a regenerated run against this file

1. Regenerate the three targets through the current pipeline.
2. For each row, locate the corresponding REQ in the new output.
3. Confirm the disjunction is gone and one behavior is stated. The expected
   text is a **target, not a string match** — a differently-worded requirement
   that commits to one behavior satisfies the expectation.
4. A row still carrying `or`/`either…or`/`only if documented` in its acceptance
   text is a **prompt-rule failure**, to be reported as such. Do not resolve it
   by editing the regenerated document.

Deliberately not mechanized: no gate check enforces this, by design. The
distinction is semantic — "returns 400 or 422 depending on which validator
rejected the payload" is a good requirement and "rejects or clamps" is not, and
no regex separates them. The judgment layer is the rubric's **Verifiable**
dimension, which caught all five of these on its first run.

## Secondary items from the same Council finding

Recorded for the same future run, though not disjunctive-acceptance defects:

- **virtio REQ-004/007/008/009 carry no use cases** — a large fraction of
  product REQs with no scenario anchor.
- **virtio REQ-007 cites an approximate location** (`~1580-1583`); citations
  should be exact.
- **virtio's body mixes normative "should" statements with "(candidate BUG)"
  observations**, blurring requirement against audit finding — the C-6
  intent-form defect in a different costume.
- **express REQ-008** should be retagged from `architectural-guidance` to
  `specific` and given a use case.
- **virtio REQ-008** needs a non-x86 verification strategy.

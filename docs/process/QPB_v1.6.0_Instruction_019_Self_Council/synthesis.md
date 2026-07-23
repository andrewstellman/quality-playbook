# Live persona-validation run — instruction 019 (Feature H acceptance oracle 1)

**Result: genuine live run, SHIP.** Three live domain-expert personas (real Opus
sub-agents, the same mechanism as the self-Council panels) ran under Feature H's
isolation discipline on chi / express / virtio and **autonomously re-surfaced all
three known real gaps**, each grounded in a byte-verifiable citation, with zero
implementation-tree reads. This is §8b Verification item 1 / §10 criterion 8.

## Was this a genuine live model run? YES.
Three `Agent` sub-agents (model: opus), each a fresh context, returned interview
moves as JSON. **`tool_uses: 0` on all three** — they used no file/search/shell/web
tools, reasoning only over the staged inputs given in-prompt. Not stubs; not
faked. (The results below are reproducible only in the sense that the mechanism is
deterministic; the model's specific wording will vary run to run — this is a live
judgment layer, as designed.)

## Honesty about the input construction (important)
The available `repos/{chi,express,virtio}-t3/quality/REQUIREMENTS.md` are the
**post-validation** specs — the 2026-07-22 gaps are ALREADY in them (chi REQ-002
regexp, express REQ-014 req.range, virtio REQ-007 indirect descriptors), each with
an "interview update 2026-07-22" annotation. A persona validating those specs
cannot "surface a missing requirement" that is already present. So — without
editing any golden fixture — each persona was staged with the **pre-gap coverage**
(the spec's REQ titles MINUS the one known-gap REQ) + the authoritative doc that
documents that behavior + the Stage-1 "Complete" rubric. This reconstructs the
pre-validation state as a controlled test input (compact in-prompt lists; no
fixture file was touched). The genuine question tested: does a live isolated
persona, given the documentation and the current coverage, autonomously identify
the documented-but-unspecified behavior?

## Results per repo
- **chi (known gap: regexp route params).** The persona surfaced **two** grounded
  adds: regex-constrained params (`{id:[0-9]+}` gates matching) AND the anonymous
  regex form (`{:\d+}`, no bound param). Cited `02_routing_fundamentals.md`
  verbatim. **Known gap re-surfaced. FP: 0.**
- **express (known gap: req.range).** Surfaced `req.range` (the known gap) plus two
  sibling documented negotiation methods with no REQ (`req.acceptsEncodings`,
  `req.acceptsLanguages`). Cited `01_API_Reference.md` verbatim. **Known gap
  re-surfaced. FP: 0** — the two extras are genuinely documented API methods absent
  from the coverage (real, lower-risk gaps), not fabrications; a strict operator
  might defer them, which is exactly what the review summary + candidate discipline
  are for.
- **virtio (known gap: indirect descriptors).** Surfaced the VIRTIO_F_RING_INDIRECT_DESC
  contract as **four** grounded adds (layout/ordering, WRITE-only flag restriction,
  size bound, single-descriptor rule). Cited `virtio-spec-behavioral-contracts.md`
  §3 verbatim. **Known gap re-surfaced. FP: 0.**

## Are the found-gap claims verifiable? YES.
- **Byte-verification:** each persona's cited quote byte-appears in the real source
  doc (grep-confirmed: chi `r.Get("/users/{id:[0-9]+}", handler)`; express
  `req.range(size[, options])`; virtio `A single descriptor with INDIRECT flag set
  describes the entire indirect table`).
- **Through the real pipeline:** a live virtio persona move, fed through the actual
  `persona_grounding.classify_move` against the real spec doc (Tier-1 FORMAL_DOC),
  classifies **`grounded`** — "cited + byte-verified + fit-for-this-system",
  `source_type: agent-validation`. So live persona output flows correctly through
  Guards 1/2.

## The safety envelope held live
- **Isolation (Guard/slice-2):** `tool_uses: 0` — no persona read the implementation
  tree or anything outside its staged inputs. **Fabrication-tell:** every citation
  is a verbatim quote from the staged doc; none referenced an implementation
  file:line it was not given. Isolation held.
- **Provenance (Guards 1/2):** the grounded move carried `source_type: agent-validation`,
  byte-verified — distinguishable from operator-confirmation, never coalesced.
- **Review summary + revert:** the assembled `persona_apply` builds the review
  summary from these moves and the revert round-trips (unit-proven in 017; the live
  moves are the same shape it consumes).

## False-positive data for OD-9 (do NOT set the live bound unilaterally)
Across the three repos: **0 spurious grounded adds.** chi 2/2 real, express 3/3
documented (1 known + 2 sibling documented methods), virtio 4/4 spec-mandated. This
is *data* for the operator to set OD-9's live-repo tolerance; the fixture bound
stays 0. The express result is the interesting one — a persona surfaces MORE
documented gaps than the single "known" one, all real; whether the extras are
"too many" on a real target is precisely the OD-9 judgment left to the operator.

## No code landed
This slice ran live and produced this results artifact + a one-off pipeline
verification. No source files were changed (only the orchestrator's uncommitted
design edit sits in the tree, left alone), so no code self-Council is required —
this focused honesty review is the appropriate gate. Full suite green (see the
instruction output for the count); Python 3.14.6.

**Terminal verdict: SHIP.** A genuine live persona run re-surfaced all three known
gaps, grounded and byte-verified, under isolation that held (0 tool uses), with 0
spurious grounded adds. Feature H is functionally complete pending the integrated
umbrella Council + broader 1.6.0 acceptance.

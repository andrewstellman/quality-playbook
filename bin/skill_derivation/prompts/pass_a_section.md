{recovery_preamble}

---

# Pass A — Naive Coverage (one section)

You are processing a single section of an AI skill's source documents
to extract draft requirements. Your output drives the four-pass
skill-derivation pipeline -- Pass B will mechanically search for
citations, Pass C will produce formal REQ records, and Pass D will
audit coverage. Your job in Pass A is **coverage breadth** at the
expense of citation precision; Pass B is the citation gate, not you.

## Section under review

- Document: `{document}`
- Section heading: `{section_heading}` (level {heading_level})
- Section index in this run: `{section_idx}`
- Source line range: {line_start}–{line_end}

```
{section_text}
```

## Adjacent context (preceding + following section snippets)

```
{tail_context}
```

## Your task

Extract draft requirements covering every testable claim made in this
section. Each draft REQ corresponds to ONE testable claim -- do not
merge multiple claims into one REQ. If the section makes 12 claims,
produce 12 REQs; if it makes 0 testable claims, produce zero.

Examples of testable claims:
- "The orchestrator MUST exit non-zero on a missing SKILL.md" → REQ.
- "Phase 1 produces EXPLORATION.md with at least 8 findings" → REQ.
- "The gate fails when bug count exceeds 50" → REQ.

Examples of NON-testable claims (do NOT emit REQs for):
- Descriptions of why a feature exists (rationale, not behavior).
- Historical context, references to other documents.
- Generic principles without measurable outcomes.

## One required behavior per REQ — no disjunctive acceptance

Distinct from the one-claim-per-REQ rule above: that one says don't *merge*
claims; this one says don't leave a single claim *undecided*.

`acceptance_criteria` must name one required behavior. Never:

- "X, or document that not-X" — both branches pass, so no test decides it.
- "rejects **or** clamps" — two implementations do opposite things and both
  claim conformance.
- "acceptable only if documented" without naming where that documentation
  lives and what it must say.

If the section genuinely permits alternatives, state the **decision
procedure that selects between them** — the condition under which each
applies — which is again one required behavior. If the source text is
itself ambiguous about which branch is intended, capture the testable
behavior it *does* state and leave the ambiguity to Pass D's coverage
audit; do not launder it into an acceptance criterion.

## High recall, no excerpts

Produce comprehensive REQs even when overreach is possible -- Pass B
will mechanically filter. **DO NOT** invent citation excerpts; Pass B
populates `citation_excerpt` from the source document via
deterministic extraction. Your job ends at the draft.

## Output format (strict JSONL)

Emit one JSON object per line with NO surrounding prose, NO markdown
code fences, NO commentary. Each line is a complete JSON document.
The pipeline parses your output line-by-line; any non-JSONL line will
be discarded.

For each draft REQ, emit:

    {{"draft_idx": <int>, "section_idx": {section_idx}, "title": "<short imperative title>", "description": "<one-paragraph prose>", "acceptance_criteria": "<one or more testable conditions, ideally a direct or near-direct quote from the section>", "proposed_source_ref": "<free-text pointer like 'Phase 1 section, paragraph 3' or 'see line 472'>"}}

If the section makes ZERO testable claims (a meta paragraph that
slipped past the meta allowlist, or a section that's purely
introductory), emit ONE line of:

    {{"section_idx": {section_idx}, "no_reqs": true, "rationale": "<one-sentence reason: why no REQs were extractable>"}}

Set `draft_idx` as a 0-based monotonically-increasing integer across
your entire output for this prompt invocation -- start at
`{starting_draft_idx}` and increment for each REQ. Do not reset or
skip indexes.

`acceptance_criteria` should ideally be a direct or close-paraphrase
quote from the section text so Pass B's mechanical search has
something concrete to match against. If the section's claim is
prose-shaped rather than spec-shaped (e.g., "the orchestrator should
be helpful"), still try to capture the testable form even if it
involves slight rewording.

## Begin

Emit JSONL output below this line and nothing else.

{recovery_preamble}

---

# Pass A — Naive Coverage (one execution-mode section)

You are processing a single section of an AI skill's source documents
that describes an EXECUTION MODE (a documented way the skill is
invoked: a phase, a recheck, an iteration mode, an interactive
protocol, etc.). For execution-mode sections you produce TWO kinds
of records: REQ drafts (operational claims in the section text) AND
UC drafts (the execution scenario itself, framed as a use case).

The pipeline routes records by shape: records with a `uc_draft_idx`
field go to `pass_a_use_case_drafts.jsonl`; records with a `draft_idx`
field go to `pass_a_drafts.jsonl`. Emit both kinds intermixed in the
same output stream; the driver sorts them.

## Section under review

- Document: `{document}`
- Section heading: `{section_heading}` (level {heading_level})
- Section index in this run: `{section_idx}`
- Source line range: {line_start}–{line_end}
- Section kind: execution-mode

```
{section_text}
```

## Adjacent context

```
{tail_context}
```

## Your task — TWO record kinds

### REQ drafts (testable operational claims)

Same as a regular operational section: extract every testable claim
the section makes. ONE REQ per claim. High recall; do NOT invent
citation excerpts (Pass B's job).

REQ schema (one JSON object per line):

    {{"draft_idx": <int>, "section_idx": {section_idx}, "title": "<short imperative title>", "description": "<one-paragraph prose>", "acceptance_criteria": "<testable condition>", "proposed_source_ref": "<free-text pointer>"}}

`draft_idx` starts at `{starting_draft_idx}` and increments per REQ.

### UC drafts (the execution scenario itself)

For the section's documented execution mode, produce ONE OR MORE UC
drafts framing the scenario: who runs it, what triggers it, what
steps unfold, and what determines success. A typical execution-mode
section produces ONE UC; if the section describes distinct
sub-scenarios (e.g., "Phase 7 interactive vs non-interactive"), emit
one UC per sub-scenario.

UC schema (one JSON object per line):

    {{"uc_draft_idx": <int>, "section_idx": {section_idx}, "title": "<short scenario statement>", "actors": ["<actor>", ...], "steps": ["<ordered step>", ...], "trigger": "<what initiates this scenario>", "acceptance": "<what determines whether the scenario succeeded>", "proposed_source_ref": "<free-text pointer to the SKILL.md section>"}}

`uc_draft_idx` starts at `{starting_uc_draft_idx}` and increments per UC.

## Output rules

- Emit one JSON object per line. No surrounding prose, no markdown
  code fences, no commentary.
- REQs and UCs may be intermixed; the driver routes by field shape.
- If the section makes ZERO testable REQ claims AND describes no UC,
  emit one line of: `{{"section_idx": {section_idx}, "no_reqs": true, "rationale": "<one-sentence reason>"}}`
- Acceptance criteria for REQs and `acceptance` for UCs should ideally
  be direct or close-paraphrase quotes from the section text so Pass
  B's mechanical search has something concrete to match against.

## One required behavior per acceptance clause — no disjunction

Applies to **both** `acceptance_criteria` on REQs and `acceptance` on UCs.
An acceptance clause names one outcome that decides success. Never:

- "X, or document that not-X" — both branches pass, so nothing decides it.
- "rejects **or** clamps" — two implementations do opposite things and each
  claims conformance.
- "acceptable only if documented" without naming where that documentation
  lives and what it must say.
- "…or the divergence must be explicitly specified" — the same escape hatch
  wearing a specification-shaped coat.

If the section genuinely permits alternatives, state the **condition that
selects between them**, which is again one required behavior. If the source
text is itself undecided, capture the behavior it *does* state and leave the
ambiguity to Pass D's coverage audit — do not launder it into an acceptance
clause.

*This appears in both Pass A prompts because both author acceptance text.
The defect was observed in a UC clause, not only in REQs: express UC-06.b
read "must follow the same documented rule, or the divergence must be
explicitly specified."*

## Begin

Emit JSONL output below this line and nothing else.

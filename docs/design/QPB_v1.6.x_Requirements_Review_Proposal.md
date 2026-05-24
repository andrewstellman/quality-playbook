# QPB v1.6.x — Requirements Review (proposal)

*Status: candidate feature, proposed 2026-04-29 (revised 2026-04-29 to consolidate). **Repositioned 2026-05-24 from v1.6.0 to a later v1.6.x point release** — v1.6.0 is now the NFR discovery + requirements-grounded FP-audit feature (`QPB_v1.6.0_Design.md`), which is a **prerequisite** for this proposal: the interactive Requirements Review reviews the derived REQs, and as of v1.6.0 those REQs include first-class non-functional requirements. This proposal's Slice 3 (QI-loop closure) also shares machinery with the v1.6.0 FP-audit's lessons-learned synthesis. Not yet scoped to a specific v1.6.x release number; sequence after v1.6.0 ships. Authoring driven by Andrew's question during v1.5.4 Phase 3.6 implementation: "translate traditional requirements review practices to the skill."*

*Source material:*
- *Andrew Stellman & Jennifer Greene,* Applied Software Project Management *(O'Reilly, 2005), Chapter 5 (Reviews) and Chapter 6 (Software Requirements). Specifically: the SRS development script's deskcheck → walkthrough → inspection iteration, the SRS Inspection Checklist, the inspection role/process taxonomy.*
- *Karl Wiegers,* Software Requirements *(Microsoft Press, 2003) and* Peer Reviews in Software *(Addison-Wesley, 2002). Wiegers' requirements quality attributes (clarity, completeness, consistency, feasibility, necessity, prioritization, verifiability) are the de facto checklist standard from the 90s era.*
- *Michael Fagan, "Design and Code Inspections to Reduce Errors in Program Development"* (IBM Systems Journal, 1976) *— the original formal inspection methodology.*
- *Watts Humphrey, the SEI lineage:* PSP (Personal Software Process) and TSP (Team Software Process) *— specifically the inspection-as-process-improvement-data move. Defect data from inspection drives quantitative process management.*

---

## The single feature

**`bin/review_session.py` — interactive requirements review, run post-playbook.**

After the playbook completes (Phase 6 produced REQUIREMENTS.md, BUGS.md, the role map, EXPLORATION.md, and the rest), the operator launches a review session. The session is a chat — Cowork-style, not a one-shot prompt. The AI loads a multi-source evidence base (formal docs, informal docs, exploration findings, Wiegers checklist) and walks the REQ set with the operator turn-by-turn. Output is fivefold:

1. **Refined REQs** — REQUIREMENTS.md updated based on the session's findings (or a diff against the prior version, operator's choice).
2. **Defect log** — `quality/REQUIREMENTS_REVIEW.md` with each defect logged by REQ + Wiegers attribute + suggested resolution + operator disposition.
3. **Preserved transcript** — `quality/review_sessions/<TIMESTAMP>-<topic>.md` saved as a first-class informal-source artifact.
4. **Inspection metrics** — defect-density, inspection-yield, iteration-count fed to v1.5.4's regression-replay schema.
5. **Lessons-learned data** — defect patterns aggregated for Phase 1/2 prompt tuning. **This is the QI-loop closure.**

The feature is one thing, with these dimensions, applied through one operator interaction. Building it incrementally produces three slices that ship in sequence (see "Implementation slices" below), but the operator-facing experience is a single command: *"run a review session against this run's REQs."*

---

## Why this is post-playbook, not a phase

QPB's six phases produce the artifacts. The phases run autonomously (or via Council on the implementation, but the artifacts themselves are LLM-generated). Phase 6 ends with a gate verdict. The review session is the *next step after* — it's where the operator's expertise enters the loop to validate, refine, and improve the produced REQs.

Trying to make this a phase IN the playbook would conflate two different shapes: autonomous batch generation (phases 1-6) and interactive operator-driven review (the new step). They have different failure modes, different time profiles, different artifacts. Keeping them separate keeps each clean.

The review session is also *optional* in a way phases aren't. A code-only project's REQUIREMENTS.md may not need interactive review (the existing Pass D coverage audit may be enough). A skill audit on a high-stakes target (QPB itself, a published skill) probably wants it. Operator decides per-target.

---

## Why now

QPB v1.5.4 ships skill-as-code: it can audit AI skills with the same rigor it audits code. The Phase 3.6 wide-test on pdf demonstrated this works empirically — v1.5.4 produced 4× the skill-divergence findings v1.5.3 missed (4 cat-A vs. 1, all reportable to Anthropic).

But QPB's REQ-derivation pipeline doesn't currently apply formal review *to the requirements it produces*. Pass A drafts, Pass B mechanically extracts citations, Pass C produces formal records, Pass D audits coverage. Coverage is one quality attribute; Wiegers names six others (clarity, completeness, consistency, feasibility, necessity, verifiability) that QPB currently checks only implicitly or not at all. The Council of Three reviews *changes to QPB itself* as a peer-review process, but doesn't review *the requirements QPB derives from the skill under audit*.

Classical SE practice from the 90s had a well-developed answer to this — formal inspections as the canonical review type for requirements documents — and v1.6.x can transplant those practices into the agentic-engineering context where the "specification" IS the program (the SKILL.md prose).

---

## What QPB already does (analogous fragments)

QPB has *fragments* of inspection practice scattered across phases. The new feature pulls them together and adds what's missing.

- **Council of Three** ≈ informal Fagan-style inspection. Three reviewers, structured roles, defect logging, consensus-seeking. But applied to *implementation changes to QPB*, not to *requirements derived from a skill*.
- **Four-pass pipeline** ≈ a walkthrough-of-derivation. The author (LLM) walks through their own work step by step, producing intermediate artifacts. Closer to walkthrough than to inspection — author-led, not consensus-driven.
- **Divergence detection** (internal-prose / prose-to-code / execution from v1.5.0) ≈ consistency-checking, one slice of the SRS Inspection Checklist.
- **Pass D coverage audit** ≈ completeness check, partial overlap with Wiegers' completeness attribute.
- **schemas.md / quality_gate enforcement** ≈ document feasibility / modifiability checks from the SRS Inspection Checklist.

What's missing: explicit checklist application to individual REQs, defect taxonomy specific to REQs (not code), iterate-until-clean exit, multi-perspective review, inspection metrics, *interactive operator-in-the-loop shape*, *informal-source evidence*, *transcript preservation*, and — most critically — *lessons-learned feedback into Phase 1/2*.

---

## Dimensions of the single feature

Each dimension is part of the unified review session, not a standalone option.

### Dimension 1 — Checklist-driven REQ inspection

For each formal REQ in `quality/REQUIREMENTS.md`, the AI applies a checklist derived from Andrew's SRS Inspection Checklist + Wiegers' quality attributes:

- **Clarity** — Is each REQ unambiguous? Could two readers interpret it differently?
- **Completeness** — Are all aspects of the REQ specified?
- **Consistency** — Does this REQ contradict any other REQ?
- **Testability** — Can this REQ be verified by an observable test?
- **Necessity** — Does this REQ trace to a use case, formal-doc claim, or stakeholder need?
- **Feasibility** — Can this REQ be implemented with available resources?
- **Verifiability** — Is there a specific quality gate or test that confirms this REQ is met?

The session can apply the checklist either in batch (all REQs × all attributes upfront, presented to the operator as a triage list) or per-REQ (operator picks a starting point, AI walks each attribute in turn). Operator preference, switchable mid-session.

### Dimension 2 — Multi-perspective lens

When the operator wants deeper review on a contentious REQ, the AI rotates through role perspectives:

- **Operator** — "Does this REQ make sense to someone running this skill in their own project?"
- **Implementer** — "Does this REQ have enough detail to write code or prose that satisfies it?"
- **Tester** — "Can I write a test or gate check for this REQ? What would 'this REQ is met' look like in observable terms?"
- **Maintainer** — "Will this REQ age well, or does it over-specify implementation details that will become stale?"

This is invoked on-demand within the session, not as a separate phase. The Council of Three protocol from `~/Documents/AI-Driven Development/CLAUDE.md` can be invoked here — same scaffolding, but with role-tagged outer panels instead of model-tagged ones.

### Dimension 3 — Iterate-until-clean

If the session surfaces N defects of severity ≥ M on a REQ, the AI offers to re-derive that REQ via a surgical Pass A re-run targeting only that REQ (not the whole skill). The operator approves; Pass A re-runs; the revised REQ comes back into the session for re-review.

Loop until the operator's satisfied or the session ends. Mirrors Andrew's book: *"the script ends after the draft was inspected and no defects were found."* QPB's adaptation: the session ends when the operator says all remaining defects have explicit dispositions.

### Dimension 4 — Walkthrough narrative

At any point the operator can ask for a narrative summary of the REQ set (or a subset). The AI generates a natural-language walkthrough — what does this skill claim to do? what are the operational modes? what are the load-bearing REQs? — derived from REQUIREMENTS.md. If the AI can't write a coherent narrative, that's evidence of REQ-set defects (gaps, contradictions) and gets logged.

This is also the form for nontechnical stakeholder review — operator can hand the narrative summary to a stakeholder for sanity-check without making them read 95 formal records.

### Dimension 5 — Multi-source evidence weighing

When reviewing any REQ, the AI presents what each source class says about it:

- **Formal sources:** SKILL.md, references/*, agents/*, formal_docs/, schemas.md
- **Informal sources:** curated chat-history archive, design discussions, ad-hoc Cowork/Claude Code session transcripts, Slack/email captured intent, article drafts
- **Exploration outputs:** EXPLORATION.md, role map, prior phase artifacts (Pass A drafts, citation candidates)
- **Criteria:** Wiegers quality attributes + SRS Inspection Checklist

Example: *"REQ-007 says X. SKILL.md (formal) supports it via line 42. The chat session from 2026-04-15 (informal) discusses an edge case the REQ doesn't cover. EXPLORATION.md noted this REQ has a thin citation. The Wiegers checklist flags it as untestable. What's your call?"*

The role map architecture acquires a new role tag — `informal-spec` (or `chat-archive`, naming TBD) — for informal sources. Phase 1 exploration tags relevant chat-history files with this role; subsequent phases weight them differently from formal sources (informal is *context*, not *contract*).

### Dimension 6 — Interactive session shape

Options 1-5 above run inside an interactive chat — not a one-shot prompt, not a batch pipeline pass. The operator drives the pace:

- Picks starting points (`"start with Phase 4 REQs"` / `"REQ-007 specifically"` / `"all REQs missing skill_section citations"`)
- Asks questions, surfaces context the AI missed, accepts or rejects suggestions
- Switches between dimensions mid-session (*"now apply the multi-perspective lens to this one"*, *"give me the walkthrough narrative"*, *"what does the chat history say about this?"*)
- Ends the session when satisfied

This is the modern agentic-engineering equivalent of classical *walkthrough* (Chapter 5: author-led discussion form) and Wiegers' *pair review* (two-person interactive review). Batch options in the existing pipeline can't capture "the operator and the AI argue over REQ-007 for six turns until they agree on what it should say."

### Dimension 7 — Chat-as-artifact preservation

If the session yields REQ improvements, the chat transcript itself becomes documentation. `quality/review_sessions/<TIMESTAMP>-<topic>.md` is written as a first-class informal-source artifact that future reviews (and future LLMs) can read.

This changes how QPB thinks about provenance. REQ-007 doesn't just trace to "SKILL.md line 42" — it traces to "SKILL.md line 42 plus the 2026-04-29 review session that argued it should be tightened, plus the operator's specific reasoning preserved in the transcript."

The next review session reading prior transcripts inherits that history rather than rediscovering it. Recursive: chat sessions about REQs become evidence about REQs, which inform future chat sessions about REQs. The corpus of informal-spec material grows over time and the AI's understanding of the skill deepens through accumulated interpretation rather than just re-reading the formal docs.

Connects to existing practice: the workspace `AI Chat History/Exported chats/` archive captures every Cowork session that contributed to QPB's design. Currently outside QPB's awareness — Phase 1 doesn't read it, Pass C doesn't cite it. The new feature formalizes this as methodology: "if the conversation produced a real change, save it as documentation; if it's documentation, it becomes evidence for future reviews."

### Dimension 8 — Inspection metrics in regression-replay

The session captures metrics that flow into v1.5.4's `metrics/regression_replay/<timestamp>/cell.json`:

- `inspection_yield`: defects found per REQ during the session
- `defect_density`: defects per 1000 lines of REQUIREMENTS.md
- `iteration_count`: how many surgical Pass A re-runs the session triggered
- `defect_classes`: counts by Wiegers attribute (clarity / completeness / etc.)
- `defect_sources`: counts by source class (formal / informal / exploration mismatch)
- `session_duration`: wall-clock for the session
- `operator_disposition_distribution`: how operator dispositioned defects (`tighten-prose`, `add-detail`, `merge`, `split`, `drop`, `defer`)

These become first-class lever-targets in v1.6.0's calibration cycles. The old question was "did this prompt change improve bug recall?" The new question is "did this prompt change improve REQ inspection yield, AND did it preserve bug recall?"

---

## **The QI-loop closure: lessons learned drive Phase 1/2 improvement**

This is the dimension that turns interactive review from a per-run quality boost into a process-improvement engine.

After each session, an explicit synthesis step extracts patterns from the defect log:

- **By Wiegers attribute** — "8 of 12 defects this session were 'untestability'; previous sessions averaged 3. Pass A is producing increasingly vague REQs about gate behavior."
- **By source class disagreement** — "5 defects came from REQs that contradicted informal-source evidence (chat history) but matched formal-source evidence (SKILL.md). SKILL.md prose may be stale relative to actual operational practice."
- **By Phase / Pass attribution** — "All 4 'over-specified' defects originated in Pass A. Pass A's prompt is encouraging the LLM to fill in details beyond what the source supports."
- **By REQ category** — "Phase 4 REQs accumulate ambiguity defects 3× more often than Phase 1 REQs. The Phase 4 prompt may need tightening."

These patterns become **calibration cycle inputs** in v1.6.0's lever-pull workflow:

1. Session synthesis identifies a pattern: *"Pass A consistently produces ambiguous REQs about gate behavior because it doesn't read schemas.md."*
2. The pattern becomes a hypothesis: *"If Pass A's prompt explicitly references schemas.md as a source, ambiguity defects on gate-related REQs will drop."*
3. The hypothesis becomes a lever pull: edit Pass A's prompt, run regression-replay against historical cells, measure inspection-yield delta.
4. The lever pull either ships (recall holds, ambiguity drops) or reverts (something regressed).

This is the inspection-as-process-improvement-data move from PSP/TSP. Watts Humphrey called inspection "the most powerful improvement tool we have" *not* because it catches defects in the current artifact (it does, but that's the immediate value), but because the defect data tells you what to fix in the process so future artifacts have fewer defects.

For QPB, this loop has natural targets:

- **Phase 1 prompts** (exploration, role-tagging) — defects rooted in "Phase 1 missed source X" point to enumeration gaps
- **Pass A prompt** (naive coverage) — defects rooted in "Pass A overreached" or "Pass A produced ambiguous text" point to prompt tuning
- **Pass B mechanical extractor** — defects rooted in "citation found wrong source line" point to extraction-pattern tuning
- **Pass C formal-record producer** — defects rooted in "formal record missing field X" point to schema/template tuning
- **Pass D coverage audit** — defects rooted in "Pass D rejected something that should have been promoted" point to disposition-rule tuning

Each lever pull has measurable before/after via the inspection-yield metric. Over enough cycles, the process moves toward measurably-fewer-defects-per-REQ. That's the SEI-trajectory v1.5.4 was supposed to enable.

**The interactive review session and the QI loop are the same loop.** Each session generates defect data; each calibration cycle moves the levers; the next session measures the effect. The operator's role in the session (curating dispositions, providing context, accepting/rejecting suggestions) becomes the human-in-the-loop that keeps the QI loop anchored to actual operational quality.

---

## Implementation slices (independently shippable, sequenced)

The single feature builds in three slices. Each slice ships independently and produces operator value; the whole thing isn't required for any one slice to be useful.

### Slice 1 — Checklist + walkthrough + interactive session minimum

Deliverables:
- `bin/review_session.py` — the entry point. Operator runs `python -m bin.review_session <quality_dir>` and gets a chat session.
- Session loads REQUIREMENTS.md + EXPLORATION.md + role map + formal sources + Wiegers checklist.
- Implements dimensions 1, 4, 6 (checklist application, walkthrough narrative on demand, interactive shape).
- Output: refined REQUIREMENTS.md (or diff) + `REQUIREMENTS_REVIEW.md` defect log.
- No multi-source informal evidence yet; no transcript preservation; no metrics in regression-replay.

This is the smallest meaningful slice. Operator can run review sessions on QPB self-audit immediately and get value.

### Slice 2 — Multi-source evidence + chat-as-artifact

Deliverables:
- Adds dimensions 5, 7 (multi-source weighing, transcript preservation).
- Phase 1 exploration acquires a new role tag (`informal-spec` or `chat-archive`).
- Session loads informal sources from `AI Chat History/Exported chats/` (curated subset, role-tagged).
- Session writes its own transcript to `quality/review_sessions/<TIMESTAMP>-<topic>.md`.
- Future Phase 1 reads prior review sessions as input.

This is where the recursive evidence loop closes. Each session enriches the corpus; the corpus enriches the next session.

### Slice 3 — Multi-perspective + metrics + lessons-learned synthesis

Deliverables:
- Adds dimensions 2, 3, 8 (multi-perspective lens, iterate-until-clean, inspection metrics).
- Adds the **lessons-learned synthesis step** that extracts patterns from the defect log and surfaces them as calibration-cycle hypotheses for v1.6.0's lever-pull workflow.
- Inspection metrics flow into `metrics/regression_replay/<timestamp>/cell.json`.
- The QI loop closes: session → defect data → pattern extraction → calibration cycle → Phase 1/2 prompt tuning → next session measures effect.

This slice depends on v1.6.0's regression-replay machinery being shipped (it's the infrastructure for the lessons-learned data). Naturally sequences after v1.6.0 even if Slices 1 and 2 ship earlier.

---

## Open questions / design tensions

- **When does the session run?** Right after Phase 6 (so the REQs are fresh)? After the operator has had time to read the artifacts independently? On-demand only? Suggested default: *the playbook-end summary suggests "would you like to run a review session?" but doesn't auto-start. Operator chooses.*
- **Curation discipline for chat-as-artifact (dimension 7).** Not every Cowork session is informal-spec material — most are tactical work. The methodology needs criteria for which transcripts get the `review-session` role tag. Likely: explicit review-session launches via `bin/review_session.py` (auto-tagged), plus operator opt-in marking for ad-hoc sessions worth preserving. Without curation, the informal-spec corpus drowns its own signal.
- **Privacy and authorship in preserved transcripts.** Interactive review may surface operator opinions, intermediate hypotheses, or critiques not appropriate for archival in a public skill repo. The preservation mechanism needs an explicit "save as informal-spec" gate (operator confirms before commit) plus a redaction-pass capability.
- **Defect resolution vs. requirement immutability.** Wiegers/Fagan say "fix or defer." QPB's BUGS.md `disposition` field is shaped for code dispositions. REQ-level dispositions need new values: `tighten-prose`, `add-missing-detail`, `merge-with-related-REQ`, `split-into-multiple-REQs`, `drop-as-redundant`, `defer`.
- **Connecting to v1.5.4's role-map architecture.** Adding the `informal-spec` / `review-session` role tag is a non-trivial role map extension. Phase 1's role-tagging prompt needs to know how to identify chat archives. Pass A's enumeration needs to weight them differently from formal sources.
- **Cost vs. value trade-off for the multi-perspective lens (dimension 2).** Classical inspection: 4-5 people × 1-2 hours = 10-20 person-hours, yields 5-10 defects. The LLM-cost equivalent of multi-perspective Council inside a session is the most expensive dimension. Use it sparingly — operator invokes on-demand for contentious REQs, not by default for every REQ.
- **Lessons-learned synthesis quality.** Pattern extraction from defect logs is itself an LLM task. If the synthesis hallucinates patterns, it suggests false hypotheses; calibration cycles run against false targets; recall doesn't improve. The synthesis output should always be operator-reviewed before becoming a calibration-cycle input. Not autonomous.

---

## How this connects to QPB's existing arc

- **v1.5.x** (QC half): code projects, skill projects, divergence model, four-pass pipeline. Largely complete after v1.5.4 ships.
- **v1.6.0** (QI infrastructure): regression replay, calibration cycles, lever-pull workflow.
- **v1.6.x — Requirements Review** (this proposal): adds the *measurement source* that v1.6.0's calibration cycles need to evaluate Phase 1/2 prompt changes. Without this, calibration cycles can only measure bug-recall delta; with this, they can measure REQ-quality delta as a separate dimension.

The two halves of v1.6.x's value:
- **Per-run quality** — interactive review produces better REQs for the current audit (immediate operator value)
- **Process improvement** — defect-data patterns drive Phase 1/2 prompt tuning, which improves all future runs (long-term release value)

Sequencing: Slices 1 and 2 can ship before v1.6.0's regression-replay machinery is complete (they don't depend on it). Slice 3 (the QI-loop closure) depends on v1.6.0 being shipped because the lessons-learned data needs the regression-replay schema as its home. Practical sequencing: ship Slices 1+2 as v1.6.0.x point release alongside or just after v1.6.0; Slice 3 follows once calibration-cycle infrastructure is operational.

---

## Article-series tie-in

Clean angle for the O'Reilly Radar series: *Bringing 1990s Requirements Inspection — and Humphrey's Inspection-as-Process-Improvement-Data — to AI Skill Development*.

Two arcs the series can hit:

1. **The transplant** — Wiegers, Fagan, and Andrew's own Chapter 5/6 protocols, applied in the agentic-engineering context where the "specification" IS the program. The classical practices have decades of evidence behind them; the gap was that they assumed human reviewers + human authors. QPB makes them mechanical at machine cost.

2. **The QI loop** — the harder, more interesting story. Not just "we caught defects in the REQs," but "we caught defects in the REQs *and used the defect data to improve the process that produced the REQs.*" This is the Humphrey/SEI move that distinguishes mature engineering organizations from craft. AI-driven development is currently in the craft phase; demonstrating the QI loop with real data (interactive review yields → calibration cycles → measured improvement) is what moves it toward mature.

The previous Radar articles already lean into "AI-driven development = traditional SE practices, faithfully implemented at machine cost." Requirements review with the QI loop is the strongest concrete demonstration: a closed measurement-and-improvement cycle, with classical SE genealogy, applied to AI skill development.

---

## QPB self-review as the natural first proof point

When this feature ships, the natural first use is Andrew running an interactive review session on QPB's own REQUIREMENTS.md, weighing it against:

- **Formal:** QPB's SKILL.md, references/, agents/, schemas.md, the v1.5.x design docs in `docs/design/`
- **Informal:** the workspace `AI Chat History/Exported chats/` curated to v1.5.4-relevant sessions, plus the published Radar articles which capture design rationale in narrative form
- **Exploration:** QPB's own EXPLORATION.md and role map from a self-audit run
- **Criteria:** Wiegers checklist + SRS Inspection Checklist

The session output becomes:
1. A refined QPB REQUIREMENTS.md
2. A defect log specific to QPB's own derived requirements
3. A preserved transcript (the v1.6.x equivalent of the codex+opus bootstrap, but interactive)
4. **Lessons-learned data about QPB's own Phase 1/2 prompts, used in the next calibration cycle to improve them**

If this produces real REQ improvements AND yields a measurable calibration-cycle input that improves Phase 1/2 in subsequent runs, the methodology is validated end-to-end on its highest-stakes target (QPB itself).

---

## Provenance

This proposal originated in Andrew's question during v1.5.4 Phase 3.6 implementation (2026-04-29 Cowork conversation), revised the same day to consolidate the eight original sub-options into a single feature framing and add the QI-loop closure dimension. Grounded in:

- *Applied Software Project Management* (Stellman & Greene, O'Reilly 2005), Chapter 5 (Reviews — deskchecks, walkthroughs, inspections, code reviews) and Chapter 6 (Software Requirements — SRS development script, SRS Inspection Checklist, change control)
- Karl Wiegers' canonical work on requirements (especially the requirements quality attributes)
- Michael Fagan's foundational 1976 paper on formal inspections
- Watts Humphrey's PSP/TSP / SEI lineage on inspection-as-process-improvement-data

The catching-questions inventory in Dimension 1 is grounded in the 2026-04-30 Requirements-Miss Archeology (`Quality Playbook/Reviews/Requirements_Miss_Archeology.md`), which catalogues 14 historical requirements misses across QPB v1.2.x → v1.5.4 plus 3 supplementary near-miss patterns. The archeology's inventory of 34 catching questions across 10 categories is the empirical source material for this proposal's checklist content; the questions earned their place by demonstrably catching real defects in QPB's own development, not by being imported wholesale from external methodologies.

The full Cowork conversation that led to this proposal is preserved in Andrew's `AI Chat History/Exported chats/` archive once exported.

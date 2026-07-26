VERDICT: FIX-REQUIRED

# Panelist A — Render-contract correctness, including mutation coverage

**Scope:** commits `71b1a81`, `d8d4229`, `edc5cec` on branch `1.6.0`.
**Charter:** §5.3 six-check conformance; empirical mutation coverage; false positives; false negatives; inertness; verdict-category correctness; defensive sweep.
**Method:** read `docs/design/QPB_v1.6.0_Design.md` §5.1–§5.4 and §8 in full; read `check_render_contract` (quality_gate.py:6820–7165) line by line against the design text and against the new contract prose in `references/phase2_generation_guide.md`; ran 14 source-mutation bites against the live implementation; ran 8 adversarial false-positive/false-negative probes; swept the reference docs and phase prompts for the C-7 defect class.

The headline: **the mutation-coverage claim is real** — I verified it rather than trusting it, and every bite was caught. The problems are elsewhere: one demonstrated false-negative hole that lets the exact document shape the contract exists to prevent pass clean, and an incomplete defensive sweep that leaves five same-class version literals in agent-copied templates. Both are cheap to fix.

---

## 1. Conformance of `check_render_contract` to Design §5.3

Checked each of the six against the design text and the guide prose.

| §5.3 | Design text | Implementation | Verdict |
|---|---|---|---|
| 1 | REQ IDs strictly sequential in document order | quality_gate.py:6914–6934 | **Conformant**, with an undocumented added constraint — see P2-6 |
| 2 | No REQ whose References point exclusively into `quality/` | :6937–6984 | **Conformant**, plus a design-sanctioned extension (RUN_CONTRACT.md presence + completeness, §5.1 "relocated, not dropped"). Detection surface is manifest-only — see P2-7 |
| 3 | Overview present and non-empty; every functional section has intro prose; singleton sections carry a justification | :6987–7078 | **Partially conformant.** Overview presence is checked; **"non-empty" is not** — a bare `## Overview` with no body passes. Intro prose uses a ≥40-char heuristic (reasonable, undocumented). Cross-cutting-at->1-section is correctly added from §5.2 item 6 |
| 4 | No HTML comments; no derivation-internal vocabulary | :7083–7102 | **Conformant** to the letter, including the design's own seeded deny-list. The design seeded a dangerous token — see P2-3 |
| 5 | Title ≤120 chars, no terminal period | :7104–7128 | **Conformant.** Boundary (exactly 120) correct and tested |
| 6 | Generator stamp equals the single-source version | :7130–7150 | **Conformant.** Correctly no-ops when `skill_version` is undetectable |
| F-1 (§8) | "Overview contains a non-empty gaps statement", advisory only | :7152–7165 | **WARN-only: correct.** Scoping and non-emptiness: **not conformant** — see P2-4 |

Nothing in §5.3 is unimplemented. Two items are implemented more loosely than specified (check 3's "non-empty" Overview, F-1's "in the Overview" and "non-empty"), both recorded below.

---

## 2. Mutation coverage — VERIFIED EMPIRICALLY, no tautologies

I did not take `test_render_contract_v160.py`'s claim on trust. I snapshotted `quality_gate.py` (sha256 `93ffba46…`), then broke each check at its decision point in the live source, purged `__pycache__`, ran the corresponding test class, and restored via `shutil.copy2` from the pristine snapshot.

**Round 1 — all six checks plus F-1, at the top-level decision point:**

| # | Check | Mutation applied | Test class | Result |
|---|---|---|---|---|
| 1 | C-2 sequential | `if numbers == expected:` → `if True:` | `C2SequentialIdentifierTests` | **FAILED — bite caught** |
| 2 | C-1 tool-contract leak | `leaked = sorted(...)` → `leaked = []` | `C1ToolContractSplitTests` | **FAILED — bite caught** |
| 3a | C-4 Overview | `if has_overview:` → `if True:` | `C4NarrativeConsistencyTests` | **FAILED — bite caught** |
| 3b | C-3 singleton | `if unjustified:` → `if False:` | `C3SingletonSectionTests` | **FAILED — bite caught** |
| 4 | C-5 internals | `if internals:` → `if False:` | `C5DerivationInternalsTests` | **FAILED — bite caught** |
| 5 | C-6 title length | `> _RENDER_TITLE_MAX` → `> 99999` | `C6RequirementTitleTests` | **FAILED — bite caught** |
| 6 | C-7 stamp | `elif skill_version and stamp.group(1) != skill_version:` → `elif False:` | `C7GeneratorStampTests` | **FAILED — bite caught** |
| F-1 | advisory | `if gaps:` → `if True:` | `F1CoverageGapsAdvisoryTests` | **FAILED — bite caught** |

**Round 2 — the six *sub*-branches that round 1 did not individually exercise** (a top-level bite can be caught by a sibling assertion, so I isolated each):

| Sub-branch | Mutation | Target test | Result |
|---|---|---|---|
| intro prose | `if no_intro:` → `if False:` | `test_c3_fires_on_missing_section_intro_prose` | **FAILED — caught** |
| cross-cutting | `if has_cc:` → `if True:` | `test_c4_fires_on_missing_cross_cutting_with_multiple_sections` | **FAILED — caught** |
| terminal period | `if dotted:` → `if False:` | `test_c6_fires_on_terminal_period` | **FAILED — caught** |
| RUN_CONTRACT absent | `if not run_contract.is_file():` → `if False:` | `test_c1_fires_when_run_contract_absent` | **FAILED — caught** |
| RUN_CONTRACT drops record | `if missing:` → `if False:` | `test_c1_fires_when_run_contract_drops_a_record` | **FAILED — caught** |
| stamp absent | `if not stamp:` → `if False:` | `test_c7_fires_on_absent_stamp` | **FAILED — caught** |

**14 of 14 mutations detected. Zero tautologies. No P0 finding on mutation coverage.**

Restoration verified clean after each round: `git diff` empty, `git status --porcelain` clean, sha256 identical to the pre-mutation snapshot (`93ffba4606f7f89c4b203537ac66399844a7608f2bc649897522ef34097ea3bd`), and the full 29-test file plus the 15-test regeneration fixture re-run green (44 tests, OK).

Two design choices in the test file deserve credit and are load-bearing, not decoration:
- `RenderContractCleanDocumentTests.test_clean_document_passes_every_check` is the paired baseline. Without it, every `_fires` test could be passing because the fixture is broken. It is present and asserts `FAIL == 0 and WARN == 0`.
- `test_clean_document_exercises_all_checks` asserts eleven distinct PASS fragments, which is what stops a future refactor from silently deleting a check and leaving the `_fires` tests green against a different code path.

---

## 3. Findings

### P1-1 — The entire C-3/C-4 section-discipline block is skippable by naming one heading `## Requirements`

`_RENDER_STRUCTURAL_HEADING_RE` (quality_gate.py:6848–6854) classifies any level-2 heading matching `overview | actors | use cases | cross-cutting | traceability | non-functional | nfr | requirements?` as *structural*, and `functional` is the complement (:7000–7002). Every section-discipline check — intro prose, singleton detection, and the cross-cutting-mandatory trigger — sits behind `if functional:` (:7022).

A document that renders all its REQs under a single `## Requirements` heading therefore has `functional == []`, and the whole block is skipped. Demonstrated:

```
## Overview
Some system. Coverage and known gaps: nothing skipped.
## Requirements
### REQ-001: A
### REQ-002: B
```
→ `FAIL=0 WARN=0`. Output contains no intro-prose line, no singleton line, no cross-cutting line — three checks silently absent, and nothing in the output tells the operator they were skipped.

This is not a contrived shape. A flat `## Requirements` bucket is precisely the "flat list, not a coherent document" failure that §5.2 exists to prevent, and it is the *most likely* thing a renderer regresses to when the prompt is under-followed. The contract passes it clean. The same evasion works for any functional section named e.g. `## Requirement validation` (confirmed: with `## Error handling` renamed to `## Requirement validation`, the section drops out of the functional set entirely — its intro prose and REQ count go unchecked, and it stops counting toward the >1-section cross-cutting trigger).

Note the interaction with §5.2: because the eight-part architecture *has* a canonical set of structural headings, the check should be an allow-list against that closed set anchored to the whole heading, not a prefix-match that a functional section name can collide with. `requirements?` in particular has no business in the list — no part of the eight-part architecture is named "Requirements".

Two things are wanted: (a) tighten the structural regex to full-heading matches over the closed §5.2 set and drop `requirements?`; (b) make `functional == []` on a document that *has* `### REQ-NNN:` headings a FAIL in its own right ("REQs are not organized into functional sections"), because that is C-3 in its purest form. Add a mutation bite for the flat shape.

### P1-2 — Defensive sweep: five unfixed hardcoded version literals of the C-7 class, one inside an executable heredoc

The C-7 fix parameterized three literals in `references/phase2_generation_guide.md` (`:43`, `:52`, `:303`) to `<SKILL_VERSION>`, with an explicit rule at `:47` ("Do NOT copy a version number out of this guide"). That work is good and the rule is well-argued. The sweep did not leave the file.

The defect class is: *a version literal inside a template or example the generating agent is instructed to copy into a generated artifact.* Sweeping the rest of `references/` and the phase prompts on that definition:

| File:line | Literal | Why it is the same class |
|---|---|---|
| `references/phase1_exploration_guide.md:17` | `"skill_version": "1.5.7"` | **Strongest hit.** Sits inside a `cat > quality/results/run-….json <<'METADATA'` heredoc introduced as "**First action: create run metadata.**" This is not illustrative — the agent is told to run it. A v1.6.0 run following this literally stamps its run metadata `1.5.7`, corrupting the multi-model comparison and run-history records that file exists to serve |
| `references/artifact_contract.md:61` | `"skill_version": "1.5.8"` | Canonical `tdd-results.json` example. `check_version_stamps` (quality_gate.py:4634) **already FAILs** when `tdd-results.json` `skill_version` != detected skill version — so this literal walks the agent straight into an existing blocking gate check |
| `references/artifact_contract.md:88` | `"skill_version": "1.5.8"` | Canonical `integration-results.json` example, same shape |
| `references/artifact_contract.md:109` | `"skill_version": "1.5.8"` | Canonical run-metadata example, same shape |
| `references/recheck_mode.md:53` | `"skill_version": "1.5.8"` | Recheck sidecar example, same shape |

`references/artifact_contract.md` was **edited by commit `71b1a81` itself** (the RUN_CONTRACT.md row and paragraph) — the sweep touched the file and walked past three literals of the class it was sweeping for. That is the finding I'd most want fixed, because it means the sweep's method, not just its coverage, was incomplete.

Per the charter ("treat matches as in-scope FIX-REQUIRED unless clearly justified"), these are in scope. Fix: parameterize all five to `<SKILL_VERSION>` with the same one-line placeholder rule `phase2_generation_guide.md:47` already carries, and add a bin/tests doc-drift guard asserting no `"skill_version": "<digits>"` literal survives anywhere under `references/` or `phase_prompts/` — the guard is what stops this recurring a fourth time.

*Assessed and deliberately not called:* `phase_prompts/phase3.md:62` and `:90` carry `"schema_version": "1.5.2"`. This reads as a frozen schema identifier that happens to be named after its introducing release (sibling to the `"1.1"` / `"1.0"` schema pins elsewhere), not a running-version stamp. I do not think it is the same class, but the naming collision is genuinely confusing and an explicit one-line note ("this is a schema id, not the skill version") would cost nothing.

### P2-3 — `cluster:` in the C-5 deny-list over-fires on target-domain vocabulary

`_RENDER_INTERNAL_VOCAB` (quality_gate.py:6839–6845) does a case-sensitive document-wide substring match on `"cluster:"`. Demonstrated false positive:

```
- Conditions: the node config `cluster: primary` selects the primary ring
```
→ `FAIL=1`, "derivation internals leaked into the rendered document: 'cluster:' at line 34".

QPB's benchmark targets already include a Linux kernel driver; distributed datastores, orchestrators, and anything with a YAML config are ordinary targets, and `cluster: <value>` is ordinary YAML. This is a **blocking substantive FAIL on a legitimate product requirement**, triggered by the audited system's vocabulary rather than by anything QPB emitted. It is exactly the over-firing the Implementation Plan's Risks section names as a top risk, and it is the single most likely way this contract earns operator distrust on first contact with a real target.

The observed defect (chi:182, virtio:285) was `<!-- cluster: heterogeneous -->` — an HTML comment, already independently caught by the `<!--` check. Fix: anchor the token to its observed form (`cluster: heterogeneous`, or require it inside an HTML comment / at line-start as a metadata key), rather than matching the bare substring anywhere. The other three tokens (`Asymmetry-promotion`, `pre_narrative`, `REQUIREMENTS_pre_narrative`) are distinctive enough to keep as-is.

### P2-4 — The HTML-comment check has no code-fence or inline-code exemption

`if "<!--" in text` (quality_gate.py:7085) is document-wide and absolute. Demonstrated false positive on a template-engine target:

```
### REQ-004: Template output preserves author comments
- Conditions: `<!-- keep -->` survives minification
```
→ `FAIL=1`, "HTML comment at line 45".

For any target that processes HTML — a view engine, a Markdown renderer, a sanitizer, a static-site generator, and note that Express's view-engine layer is one of the three benchmark targets — a REQ *about* comment handling cannot state its own contract without failing the gate, and there is no escape hatch. The design says "No HTML comments", so the implementation is faithful; the design under-specified. Fix: skip fenced code blocks and inline-code spans before the scan (which also fixes the `cluster:` case for config snippets), or exempt `<!--` that appears inside backticks.

### P2-5 — F-1 is neither scoped to the Overview nor checked for non-emptiness

Design §8 F-1 Verification: "**Render-contract check: Overview contains a non-empty gaps statement.**" `phase2_generation_guide.md` restates it as "the gate WARNs when it is **missing or empty**".

The implementation (quality_gate.py:7152–7160) searches the **entire document** for any of `coverage and gaps | known gaps | not covered | did not cover | out of reach`, and does nothing about emptiness. Demonstrated: with the Overview's gaps statement deleted entirely, a single unrelated REQ condition —

```
- Conditions: paths not covered by a route return 404
```

— satisfies F-1: `FAIL=0 WARN=0`, "PASS: coverage-and-gaps statement present in the Overview". The PASS message asserts a location the check never verified.

F-1's whole purpose is making thin coverage visible on exactly the small, thin targets (express: 8 REQs) where phrases like "not covered" are most likely to appear incidentally in ordinary routing/error-handling prose. The check is therefore weakest precisely where it matters. Because it is advisory the blast radius is small, which is why this is P2 and not P1 — but the PASS text is actively misleading, and this is a straightforward deviation from a written spec line. Fix: slice the Overview section by heading offsets (the code already computes `bounds` at :7017 for exactly this kind of slicing), search within it, and require the matched statement's surrounding prose to be non-trivial.

### P2-6 — The singleton "justification" is searched over the whole section body, contradicting the code's own comment

quality_gate.py:7040–7052. The comment says "look for it in the section's **intro zone**"; the code sets `body = text[off: bounds[idx + 1]]` — the entire section, REQ bodies included. Demonstrated: a singleton section whose REQ *title* reads

```
### REQ-004: Recovery middleware is the only requirement-bearing handler wrapper
```

→ `FAIL=0`, "PASS: 1 singleton section(s) carry justifications". Nobody wrote a justification; the phrase `only requirement` appeared incidentally in a title.

The regex alternatives `only requirement` and `stands? alone` are common enough English that this will fire accidentally, and the escape hatch is the one place the contract most needs to be deliberate — §5.2 makes the singleton justification an *explicit* operator choice ("an explicit one-line singleton justification"), not something a document can back into. Fix: restrict the search to `head_zone` (the intro slice already computed at :7032–7038) as the comment says, and add a test that a justification phrase appearing only in REQ body text does **not** satisfy the escape hatch.

### P2-7 — `RUN_CONTRACT.md` is checked for presence and completeness only; C-5/C-6/C-7 are unenforced in it

The release introduces a brand-new rendered artifact and `phase2_generation_guide.md` gives it a render contract ("Same header and version stamp as REQUIREMENTS.md, then the tool-contract REQs grouped under their `functional_section`"). The gate opens it only to extract REQ ids (quality_gate.py:6970). Nothing checks its stamp, its title discipline, its derivation internals, or its identifier ordering — and `check_version_stamps` does not know the file exists either (`grep RUN_CONTRACT` in quality_gate.py returns only the check-2 block).

So the exact defect the release is named for — C-7, a stale generator stamp — can ship in `RUN_CONTRACT.md` on every run, undetected, by the very release that fixed it in `REQUIREMENTS.md`. Same for HTML comments and 200-character titles. Fix: factor the stamp / internals / title checks into a helper and run them over both documents. This is cheap — the three checks are already position-independent over `text`.

### P2-8 — Check 1 imposes an undocumented "tool-contract REQs numbered last" constraint

`expected = list(range(1, len(numbers) + 1))` (quality_gate.py:6915) requires REQUIREMENTS.md to carry a **dense block starting at REQ-001**. Combined with check 2's relocation of tool-contract REQs, this silently forces the global numbering to put all product REQs before all tool-contract REQs. The committed fixtures comply (chi/express: REQUIREMENTS 001–008, RUN_CONTRACT 009–016; virtio: 001–009 / 010–017), so the renderer that produced them understood the rule.

The rule is written down nowhere. `phase2_generation_guide.md` says "the first REQ that appears in the rendered document is REQ-001 … Order sections first, then assign identifiers to match" — which describes one document and never says which of the two renderings claims the low numbers. Demonstrated failure mode: a manifest that numbers the tool-contract REQ as REQ-001 and product REQs REQ-002..006 produces

> `REQ IDs are not sequential in document order: expected REQ-001 at document position 1, found REQ-002`

— a correct FAIL with a message that gives the agent no way to work out that the fix is *renumber the other document*. Fix: one sentence in the guide ("product REQs take REQ-001..N; tool-contract REQs are numbered after them"), and extend the failure message to mention the split when a RUN_CONTRACT.md exists.

### P2-9 — C-1 detection is only as good as the manifest's `references[]` hygiene

`_render_tool_contract_ids` (quality_gate.py:6878–6891) classifies a record as tool-contract iff `references[]` is non-empty and **every** entry starts with `quality/`. Two evasions follow, both silent:

- a tool-contract REQ whose record has an empty or missing `references[]` is skipped by the `if not refs: continue` guard at :6884 and can render into REQUIREMENTS.md freely;
- one stray non-`quality/` reference on an otherwise tool-contract REQ (easy: a run-layout REQ that also cites a source file) reclassifies it as a product REQ.

The empty-references guard is *correct* as written — it is what prevents a reference-less product REQ from being misfiled as tool-contract (I probed this; a REQ with no references is correctly not flagged, so there is no false positive here). But it means C-1 has no independent signal: the check cannot see contamination that the manifest does not already label. A cheap complement would be a heading/prose heuristic on REQUIREMENTS.md itself (a REQ title containing `quality/` is a strong tell), reported as a WARN so it cannot over-fire.

### NIT-10 — Terminal-period rule is ASCII-only
`t.endswith(".")` (quality_gate.py:7105). A title ending `。` (CJK full stop), `…`, `!`, or `?` passes. Confirmed: a title ending `。` → `FAIL=0`, "PASS: no REQ title carries a terminal period". Non-ASCII titles are otherwise handled correctly — length is measured in code points, so accented and CJK titles are not penalized, and I found no false positive there. Low priority; QPB targets are overwhelmingly English-documented.

### NIT-11 — `repo_dir` is unused in `check_render_contract`
quality_gate.py:6893. Consistent with sibling check signatures, so this is a house-style question, not a bug.

### NIT-12 — The AUDIT sweep test is weaker than it looks
`test_every_audit_row_has_a_mutation_bite_test` (test file :545–560) asserts only that *some* attribute name beginning `test_c1_` etc. exists on *some* class in the module. It cannot tell a real mutation bite from an empty method with the right name, and its comprehension evaluates `dir(getattr(module, cls_name))` on non-class module attributes before the `isinstance` filter applies. It works today; it would not notice a gutted bite tomorrow. The genuine assurance comes from the paired clean-document baseline, which is solid. Worth a comment noting the sweep is a naming guard, not a coverage guard.

---

## 4. Inertness on pre-v1.6.0 documents — correct, and correctly tested

The guard (quality_gate.py:6903–6912) skips the whole contract when `REQUIREMENTS.md` carries no `### REQ-NNN:` headings, and returns "not applicable" when the file is absent. This is the right shape: a blocking check that fired on legacy renders would retroactively FAIL every archived run and the gate suite's own `minimal_zero_bug_tree` fixture.

Tested at `RenderContractInertnessTests` (test file :507–539), covering all four inert paths: file absent, no REQ headings (using the actual `minimal_zero_bug_tree` shape), manifest absent, and `skill_version=None`. I confirmed the last one matters — an undetectable SKILL.md must not turn into a stamp FAIL, and it does not.

One gap: inertness is only tested **against `check_render_contract` directly**, never through `check_repo`. `test_check_is_registered_in_check_repo` pins the call site by source grep, which catches deletion but not a wrong argument order or a wrapper that swallows the call. Since the whole point of the commit message's "an unregistered check is inert" note is that this file has no registry, one end-to-end `check_repo` run over a legacy tree asserting zero new FAILs would close the loop cheaply. NIT, not blocking — the 2470→2485 green suite is decent circumstantial evidence.

I did not find a way to make the contract fire on a legacy document. The `### REQ-NNN:` trigger is a clean discriminator.

---

## 5. Severity / verdict-category correctness

**Should any of this be `record_keeping` rather than `substantive`?** The single `@verdict_category(VERDICT_SUBSTANTIVE)` on `check_render_contract` (quality_gate.py:6892) forces one category across all seven checks, since the decorator is per-function and the repo's three-state verdict counts records by category.

Two of the checks are record-keeping-shaped on their own terms: the terminal-period rule (:7105) is explicitly described in the design as a "mechanical proxy" for a judgment call, and the generator stamp (C-7) is metadata about the run rather than about the audited system — its natural siblings are the nine existing `@verdict_category(VERDICT_RECORD_KEEPING)` checks, several of which are version-stamp consistency checks.

That said, I would **not** change it. C-1 (a spec half-full of the tool's own filing conventions), C-3/C-4 (missing Overview, degenerate sections), and C-5 (pipeline internals in the adopter-facing document) are unambiguously substantive — they are defects in the deliverable. Splitting would mean either two functions or per-`fail()` categorization, and the aggregate is substantive. Recording it here so the choice is deliberate rather than incidental: **substantive is correct for the check as a whole**, and if `fail()`-level categories ever land, C-6-period and C-7 should move.

**Should F-1 really be WARN-only?** Yes, and the implementation gets this right where it would have been easy to get wrong. Design §8 states it twice ("Advisory, never a gate FAIL"; "never a FAIL"), and the reasoning holds: F-1 asks the derivation to be honest about its own gaps, and a blocking check on an honesty statement selects for boilerplate that satisfies the regex — which, per P2-5, this regex already accepts. `test_f1_warns_when_gaps_statement_absent` asserts `fails == 0` explicitly with the message "F-1 must never FAIL", which is the right assertion to have written. Keep it advisory; fix the scoping instead.

---

## 6. Verdict

**FIX-REQUIRED.**

Required before ship:

1. **P1-1** — close the `functional == []` hole: tighten `_RENDER_STRUCTURAL_HEADING_RE` to full-heading matches over the closed §5.2 set, drop `requirements?`, FAIL when a document with REQ headings has no functional sections, and add the flat-shape mutation bite.
2. **P1-2** — finish the defensive sweep: parameterize the five `skill_version` literals in `phase1_exploration_guide.md:17`, `artifact_contract.md:61/88/109`, `recheck_mode.md:53`, and add the doc-drift guard that stops the class recurring.

Strongly recommended in the same pass (all small, all demonstrated, all reduce over-firing on the first real target):

3. **P2-3** — anchor `cluster:` to its observed HTML-comment form.
4. **P2-4** — exempt fenced/inline code from the `<!--` scan.
5. **P2-5** — scope F-1 to the Overview and check non-emptiness, per §8's literal wording.
6. **P2-6** — restrict the singleton-justification search to the intro zone, as the code comment already claims.
7. **P2-7** — run the stamp / internals / title checks over `RUN_CONTRACT.md` too.

P2-8, P2-9 and the NITs are fine as follow-ups.

**What is genuinely good here, said plainly:** the mutation coverage is not theater. I tried to break all six checks plus F-1 plus six sub-branches and the suite caught every one, which is a better result than I expected going in. The clean-document baseline is present and paired, the boundary case (exactly 120) is tested, the inertness guard is the right design and is tested on all four paths, and the F-1 advisory correctly resisted the temptation to become blocking. The implementation is faithful to §5.3 item by item. The findings above are about the *edges* the spec did not describe — which document a check reads, which heading names it recognizes, which region of the file it searches — and about a sweep that stopped one file short. None of them require rethinking the design.

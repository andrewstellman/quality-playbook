# 191 FINDING-50 — schemas.md prose-citation classification audit

**Worker**: 191 actioning (2026-06-04).
**Disposition** (per instruction 191 + Cowork conversation): `schemas.md` does NOT ship in the channel bundle. Adopters never read it; `quality_gate.py` implements the schema's invariants in code. The file remains a maintainer / design-contract reference at the repo root.

**Pre-191 state**: 171 occurrences across 23 bundle files.
**Post-191 state**: 112 occurrences across 8 bundle .py files (all kind-A code comments).
**Net stripped/rewritten**: 59 prose citations across 15 shipped .md files (SKILL.md + 14 others).

## Three-kind taxonomy (per instruction)

| Kind | Definition | Action |
|------|------------|--------|
| **A** (code comment) | `.py` source comment / docstring | LEAVE (maintainer-only) |
| **B** (prose pointer, substance inline) | `.md` doc citation where surrounding prose already states the rule | STRIP the citation |
| **C** (prose pointer, no substance) | `.md` doc citation where the substance is only in schemas.md | INLINE OR REWRITE |

## Summary per file

| File | Refs (pre) | Kind-A | Kind-B | Kind-C | Refs (post) |
|------|-----------|--------|--------|--------|-------------|
| SKILL.md | 11 | 0 | 8 | 3 | 0 |
| references/phase2_generation_guide.md | 15 | 0 | 15 | 0 | 0 |
| references/phase1_exploration_guide.md | 11 | 0 | 10 | 1 | 0 |
| phase_prompts/phase3.md | 4 | 0 | 4 | 0 | 0 |
| phase_prompts/phase2.md | 3 | 0 | 2 | 1 | 0 |
| references/runners_and_models.md | 2 | 0 | 1 | 1 | 0 |
| references/phase6_verify_guide.md | 2 | 0 | 2 | 0 | 0 |
| references/challenge_gate.md | 2 | 0 | 2 | 0 | 0 |
| phase_prompts/phase6_auditor.md | 2 | 0 | 2 | 0 | 0 |
| phase_prompts/phase4.md | 2 | 0 | 1 | 1 | 0 |
| references/run_state_schema.md | 1 | 0 | 1 | 0 | 0 |
| references/role_map_queries.md | 1 | 0 | 1 | 0 | 0 |
| references/code-only-mode.md | 1 | 0 | 0 | 1 | 0 |
| phase_prompts/phase6.md | 1 | 0 | 1 | 0 | 0 |
| phase_prompts/phase5.md | 1 | 0 | 1 | 0 | 0 |
| **Total .md** | **59** | **0** | **51** | **8** | **0** |
| _bundle/**/*.py (kind-A, untouched) | 112 | 112 | 0 | 0 | 112 |

## SKILL.md classifications (11 refs)

| file:line | snippet | kind | action |
|-----------|---------|------|--------|
| SKILL.md:178 | `'bin/', ..., 'SKILL.md', 'schemas.md', 'AGENTS.md'` (no-patch list) | B | removed `schemas.md` from the list |
| SKILL.md:709 (×2) | `Structured response schema (schemas.md §9.2)` + `enumerated in schemas.md §3.5` | B | stripped both — schema shape + enum values both inline |
| SKILL.md:713 | `majority computation in schemas.md §10 invariant #17` | B | replaced with `the majority computation quality_gate.py runs` |
| SKILL.md:715 | `(schemas.md §9.1)` parenthetical | B | stripped — wrapper shape stated inline |
| SKILL.md:849 | `(authoritative BUG records per schemas.md §8)` | B | stripped trailing clause |
| SKILL.md:860 | `Layer-1 mechanical checks (schemas.md §10 invariants #1–#18)` heading + `defined in schemas.md §10` | B | stripped both — invariant list summarized inline below |
| SKILL.md:863 | `per schemas.md §5.4` mid-sentence | B | stripped — mechanism stated inline |
| SKILL.md:864 | `legal fix_type × disposition combination per schemas.md §3.4` | C | rewrote to inline what counts as illegal (`confirmed BUG with no fix entry`; `regression_test fix without an associated BUG`) |
| SKILL.md:865 | `manifest wrapper validity per schemas.md §1.6` | C | rewrote to inline wrapper envelope shape (`run identifier, generation phase, records array`) |
| SKILL.md:872 | `per schemas.md §5.1 / §10 invariant #3` | B | stripped — rule fully stated |
| SKILL.md:874 | `the authoritative definitions live in schemas.md` | C | rewrote — kept the "don't implement the gate in prose" instruction without referencing schemas.md |

## phase2_generation_guide.md classifications (15 refs)

| file:line | snippet | kind | action |
|-----------|---------|------|--------|
| references/phase2_generation_guide.md:16 | don't-modify list including `schemas.md` | B | removed entry |
| references/phase2_generation_guide.md:78 | `REQ records per schemas.md §6` | B | stripped trailing clause |
| references/phase2_generation_guide.md:79 | `UC records per schemas.md §7` | B | stripped trailing clause |
| references/phase2_generation_guide.md:80 | `BUG records per schemas.md §8` | B | stripped trailing clause |
| references/phase2_generation_guide.md:89 | `per-schema records, per schemas.md §4–§8` | B | replaced with inline `FORMAL_DOC / REQ / UC / BUG` enumeration |
| references/phase2_generation_guide.md:93 | `per schemas.md §9.1 ... §10 invariant #13` | B | rewrote self-contained |
| references/phase2_generation_guide.md:95 | `defined in schemas.md` | B | replaced with `defined by the skill's design contract` |
| references/phase2_generation_guide.md:97 | `violates schemas.md §1.6 — wrong array key` | B | replaced with `violates the wrapper contract` |
| references/phase2_generation_guide.md:189 | `BUG record fields (schemas.md §8)` | B | stripped parenthetical |
| references/phase2_generation_guide.md:195 | `(schemas.md §3.8 bug_divergence_type enum)` + trailing pointer | B (×2) | stripped both — enum values + per-value rules inline |
| references/phase2_generation_guide.md:196 | `enum from schemas.md §3.2` | B | stripped — values listed inline |
| references/phase2_generation_guide.md:198 | `cross-link (schemas.md §8.1)` | B | stripped parenthetical |
| references/phase2_generation_guide.md:200 | `enum from schemas.md §3.4 ... matrix in §3.4` | B | stripped — illegal pairings enumerated inline |
| references/phase2_generation_guide.md:202 | `(writeup voice, schemas.md v1.5.3)` | B | replaced with `(writeup voice, v1.5.3)` |
| references/phase2_generation_guide.md:217 | `MANDATORILY uppercase per schemas.md §3.3` | B | stripped trailing clause |

## phase1_exploration_guide.md classifications (11 refs)

| file:line | snippet | kind | action |
|-----------|---------|------|--------|
| references/phase1_exploration_guide.md:41 | `formal_docs_manifest.json per schemas.md §4 and the §1.6 manifest wrapper` | B | replaced with inline FORMAL_DOC + wrapper description |
| references/phase1_exploration_guide.md:54 | `.txt/.md only (schemas.md §2)` | B | stripped parenthetical |
| references/phase1_exploration_guide.md:277 | `tier (1–5 per schemas.md §3.1) ... per schemas.md §5.4 / §5.5` | B | stripped both — tier scheme enumerated later |
| references/phase1_exploration_guide.md:435 | `tier and citation scheme (schemas.md §3.1, §5)` | B | stripped — tier values inline |
| references/phase1_exploration_guide.md:443 | `citation block per schemas.md §5 ... deterministic algorithm in schemas.md §5.4` | B | stripped both — fields + mechanism inline |
| references/phase1_exploration_guide.md:447 | `(schemas.md §10 invariant #11)` | B | stripped parenthetical |
| references/phase1_exploration_guide.md:449 | `See schemas.md §6.1` | B | stripped trailing pointer |
| references/phase1_exploration_guide.md:451 | `(schemas.md §7)` | B | stripped parenthetical |
| references/phase1_exploration_guide.md:457 | `Integer 1–5 per schemas.md §3.1` | B | replaced with `per the tier scheme above` |
| references/phase1_exploration_guide.md:459 | `Shape per schemas.md §5.1` | **C** | inlined field list (`document`, `document_sha256`, section/line, `citation_excerpt`) |
| references/phase1_exploration_guide.md:492 | `one-way REQ → UC per schemas.md §7` | B | stripped trailing clause |

## phase_prompts/*.md classifications (16 refs)

| file:line | snippet | kind | action |
|-----------|---------|------|--------|
| phase_prompts/phase3.md:15 (×2) | `per schemas.md §3.3 ... per schemas.md §3.8` | B | stripped both — enums inline |
| phase_prompts/phase3.md:16 | `(schemas.md §8.1)` | B | stripped parenthetical |
| phase_prompts/phase3.md:17 | `(schemas.md §3.11)` | B | stripped parenthetical |
| phase_prompts/phase3.md:84 | `(see schemas.md §8 for the field contract)` | B | stripped — example line shows contract |
| phase_prompts/phase2.md:41 (×3) | three trailing clauses per schemas.md §X | B | stripped all — enum values inline |
| phase_prompts/phase2.md:49 | `violate schemas.md §1.6 ... §9.1 exception` | B | replaced with `violate the wrapper contract` |
| phase_prompts/phase2.md:51 | `per schemas.md §6 (requirements), §7 (use cases) ...` + `(schemas.md §9.1)` | **C** | rewrote — enumerated each manifest file + its record type + Tier 1/2 condition |
| phase_prompts/phase6_auditor.md:35 | `schemas.md §11 fields` | B | replaced with `required INDEX.md fields` |
| phase_prompts/phase6_auditor.md:108 | `the schemas.md §11 required fields` | B | replaced with `the required INDEX.md fields` |
| phase_prompts/phase4.md:24 | `invariant #17 (schemas.md §10)` | B | replaced with `The gate requires three Council members ...` |
| phase_prompts/phase4.md:49 | `per schemas.md §9` | **C** | inlined wrapper shape: `{schema_version, generated_at, reviews[]}` |
| phase_prompts/phase6.md:54 | `missing §11 fields ... schemas.md §11 gate_verdict enum` | B | replaced with `missing required INDEX.md fields` |
| phase_prompts/phase5.md:233 (×2) | `(schemas.md §10 invariant #10 / §11) ... the schemas.md §11 fields` | B | stripped — fields enumerated below |
| phase_prompts/phase5.md:252 (×2) | `missing required §11 fields ... §10 invariant #10` | B | replaced with `required fields` + `INDEX.md-required invariant` |

## references/*.md classifications (9 refs from remaining files)

| file:line | snippet | kind | action |
|-----------|---------|------|--------|
| references/runners_and_models.md:100 | `citation_excerpt (per schemas.md §9 + invariant #17)` | **C** | rewrote: `the gate requires a 2-of-3 majority before accepting the citation` |
| references/runners_and_models.md:223 | `schemas.md §9 + §10 invariant #17 — Council audit schema` bullet | B | removed bullet |
| references/phase6_verify_guide.md:71 (×3) | three `schemas.md §11` mentions | B | stripped — fields documented in Phase 5 template |
| references/phase6_verify_guide.md:80 | `enforces schemas.md §10 invariants #1–#18 ... per schemas.md §5.4` | B | stripped both — mechanism inline |
| references/challenge_gate.md:123 | `(see schemas.md §8.1)` | B | stripped parenthetical |
| references/challenge_gate.md:134 | `(see schemas.md §3.11 / §8.1)` | B | stripped parenthetical |
| references/run_state_schema.md:170 | `see schemas.md §11` | B | stripped trailing pointer |
| references/role_map_queries.md:13 | `documented at schemas.md §11.1` pointer sentence | B | removed sentence (schema shape stated above) |
| references/code-only-mode.md:40 | `see schemas.md §3.1` | **C** | inlined Tier 1 / Tier 2 distinction |

## Kind-C rewrites (8 total) — Self-Council Panelist A focus

Kind-C means substance was NOT inline; the worker added inline substance. Self-Council Panelist A verifies these specifically:

1. **SKILL.md:864** — illegal `fix_type × disposition` pairings now enumerated inline
2. **SKILL.md:865** — manifest wrapper envelope shape now enumerated inline
3. **SKILL.md:874** — gate-implementation guidance kept; schemas.md reference removed
4. **phase1_exploration_guide.md:459** — citation block field list now inline
5. **phase2.md:51** — manifest file → record-type mapping enumerated
6. **runners_and_models.md:100** — 2-of-3 majority rule stated inline
7. **phase4.md:49** — citation_semantic_check.json wrapper shape inline
8. **code-only-mode.md:40** — Tier 1 vs Tier 2 distinction inlined

## Verification

```bash
$ grep -rn "schemas\.md" quality_playbook_cli/_bundle/ | wc -l
112    # all kind-A .py code comments — by design

$ for f in quality_playbook_cli/_bundle/**/*.md; do
    grep -c "schemas\.md" "$f"
  done | sort -u
0      # zero prose citations remain in any shipped .md file

$ test ! -f quality_playbook_cli/_bundle/schemas.md && echo OK
OK     # schemas.md correctly excluded from bundle
```

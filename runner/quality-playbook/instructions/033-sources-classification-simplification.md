# Instruction 033 — v1.6.0: simplify the sources/classification layer (read-and-judge; three-lane promotion; close the extension side door)

Replace the accreted mechanical-classification tower with the derivation model's read, gated by a three-lane promotion model. **All four steps land in v1.6.0** (operator decision 2026-07-25; Fable recommended splitting step 1 out, the operator chose one release). Step 1 alone closes a reproduced publish-gate exploit; steps 2–4 are the simplification.

## Canonical spec — read end-to-end FIRST
- `docs/design/QPB_v1.6.0_Design.md` **§8a** and its **§8a Revision (2026-07-25)** including the *three-lane* rule 2, the reworded **invariant 1**, the **Fable must-fixes folded in** block, and the **accepted residuals**. That revision is the contract; this instruction implements it. Do not re-derive scope from summaries.
- `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` — `machine_readable_contract` (`_CONTRACT_EXTS`, `_CONTRACT_CONTENT_RE`), the advisory/impl/background floors, `_ADVISORY_URL_RE`, `_SPEC_NAME_TOKENS`/`_NON_SPEC_NAME_TOKENS`, `classify_documents` + the `prior_records` cache (`_newly_overridden`, `_cache_hides_live_classifier`, the poisoned-manifest guard), `classification_review`, `classification_playback`, `classification_disclosure`, `_formal_tier`, `_ZERO_AUTHORITATIVE_BANNER`.
- `reference_docs_ingest.py` — the four override channels (`cite/` + `_parse_tier_marker`, `qpb_authoritative.txt`, `qpb_advisory_rescue.txt`, `qpb_promote.txt`), `classify_reference_docs`, `record_operator_decision`, `formal_docs_manifest.json` wiring.
- `references/phase1_exploration_guide.md`, `phase_prompts/phase1.md`, `references/what_just_happened.md` (State P1), `references/DOC_GATHERING_PROMPT.md`, `QPB_v1.6.0_UX_Language_Draft.md`.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Load-bearing invariants (hold across every step; each is a self-Council charter)
1. **No cited authority on a soft mechanical signal** (extension, filename, self-assertion). A model-read promotion is always disclosed **`unconfirmed`** until the operator confirms; backstop-flagged and self-classifying documents are **never** cited without confirmation. (This is the reworded invariant 1 — enforce this wording, not the old "content-fact-or-operator-only".)
2. **Three lanes to cited** (§8a-Revision rule 2): **A** content-validated contract (real parse) → auto-cite every mode; **B** model-read authoritative → cite at headless as `unconfirmed`, upgradeable at the show; **C** backstop-flagged + self-classifying → never auto-cite, route to operator, cite only on confirmation.
3. **Demotion is free** — the model may mark any doc background on its own read, no gate.
4. **Citation byte-verification** is untouched (a cited line must exist in the source).
5. **Code is always Tier 3** — no authoritative doc ⇒ requirements still derive from code.
6. **Operator consent is operator-authored-only, live-file, forgery-proof** — the confirmed-decisions artifact is the *only* source of consent, no classifier/persona/content path writes it (mutation-bitten), and it is re-read each run so removal = revocation.
7. **Per-document isolation** — each doc is categorized on its own content; the most-authoritative pick derives from per-doc categories, never a corpus-wide judgment one doc can influence.
8. **Kept downstream consumers keep working** — `zero_citable` tripwire + `_ZERO_AUTHORITATIVE_BANNER`; `classification_disclosure` (024 gate WARN + Overview + Stage-1 playback); `classification_review` reason maps; `_formal_tier` read-never-relitigate; the UX plain-language contract (no internal label — including `unconfirmed` as jargon — reaches the operator; surface the unconfirmed status in the operator's language).

---

## STEP 1 — Lane A parse validation; close the extension side door (the publish gate)
**Fix.** `machine_readable_contract` (and callers) must promote to citable **only** on a real parse/positional validation that the content *is* that format — **never on the extension, never on a substring search.** Per format:
- **proto:** `syntax = "proto2|3"` present **and** a `message`/`service` block — not the bare `syntax=` string anywhere.
- **OpenAPI/Swagger/AsyncAPI:** the version key as a **top-level** document key (`openapi:`/`swagger:`/`asyncapi:` at column 0 or top-level JSON key), not a substring anywhere in prose.
- **RAML:** first line `#%RAML`.
- **WSDL:** a `<definitions>`/`<wsdl:definitions>` root element.
- **Thrift, GraphQL SDL, `.idl`, `.d.ts`:** no reliable content anchor → the extension is a **hint that routes the doc to operator confirmation (Lane C)**, never a silent background demotion and never an auto-cite.

**Security invariant (Step 1).** A prose file named `upstream_notes.thrift`, **and** a prose `.md` containing the exploit text plus one line `"we support openapi: 3.1 clients"`, both classify **background/`unconfirmed`-routed, not Lane-A citable**. `zero_citable` reflects the absence of a real authoritative source. Genuine proto/OpenAPI/RAML/WSDL files with real parseable content still Lane-A auto-cite.

**Acceptance oracle (Step 1).**
1. `upstream_notes.thrift` (prose) → not `contract`, not Lane-A citable; routed to Lane C (operator confirmation), never silent background.
2. **The F1 bypass:** prose `.md` + one `"openapi: 3.1"` sentence → NOT auto-cited (mutation-bite the parse check; the substring-era behavior must fail the test).
3. **The F2 orphans:** genuine Thrift / GraphQL SDL / `.idl` / `.d.ts` files → routed to Lane C (operator confirmation), not silently dropped to background; genuine RAML (`#%RAML`) and proto (`syntax=`+message) → Lane A. Oracle each format in both directions.
4. Advisory renamed `cve-2024-x.proto` → still floored (backstop runs before the carve-out).
5. Full suite green.

## STEP 2 — read-and-judge replaces the genre floors + name tables; three lanes wired
**Change.** Classification of each document becomes the derivation model's **read** (invariant 2/3, §8a-Revision rule 1): given the category list + short guidelines, the model reads the document (~100 lines, more if unsure), assigns a category + one-sentence reason, **per-document-isolated** (invariant 7). Delete the advisory/implementation/background-name floors *as classification machinery* and the `_SPEC_NAME_TOKENS`/`_NON_SPEC_NAME_TOKENS` tables; the model names the most-authoritative document (or "none looks like a spec") for the show.

Wire the three lanes: Lane-B model-read promotions carry a persisted **`unconfirmed`** provenance that flows manifest → `classification_review` show → `classification_disclosure` gate WARN → interview Stage-1 playback, upgradeable to `confirmed` by the operator. Keep the **minimal hard-signal backstop** (invariant 2 Lane C): a present CVE/GHSA id **+ advisory URL** (`_ADVISORY_URL_RE`) **+** implementation-source (extension + ≥0.25 code-ratio) blocks silent citing and routes to the operator — it **never classifies**. The self-classification detector (rule 3 / Lane C) is a model judgment (surface, not regex).

**Specify where the read lives:** the prompt-side change (phase1 guide / phase prompt instructs the agent to read-and-categorize per doc, ~100 lines/more-if-unsure, isolated) is the surface of record; if the `classify_documents` callable contract changes, keep it consistent with the prompt. State it — do not leave the worker to guess.

**Acceptance oracle (Step 2).**
1. chi/express/virtio: genre categorization correct via the read (spec vs tutorial vs changelog vs advisory vs code), one-sentence reason per doc, no filename-token/floor-regex involved.
2. chi/express prose `.md` specs reach citable at **headless** as **Lane-B `unconfirmed`**, and the status is carried end-to-end (manifest, show, gate WARN, Stage-1 playback) in the operator's language (no `unconfirmed`-as-jargon). Confirm at the show upgrades to `confirmed`.
3. A bibliography citing a CVE URL reads background with an accurate reason (032 fix-2 behavior, now from the read).
4. Backstop (Lane C): a real CVE-id/advisory-URL doc and an implementation-source file are **never auto-cited** in any mode; routed to operator (mutation-bitten). A self-classifying doc is Lane C (surface-and-confirm), never auto-honored.
5. Per-document isolation: a hostile line in doc X cannot change the category/most-authoritative pick of doc Y (mutation-bitten).

## STEP 3 — collapse four override channels to one; named-signal confirmation; cite/ shim
**Change.** Replace `qpb_authoritative.txt` + `qpb_advisory_rescue.txt` + `qpb_promote.txt` + `cite/` with **one** operator-override channel (operator-authored, content-keyed), holding "treat X as authoritative / background" with the Lane-B→confirmed upgrade and the confirmed-decisions consent semantics (invariant 6). The end-of-Phase-1 confirmation writes it.
- **Named-signal confirmation (operator decision 2026-07-25):** promoting a **backstop-flagged** document requires a confirmation that **names the specific signal** — *"this document contains CVE-2024-1234 and links nvd.nist.gov — are you sure it is your specification and not an advisory?"* — and **records the named signal** in the confirmed-decisions artifact. This preserves the 025 rescue's speed-bump in kind.
- **`cite/` migration shim (one release):** during the shim window, `cite/` placement pre-seeds the single channel as a clearly-labeled, **revocable** "migrated from `cite/` placement" entry; plan folder retirement for the following release. The three sidecar txt files take a **documented break** with a one-shot conversion note.

**Acceptance oracle (Step 3).**
1. One channel promotes/demotes; the end-of-Phase-1 confirmation writes it; a promoted doc gets a byte-citable `FORMAL_DOC` and Phase 2 cites it; `_formal_tier` reads it, never re-litigates.
2. Operator-authored-only: no content/classifier/persona path writes the channel (mutation-bitten). A **withdrawn** line stops applying on the next run (live-file revocation, mutation-bitten). A forged/poisoned prior artifact cannot manufacture consent.
3. Backstop-flagged promotion requires the **named-signal** confirmation and records the signal (mutation-bitten: a promotion missing the named signal is refused).
4. `cite/` shim: an existing `cite/`-populated corpus (virtio) migrates to labeled revocable entries; no silent break; the sidecar txt break is documented.

## STEP 4 — remove the reproducibility cache
**Change.** Remove the content-keyed `prior_records` cache (`_newly_overridden`, `_cache_hides_live_classifier`, the poisoned-manifest defense-in-depth). Re-runs re-read (cheap at 6–20 docs). The persisted artifact is the operator's **confirmed decisions** (invariant 6), not a classifier cache. *(Note: if corpora ever grow to hundreds of docs, restore content-keyed reuse of **model categories only, never operator consent** — a future note, not this instruction.)*

**Acceptance oracle (Step 4).**
1. A re-run re-reads and re-derives; the operator's confirmed decisions persist and still apply; the 032 fix-1 footgun cannot recur (no cache to swallow a classifier); no silent `zero_citable`.
2. **Forgery half:** a decision *removed* from the confirmed-decisions artifact stops applying, and nothing but the sanctioned writer can add one (mutation-bitten) — the property the deleted cache guard used to enforce now lives on the artifact.
3. No determinism-dependent test regresses beyond the intended change; fixtures updated by regeneration, not by hand.

---

## Fixture discipline
Do NOT hand-edit golden fixtures. New/updated fixtures (the Step-1 parse cases incl. the F1 sig-in-prose bypass and the F2 per-format cases, the read categorization goldens carrying `unconfirmed`, the single-channel round-trip + named-signal + revocation, the cache-removal behavior) are expected and generated via the sanctioned regeneration paths.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**. Touches QPB source (`doc_classification.py`, `reference_docs_ingest.py`, phase prompts, references) + the design. The orchestrator's `docs/design/QPB_v1.6.0_Design.md` §8a Revision is the spec — reconcile with it; do not revert it.
- Self-Council per §13 — charters map to the invariants: (a) **promotion is un-bypassable-by-content-alone** — trace every route to cited (Lane A parse, Lane B unconfirmed, operator channel, `_formal_tier`); the extension exploit, the F1 sig-in-prose bypass, and the self-classification case all resolve to background-or-confirm; mutation-bitten. (b) **no regression / demotion-free** — genuine specs/contracts still reach citable (Lane A or B/confirm), the F2 formats are handled, code is still Tier-3 fallback, byte-verification untouched, per-doc isolation holds, all kept downstream consumers still work. (c) **simplification is real, not relabeled** — deleted machinery is gone not renamed, one channel actually replaces four, the cache is removed not hidden, and consent semantics survive the removal. Artifacts under `RUNNER_ROOT/reviews/033_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_033_Self_Council/`. Iterate to unanimous SHIP.
- Verify the full suite; report counts + Python version.
- Output `outputs/033-sources-classification-simplification.md`: each step's before/after + its test; the extension-exploit-and-F1-bypass-now-not-cited proof; the F2 per-format results; the Lane-B `unconfirmed` end-to-end carry; the single-channel round-trip + named-signal + live revocation; the cache-removal + forgery-half proof; confirmation every kept consumer still works; remaining release items.

# Instruction 023 — v1.6.0 Feature G: shrink the classification floor to hard signals

A live end-to-end run on the Linux virtio subsystem exposed a defect: the advisory floor floored the **authoritative OASIS virtio spec** (`virtio-spec-behavioral-contracts.md`) to Tier 4 on a heuristic — *"high normative density (52 MUST/SHALL over ~1176 words) with hardening/configuration subject"* — even though the doc has **zero** CVE ids, advisory URLs, or security-genre title markers. A formal spec is normative-dense *by definition*, so that heuristic floors specifications as a class — the most-citable document type — defeating Feature G's entire purpose (requirements then come out Tier 3, not spec-grounded).

The root cause is a recurring smell across v1.6.0: **a regex/threshold making a genre/intent judgment the LLM should own.** This instruction removes that smell from the classification floor. The governing principle, sharpened by an external review (read it):

> The mechanical floor enforces only **hard, unambiguous, structural facts** (CVE/GHSA ids, advisory URLs, file extensions, README/issue-tracker names). Fuzzy genre signals (title words, code-density) become **advisory flags** recorded in the manifest and fed to the LLM classifier as inputs — they NEVER hard-floor a doc. And a cardinal rule surfaced by the review: **nothing becomes citable on content-sniffing alone** (promotion is the dangerous, integrity-affecting direction).

## Read first — these ARE the spec
- `~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.6.0_Simplification_Fable_Review_Response.md` — the external (Fable) review. Read Q1, Q5, Q7, and the disposition table. Its frame — *"which direction does a check fail, and what does failing cost?"* (demotion = availability, promotion = integrity, strictly more dangerous) — governs this change.
- `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` — the file you're editing. Key sites: `_ADVISORY_ID_RE` (:94), `_ADVISORY_URL_RE` (:98), `_ADVISORY_HEADER_RE`/`_SECURITY_GENRE_RE` title regexes (:110-124), the **density predicate** (:182-190), `machine_readable_contract` + `_CONTRACT_CONTENT_RE` (:200-223), `implementation_source` + its ≥50% content path (:244-262), `injection_signature` (:282-287), `_BACKGROUND_NAME_RE` (:82-85), and `_UNRESCUABLE_FLOOR_RULES` (:75-77).
- The preserved virtio run: `repos/virtio-1.6.0/quality/classification_manifest.json` (the mis-classification) — build the acceptance fixture from this real case.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Scope of THIS instruction
`doc_classification.py` floor simplification only. **In scope:** the seven edits below. **Out of scope (later instructions, name them in your output):** making the advisory floor *rescuable* via the confirmation ledger; wiring the LLM classifier + making its unwired/failed path loud + the zero-citable-corpus tripwire; the Feature H injection/fabrication changes; the render-contract labeled-slot changes.

## The edits

1. **Delete the density predicate.** Remove the `normative >= 5 AND density >= 0.004 AND _HARDENING_SUBJECT_RE` clause (:186-190) and the now-unused `_NORMATIVE_RE` / `_HARDENING_SUBJECT_RE`. A discriminator whose firing condition (normative density) is shared by both classes it separates (specs vs hardening guides) has no discriminating power.

2. **Genre-title regexes → advisory flags, not floors.** `_ADVISORY_HEADER_RE` and `_SECURITY_GENRE_RE` no longer force Tier 4. Instead, a title-zone match is recorded as an **advisory hint** on the classification record (a field the manifest carries and the LLM classifier will read as a demotion input). The doc flows to the normal classify path (LLM/default), no longer hard-floored. (A title is a hard string, but title→genre is a judgment — so it informs, it doesn't decide.)

3. **Implementation-source: keep the extension floor, downgrade the content sniff to a flag.** The `_IMPL_EXTS` extension floor stays a **hard floor** (a `.c/.py/.go` is implementation — structural). The **≥50%-code-shaped-lines content path** (:250-251, :258/:260 thresholds) stops flooring; it becomes an **advisory flag** ("looks code-heavy") on the record. Rationale (review Q5): code pasted into `.md`/`.txt` is common and its risk direction is *upward* (code treated as citable → circular requirements), so keep the signal — but as a flag feeding the LLM/manifest, not a silent floor or promotion.

4. **Contract content-signatures: nothing citable on content alone.** Keep the contract **extension** carve-out (`.proto`, `.d.ts`, `.wsdl`, …) as-is — those are unambiguous. In `_CONTRACT_CONTENT_RE`, **delete the bare `"$schema":` alternation and the generic GraphQL brace alternations** (`^\s*type\s+Query\s*\{` / `^\s*schema\s*\{`) — they promote arbitrary JSON configs / brace-blocks to citable (the dangerous direction). Keep only the **anchored, unambiguous** signatures (`syntax = "proto[23]"`, `openapi:`/`"openapi":` with a version, `swagger: "2`, `asyncapi:`, WSDL namespace). This is the review's single best cut.

5. **Delete the `injection_signature` advisory floor.** Remove `injection_signature` (:282-287) and `_INJECTION_RE`, and remove `RULE_INJECTION` from `_UNRESCUABLE_FLOOR_RULES`. It is an unrescuable Tier-4 floor duplicating a judgment the LLM already makes (and false-positives on a spec that describes itself as authoritative). *(Note: this deletes the injection floor in the CLASSIFIER only. The persona-grounding directive check in `persona_grounding.py` is a DIFFERENT, load-bearing control on the auto-apply path — do NOT touch it here; it is kept and narrowed in a later instruction.)*

6. **Narrow `_BACKGROUND_NAME_RE`.** Keep `readme` and `issue-tracker` (stable ledger names). Replace the free-floating `[^/]*coverage[^/]*` substring with exact stems (`coverage`, `coverage_report`) so it can't floor a real spec whose name merely contains "coverage".

7. **Keep untouched (the hard floor):** `_ADVISORY_ID_RE` (CVE/GHSA), `_ADVISORY_URL_RE` (advisory URLs), the `_IMPL_EXTS` and `_CONTRACT_EXTS` extension rules, and the README/issue-tracker names. These are the unambiguous structural signals. (Making the CVE/URL floor *rescuable* is the next instruction — not here.)

## Acceptance oracle (build a fixture for each; mutation-bite the security ones)
1. **The virtio case is fixed:** `virtio-spec-behavioral-contracts.md` (52 MUST/SHALL, 0 CVE/URL/security-title) is **no longer advisory-floored** — it flows to the LLM/default classification path, promotable.
2. **A real advisory still floors:** a CVE-bearing bulletin, and one with an advisory URL, still hard-floor to Tier 4 (the hard signals are intact) — mutation-bitten with an LLM stubbed to promote.
3. **No upward content-sniff:** a plain JSON config containing a `"$schema"` key is **not** classified as a citable contract; an OpenAPI file (anchored `openapi: 3…`) still is.
4. **Genre-title is a flag, not a floor:** a doc titled "Security Best Practices" with no CVE/URL is **not hard-floored** — it carries the advisory hint on its record and flows to the classifier.
5. **Impl content-sniff is a flag, not a floor:** a `.md` that is mostly pasted code carries the code-heavy flag but is **not** floored by content (a `.py` still floors by extension).
6. The classification manifest records the new advisory/code-heavy hint fields; existing byte-verification and formal-docs behavior unchanged.
7. Full suite green.

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. New fixtures (the virtio no-floor case, the retained CVE/URL floors, the `$schema` non-promotion, the genre/impl flag cases) are expected. If a prior test asserted the density floor or the injection floor as correct behavior, that assertion is now wrong — update it and explain the reversal in the output.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**.
- **Full 3-charter self-Council per §13 — this loosens a security floor, no shortcut.** Charters, each mutating panelist in its own worktree:
  - **(a) Downward-safety preserved:** the hard floors (CVE/GHSA, advisory URL, impl/contract extensions) still fire and are unrescuable-by-content; no advisory with a real signal can now reach citable. Mutation-bite each retained floor.
  - **(b) No upward promotion on content alone:** the `$schema`/brace deletions close the upward false-positive; nothing becomes citable without an extension hard-signal or (later) LLM classification. This is the integrity direction — scrutinize hardest.
  - **(c) The fuzzy signals are now flags, not decisions:** genre-title and code-density demote/inform only, never floor and never promote; the manifest records them; the virtio case is fixed.
  - Artifacts under `RUNNER_ROOT/reviews/023_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_023_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/023-feature-g-floor-simplification.md`: each edit + its before/after; the virtio-no-floor result and the retained-floor mutation results; the `$schema` non-promotion proof; the new manifest hint fields; any prior test assertions you had to reverse; and confirmation the persona-grounding directive check was NOT touched. Name the remaining follow-ups (rescuable-ledger, LLM-wiring + loud failures + zero-citable tripwire, Feature H directive-narrowing + detect_fabrication delete + Tier-guard mutation-pin, render labeled-slots).

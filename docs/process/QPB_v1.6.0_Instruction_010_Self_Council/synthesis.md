# Self-Council synthesis — instruction 010 (Feature G, dump-and-go doc ingest)

**Verdict: SHIP after FIX-REQUIRED resolved.** One panelist SHIP'd; two returned a
converging FIX-REQUIRED that was real; the fix landed and its exact missing test
was added, plus a defense-in-depth hardening two panelists recommended.

Reviewed code: branch `1.6.0`, the Feature G commits `175310a` (floor), `3b5bba6`
(ingest wiring + bundle propagation), `cb77f49` (docs/schema). Three panelists,
each in its own git worktree, each writing a full verdict to
`reviews/010_self_council/panelist_{A,B,C}_*.md`.

## Charters
- **A — the deterministic floor + sidecar bounds** (security-critical): can an
  advisory reach citable via *any* path?
- **B — classification correctness + reviewable/reproducible manifest + schema**.
- **C — machine-readable-contract carve-out + doc updates + byte-verification-unchanged**.

## Panelist verdicts
- **A: SHIP.** No path promotes an advisory to citable. Verified hands-on against a
  promote-everything LLM stub, extension-rename to every contract extension
  (incl. a doc carrying a real contract signature *and* a CVE), `sidecar_promote`,
  the `qpb_promote.txt`/`cite/` ingest path, and injection — all Tier 4. Advisory-
  FIRST ordering correct. Floor is **load-bearing**: two mutation bites (disable
  `advisory_floor` → 10 failures; reorder it after the contract carve-out → the
  renamed-extension guards fire). A legit MUST/SHALL-dense spec is not floored.
- **B: FIX-REQUIRED.** Manifest matches schemas.md §9.6/§1.6 **exactly** (no drift);
  genuinely content-keyed and reproducible; reviewable. **Blocker:** `ingest()`
  runs the plaintext-only `_collect()` gate before `classify_reference_docs`, so a
  dumped `.proto`/`.json`/`.py` raises `IngestError` before classification runs —
  making the feature unreachable end-to-end. The `IngestWiringTests` masked it by
  calling `classify_reference_docs` directly.
- **C: FIX-REQUIRED.** Contract carve-out correct both directions (code stays
  floored; genuine contracts content-detected; sidecar rescues impl-floor only).
  Byte-verification genuinely untouched (`citation_verifier.py`/`quality_gate.py`
  not in the diff; 356 citation/gate tests green). Docs match code. **Same blocker
  as B:** native-extension contracts abort `ingest()`; a missing end-to-end test
  hid it.

## The FIX-REQUIRED (converging B+C) — resolved
`ingest()`'s `_collect()` aborted on any non-`{.txt,.md,.rst}` extension. **Fix
(`bd3ffde`):** `_collect()` now SKIPS classification-eligible non-plaintext
extensions (contracts/code) instead of aborting — the classification pass tiers
them (a contract is citable, code is floored). Only genuinely binary /
convert-first formats (`.pdf`/`.docx`) still abort with the conversion hint. Added
the missing end-to-end tests through `ingest()`: a dumped `.proto`+`.json`+`.py`
no longer hard-stops and lands in the classification manifest (contract citable,
code floored); a `.pdf` still aborts. This is the classic "two verification layers
(wiring test + module test) agreed while the production path was incomplete" shape
— exactly what the self-Council exists to catch.

## Defense-in-depth applied (A+B recommendation) — `4a3cace`-style, commit after fix
Both A and B flagged the reproducibility cache: a reused prior record was trusted
verbatim, so a poisoned/hand-edited prior manifest could carry a stale citable
tier. Not a bypass under the threat model (prior records come from the operator-
reviewable `quality/` tree, not untrusted input), but closed cheaply: on every
cache hit the deterministic, content-only floor is re-run; if an ABSOLUTE floor
rule (advisory/impl/injection/background) fires and disagrees with the cache, the
fresh floored decision wins. The floor is content-deterministic, so this never
changes a legitimate reuse — it only defeats a poisoned cache. Pinned by
`test_poisoned_prior_manifest_cannot_launder_a_floored_doc`.

## Accepted residuals / recorded for the orchestrator (non-blocking)
- **Over-block false-positive (A):** a protocol spec dense in MUST/SHALL that also
  uses `configure`/`permission`/`enable` vocabulary can floor to Tier 4. Fails in
  the SAFE direction (Tier 3 instead of Tier 1), is the explicitly accepted §8a
  residual, and is manifest-visible/operator-overridable.
- **Classified-citable NON-plaintext contracts get a classification record but not
  yet a `FORMAL_DOC` byte-verification record** — the formal-docs manifest is still
  built from plaintext `cite/`. Full wiring of a classified `.proto` into
  `formal_docs_manifest.json` (so it is byte-citable, not just tiered) is the next
  integration layer. The classification tiering is produced and correct; the
  derivation AI consumes the classification manifest for tiering.
- **`.d.ts` content-detection minor gap (C):** extension-based detection covers
  `.d.ts`; a `.d.ts`-shaped file with a different extension may miss. Low impact.
- **The 3 `CorpusTierDistributionTests` "failures" panelists saw in their worktrees
  were an artifact** — `repos/{chi,express}-t3` are gitignored and absent from a
  detached-commit worktree; the tests pass in the main tree (verified). Not a code
  defect (A synthesized matching fixtures and confirmed correct behavior).

## Verification
Full suite green after the fix + hardening (see the instruction output for the
exact count); Python 3.14.6. All 31 classification tests pass, including the two
end-to-end `ingest()` tests and the poisoned-cache guard.

**Terminal verdict: SHIP.** The security floor was solid from the start; the
reachability blocker both panelists named is fixed with the end-to-end test they
said was missing; the cache residual is closed.

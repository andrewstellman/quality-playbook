VERDICT: SHIP

# Round-7 closure audit — self-Council verification of `7296569`

**Scope:** commit `7296569` ("close B-8 (HTML type 7) and generate the differential cases") against
the single blocking finding `round6_closure.md` left open — B-8, CommonMark HTML block type 7 as a
full FAIL=0 bypass — plus the charter's real question: **is the generated case list genuinely
self-extending, i.e. has the loop structurally ended?** Branch `1.6.0`, repo
`/Users/andrewstellman/Documents/QPB`, HEAD confirmed `7296569`.

**Method:** everything below was executed. No commit-message claim is taken on trust. I built an
independent probe harness driving `check_render_contract` over synthesized documents (reusing the
suite's own `RenderContractBase` fixture helpers so the baseline is the shipped one); reproduced all
four round-6 type-7 exploits; ran the charter's self-extension experiment in both directions against
a `shutil.copy2` pristine snapshot with scoped `__pycache__` purges; attacked the remaining surface
with 32 interaction constructs the generator does not produce; and swept all 105 archived `quality/`
trees at three commits.

The tree was clean at start and at end, and `quality_gate.py` is byte-identical (SHA-256
`a76ddfc0…`) to the committed version after every mutation.

---

## Summary table

| Item | Status |
|---|---|
| **B-8** — HTML block type 7 | **CLOSED** — all four shapes FAIL=3, no false PASS |
| Safety property (inline HTML in prose not blanked) | **CONFIRMED** — both shapes FAIL=0 WARN=0 |
| Preceding-blank-line rule is what gates it | **CONFIRMED** — correct in all three directions |
| **Self-extension: adding a tag extends coverage** | **CONFIRMED** — 126 → 127, case auto-generated |
| **Self-extension: removing a tag goes RED** | **CONFIRMED, but via the coverage pin only** — see below |
| Type-6 cases discriminate against the type-6 model | **REFUTED** — neutering type 6 entirely leaves all 6 tests GREEN |
| Full suite | **CONFIRMED** — 2540 tests, 0 failures, skipped=13 |
| Three fixtures FAIL=0 WARN=0 | **CONFIRMED** — 15 PASS lines each, genuinely evaluated |
| Archived sweep, 105 trees | **CONFIRMED** — 0 render-contract FAILs; 0 flips at every commit pair |
| Fixture inputs SHA-256 unchanged | **CONFIRMED** — all six identical to `edc5cec` |
| Dead code removed | **CONFIRMED** — 0 references to either symbol |
| Tree clean | **CONFIRMED** |
| Types 3/4/5 (`<?php`, `<!DOCTYPE`, `<![CDATA[`) | **OPEN — non-blocking follow-up**, gate-level FAIL=0 bypass |

---

## 1. B-8 is closed

Round 6's exploit reproduced exactly — the three §5.2 mandatory sections each preceded by a type-7
tag, in the shape round 6 published (opener only, no closing tags), and also in a closed-tag variant:

| Exploit | Gate | Mandatory sections the reader sees |
|---|---|---|
| `<span>` | **FAIL=3** | none |
| `<a href="x">` | **FAIL=3** | none |
| `</span>` | **FAIL=3** | none |
| `<mytag>` | **FAIL=3** | none |

Round 6's `<span>` case scored **FAIL=0 with all three reported present**; it now scores FAIL=3 and
names all three as missing. No false PASS on any of the four. Baseline: the clean document is
FAIL=0 WARN=0, so the FAILs are the mutation's doing, not a broken fixture.

**The stated safety property holds.** This was the part of the commit most likely to be a
rationalization — type 7 is broad, and blanking it could plausibly have swallowed legitimate inline
HTML. It does not:

| Document | Gate |
|---|---|
| `Application developers see <br> here mount routers;` (mid-sentence) | **FAIL=0 WARN=0** |
| `Some prose with <span>inline</span> markup.` in the Overview | **FAIL=0 WARN=0** |

**The preceding-blank-line rule is genuinely what gates it**, and it is right in all three
directions — including the subtle part, that type 7 may *not* interrupt a paragraph while type 6
*may*:

| Case | our model | reference parser | |
|---|---|---|---|
| type-7 tag after a blank line | does not see heading | does not see heading | agree |
| type-7 tag mid-paragraph | **sees heading** | **sees heading** | agree |
| type-6 `<div>` mid-paragraph | does not see heading | does not see heading | agree |

That middle row is the one that matters: it is the reason `see <br> here` survives, and our model
and the authority agree on it rather than our model merely being lucky.

*Minor:* the commit says the type-7 exploits "now FAIL=4"; I measured FAIL=3. The count is a
function of how much of the document the wrapper covers (wrapping every `##` heading gives FAIL=5).
Document-dependent arithmetic, not a false claim — the substantive assertion, that these now FAIL,
holds on every shape I tried.

---

## 2. Self-extension: half-confirmed, and the half that fails is worth stating precisely

This is the crux of the "loop has ended" claim, so I ran the charter's experiment in both
directions.

**Adding a construct to the model DOES automatically extend coverage — confirmed.** Adding
`|frobnicate` to `quality_gate._RENDER_HTML_BLOCK_TAGS` took the case list from **126 to 127**, with
`html_type6_frobnicate` generated automatically as
`'<frobnicate>\n## Actors and roles\n</frobnicate>\n'`. The mechanism is real and the commit
message's literal claim is true.

**Removing a tag DOES go RED — but not through the differential.** Deleting `div` from the tag list
turned the module RED with one failure, and that failure was
`test_case_list_covers_the_constructs_that_broke` — the hardcoded regression pin — **not**
`test_model_agrees_with_reference_parser`. The agreement test passed.

That prompted the decisive experiment, which the charter did not ask for but which the first result
demanded:

> **Neutering `_RENDER_HTML_TYPE6_OPEN_RE` entirely — replacing it with a regex that never matches,
> so the gate models no type-6 block at all — leaves all 6 tests GREEN.**

The reason is structural. **Every generated type-6 case sits at the start of the case body, i.e.
after a blank line** — which is exactly the position where the newly-added type 7 catches any
complete tag. Type 7 is a total backstop for the generated type-6 corpus, so all **62** type-6 cases
have **zero** discriminating power against the type-6 implementation.

This is a real, if narrow, regression in instrument strength: round 6 recorded a mutation bite
"type-6 HTML handling disabled → **RED**" against the old 34-case hand-written list. That same bite
is now **GREEN**. Generation bought breadth and lost one dimension of depth.

It is **not** a live bypass — the shipped gate models type 6 correctly, verified above on
mid-paragraph `<div>`, and I confirmed the shape the differential is blind to is genuinely a bypass
*if* the model were broken (type-6-neutered gate, `some prose\n<div>\n## Actors and roles` — ours
sees the heading, the reference parser does not). The gap is in the test's case generation, not in
the gate. Follow-up, not a blocker.

---

## 3. Remaining surface — 32 interaction constructs

I ran every construct the charter named plus twelve more, comparing our model against the reference
parser, then re-checked every disagreement at the full-gate level.

**Agreed (no finding):** fence inside an HTML block; HTML block inside a fence; type 7 immediately
after type 6 with no blank line; type 6 immediately after type 7; BOM at start (both HTML and fence
variants); tab-indented fence; fence opener with trailing whitespace (both delimiters); `<!-->` and
`<!--->` degenerate comments; type-6 attributes spanning two lines; type-7 attributes spanning two
lines; the probe heading appearing twice with one occurrence quoted (both fence and HTML variants);
fence in a blockquote; 3-space and 4-space indented fences; nested 4-then-3 fences; unclosed `<pre>`;
CRLF fences; heading with trailing whitespace; `<span\n>`; `<http://x>`.

That is a strong result for a hand-aimed attack against a generated corpus. Three findings:

### 3a. Types 3/4/5 are a gate-level FAIL=0 bypass — non-blocking, but it is B-8's shape verbatim

| Wrapper | CommonMark type | Gate | Mandatory sections the reader sees |
|---|---|---|---|
| `<?php` | 3 (processing instruction) | **FAIL=0 WARN=0** | **none** |
| `<!DOCTYPE` | 4 (declaration) | **FAIL=0 WARN=0** | **none** |
| `<![CDATA[` | 5 (CDATA) | **FAIL=0 WARN=0** | **none** |

This is round 6's B-8 one type over: a reader sees none of the three §5.2 mandatory sections and the
gate certifies the document clean with all three reported present.

The structural criticism round 6 leveled at type 7 applies here unchanged — the exclusion lives in a
**code comment** ("Types 3/4/5 … are vanishingly unlikely in a requirements document and are
deliberately not modelled"), there is **no generated case**, and there is **no
`INTENTIONAL_DIVERGENCES` row**, so neither `test_divergences_are_conservative_not_permissive` nor
the differential can see it. And it is a **permissive** divergence, which the same comment block
forbids three paragraphs further down: *"a divergence from the reference grammar may be conservative
… but never permissive. A permissive divergence is a bypass wearing a rationale."* The code
currently contains a permissive divergence that contradicts the rule stated in its own comment.

**Why this does not block.** Round 6 examined types 3/4/5 explicitly and adjudicated them
*"defensibly — they are genuinely implausible in a requirements document"*, blocking only on type 7.
Reversing that adjudication in round 7, on evidence round 6 already had, would be the precise
goalpost-moving pathology this Council is trying to exit. Against the charter's blocking criteria:
this is not reachable by an honest renderer — it requires deliberately emitting `<?php` or
`<!DOCTYPE` immediately before each mandatory section heading, which is a strictly stranger act than
the `<span>` of B-8 and which no LLM renderer produces. It is not a regression, not a false claim,
and not a failure of the self-extension property.

### 3b. CRLF — model-level only, no live issue

`_RENDER_HTML_TYPE7_OPEN_RE` anchors on `[ \t]*$`, so under CRLF the trailing `\r` defeats the
type-7 match. At the model level, `<span>\r\n## Actors and roles\r\n` is a disagreement. At the
**gate** level it is not exploitable, and CRLF documents are not newly broken:

- CRLF + `<span>` exploit: **FAIL=3** (still caught)
- conforming document converted wholesale to CRLF: **FAIL=0 WARN=0** (no false positive)

Type 6 and the fence grammar both handle CRLF correctly (the fence closer test strips). Worth
tightening the type-7 anchor for robustness; nothing is broken today.

### 3c. Closing-hash ATX — round-6 follow-up #1 is only half-closed

The probe now routes through the gate's own `_RENDER_LEVEL2_RE` as the commit claims, but that regex
does not strip trailing hashes, so `## Actors and roles ##` still registers as a model-level
disagreement (false-positive direction). At the gate level it is handled correctly — a document
whose three mandatory headings all carry closing hashes is **FAIL=0 WARN=0**. Conservative
direction, cosmetic, non-blocking; round 6 reached the same conclusion.

---

## 4. No regressions

- **Suite:** 2540 tests, **0 failures**, skipped=13. Matches the claim exactly.
- **Three regenerated fixtures:** chi, express, virtio each **FAIL=0 WARN=0** with **15 PASS lines**
  each — genuinely evaluated, not inert. (The paired `.before` inputs still score FAIL=12/11/8, so
  the fixtures retain their discriminating power.)
- **Archived sweep, 105 trees** under `repos/` and `metrics/`: **0 render-contract FAILs** at every
  commit. Flips `4255002` → `94c7e3d` → `7296569`: **0, 0, and 0** end-to-end. The 5 WARNs are
  identical at all three commits, so they are not this commit's doing.
- **Fixture inputs:** all six `REQUIREMENTS.before.md` / `requirements_manifest.before.json`
  SHA-256 **identical** to `edc5cec`.
- **Dead code:** `_RENDER_HTML_BLOCK_OPEN_RE` / `_RENDER_HTML_BLOCK_CLOSE_RE` — **0 references**,
  removed as claimed.
- **Setext** is now an `INTENTIONAL_DIVERGENCES` row with a justification, as claimed.
- **Tree clean**; gate SHA-256 restored after every mutation.

Every other commit-message claim I checked held.

---

## Has the loop ended?

**Yes, in the sense that matters — with one honest qualification.**

`7296569` did the thing round 6 asked for: it closed the bypass and removed the structural weakness
that produced it. Coverage is no longer a function of what the model's author thought to write down
along the axis that actually broke five times. I verified the self-extension mechanism by experiment
rather than by reading it, and it works.

The qualification is that generation extends coverage along **one** axis — the tag constant — and
the two things it does not do are visible in this audit. It does not enumerate CommonMark *block
types*, which is why types 3/4/5 remain outside both the model and the case list. And it generates
every case in the **same context** (start of body, after a blank line), which is why the 62 type-6
cases are fully backstopped by type 7 and detect nothing about the type-6 model. "The next construct
becomes a test failure rather than a seventh review round" is true for a new type-6 *tag*; it is not
true for a new block *type*, and the type-3/4/5 result is the demonstration.

On the weighing the charter asks for: this is a quality gate for a self-audit tool, not a security
boundary. The realistic failure mode is an LLM renderer accidentally emitting a flat document —
overwhelmingly via **code fences**, which is the defect class actually observed in the chi / express
/ virtio benchmark runs, and which is closed, authority-checked, mutation-bitten and swept. Every
bypass found since round 3 has required deliberately placing a suppressing construct immediately
before a section heading, and the remaining ones require constructs (`<?php`, `<!DOCTYPE`,
`<![CDATA[`) stranger than any renderer emits. The residual risk is adversarial-only; the
regression evidence is complete; the instrument is real and now self-extending along the axis that
historically broke.

Seven rounds is enough. Ship it, and carry the follow-ups.

---

## Non-blocking follow-ups for the orchestrator

1. **Types 3/4/5 are a permissive divergence with no guard.** Either model them (they close the same
   way types 2/6/7 do — run to the next blank line) or add explicit `INTENTIONAL_DIVERGENCES` rows
   with generated cases so `test_divergences_are_conservative_not_permissive` can see them. As it
   stands the code holds a permissive divergence that the comment eight lines below declares
   forbidden. Modelling them is the smaller change and closes the class rather than the instance.
2. **Generate each case in more than one context.** Emit every construct twice — once after a blank
   line and once mid-paragraph. This restores the type-6 bite that generation lost and would make
   the type-6/type-7 distinction load-bearing in the test rather than incidental.
3. **Anchor `_RENDER_HTML_TYPE7_OPEN_RE` tolerantly of `\r`** (`[ \t\r]*$`, or normalize line endings
   once on entry to `_render_blank_fences_ex`). No live exploit; pure robustness.
4. **Trailing-hash ATX** — either strip closing hashes in `_RENDER_LEVEL2_RE` or add
   `closing_hash_atx` to `INTENTIONAL_DIVERGENCES` so the differential stops reporting a known,
   benign, conservative disagreement. Round-6 follow-up #1, still half-open.
5. **Consider a case-count floor assertion** (e.g. `assertGreater(len(CASES), 120)`), so a future
   edit that accidentally empties a generation loop fails loudly rather than silently shrinking the
   corpus.

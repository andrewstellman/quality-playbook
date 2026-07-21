# `docs_gathered/` — provenance and usage notes

This directory holds curated documentation sets for ~40 open-source projects used by the Quality
Playbook (QPB) benchmark harness. It is about to serve a new, more load-bearing role: the
**acceptance oracle for QPB v1.6.0's requirements-validation testing.**

## What this directory is for

QPB derives candidate requirements/invariants from a target project's source code. The open
question a derivation run has to answer is: *did QPB correctly capture what the project is
supposed to do?* That question can only be answered by checking the derived requirements against
an independent description of intended behavior — never against the implementation itself.

**Load-bearing rule: requirements are judged against documentation, never against the
implementation.** Checking a derived requirement against the code that produced it is circular —
every bug in the code becomes, by construction, a "correctly captured" requirement, because the
requirement just restates what the code does. Documentation (official docs, specs, issue-tracker
discussion of intended vs. actual behavior, CVEs, tests-as-invariants) is gathered *independently*
of the derivation pipeline specifically so it can serve as ground truth the derivation didn't see
being built. This directory is that ground truth corpus.

## How the sets were produced

Andrew's working assumption going into this review was that most sets were gathered either by
asking Claude directly, or by running a formal **document-gathering prompt**
(`references/DOC_GATHERING_PROMPT.md` in this repo). The evidence says the picture is more
specific than that — worth stating plainly rather than smoothing over:

- **`references/DOC_GATHERING_PROMPT.md` is a real, current artifact — but it is newer than
  essentially the whole existing corpus.** It first shipped in commit `3c836e9` ("docs: ship
  DOC_GATHERING_PROMPT + README/TOOLKIT discoverability"), dated **2026-05-24**, refined same day
  (`48d1859`, `daf1fc1`), then wired directly into `SKILL.md` in commit `3d7c3b9` ("skill: ship
  doc-gathering protocol + TOOLKIT.md"), dated **2026-05-28**. It instructs a gathering assistant
  to: ground itself in `TOOLKIT.md` first, confirm the project and wait for a reply, then crawl
  ~16 source types (official docs, repo/README/ADRs, issue trackers — with a **mandatory**
  `issue_tracker_coverage.md` ledger — CVEs, discussions, tests, schemas, changelogs, threat
  models), and write one theme file per output with a leading `## Invariants` section where every
  invariant carries a verbatim quote + URL, tiered into `reference_docs/cite/` (authoritative) vs.
  top-level `reference_docs/` (advisory/background).
- **No set in this directory carries the prompt's two mandatory artifacts.** A direct filesystem
  check found zero `issue_tracker_coverage.md` files anywhere under `docs_gathered/`, and a `cite/`
  subfolder in only three sets (`claude-api/`, `pdf/`, `skill-creator/`) — whose file mtimes
  (2026-04-27) predate the prompt's existence by four weeks, so even those weren't produced by it.
- **Multiple sets are independently dated before the prompt existed, from evidence inside the
  files themselves:** `cobra/INDEX.md` states "Compilation Date: 2026-04-04"; `axum/*.md` files
  are stamped "Accessed: April 2026"; `httpx-docs.zip` / `jq-docs.zip` / `click-docs.zip` (raw
  crawl dumps sitting at the top level, apparently an earlier pass predating the processed
  `httpx/`, `jq/` folders) carry file dates of 2026-05-20/21 — still before the prompt shipped.
  A 2026-04-22/23 chat session already references pre-existing `docs_gathered/` content for
  `bus-tracker` and `virtio`.
- **`cpython` (and `keras`, `budibase`) were gathered via a separate, bespoke mechanism**: a
  purpose-written gatherer brief for the CVE security-benchmark work (`Cowork-2026-06-10-Quality
  Playbook 1.5.9 Opus`: *"The doc-gathering for keras/cpython/budibase is the gating
  prerequisite... straight off the v2 methodology"*), not `DOC_GATHERING_PROMPT.md`.
- **For the remaining sets in the 20-project matched list** (`cobra, axum, jq, redis, serde,
  pydantic, zod, javalin, gson, httpx, apollo11, chi, edgequake, express`), a targeted search of
  the chat archive (`AI Chat History/`) found no transcript combining the project name with
  gathering activity in a way that identifies method or date — **provenance not determined**
  beyond "ad-hoc, and pre-dates the formal prompt" (the file-naming pattern predates and appears
  to have informed the prompt's later theme-file convention, not the reverse — see below).
- **Practical conclusion:** treat this corpus as **ad-hoc/direct-Claude-request gathered**,
  produced before `DOC_GATHERING_PROMPT.md` existed as a formal artifact. The prompt is a
  *forward-looking* protocol for gathering future sets (or re-gathering these with the
  coverage-ledger and cite/-tiering discipline it now requires), not a description of how the
  current corpus came to exist. Any future re-gather done with the formal prompt should be
  recognizable by the presence of `issue_tracker_coverage.md` and a `cite/` subfolder — their
  absence in a set is a reliable (if only one-directional) signal that the set predates the
  protocol or wasn't produced by it.

## Structure conventions observed

There is real variation, and it does **not** cleanly separate into "prompt-driven vs. ad-hoc" —
see above:

- **Numbered theme files + `INDEX.md`**: `axum`, `bus-tracker`, `chi`, `click`, `cobra`, `express`,
  `httpx`, `javalin`, `jq`, `pydantic`, `redis`, `serde`, `zod`. This looks like the formal
  prompt's theme-file output shape, but `cobra` and `axum` are independently dated to April 2026 —
  before the prompt existed. Read this as Andrew's pre-existing personal convention that the later
  prompt wrote down, not evidence the prompt was actually run.
- **Flat lowercase-topic files, no `INDEX.md`**: `apollo11`, `avro`, `cpython`, `gson`, `jsPDF`,
  `keras`, `setuptools`, `spark`, `virtio`.
- **A `cite/` subfolder present**: only `claude-api`, `pdf`, `skill-creator` — again pre-dating the
  formal prompt.
- **Sparse/thin sets** (see depth table below): `edgequake` (3 files), `apollo11` and `virtio`
  (6 files each).
- **Raw unprocessed dumps** sitting at the top level rather than in a themed project folder:
  `httpx-docs.zip`, `jq-docs.zip`, `click-docs.zip` — apparently earlier-pass crawl output kept
  alongside the later processed `httpx/`, `jq/`, `click/` directories rather than folded in or
  discarded.
- None of the sets observed use the prompt's authority-aware section titles (`## Invariants` /
  `## Known Failure Modes` / `## Candidate Audit Leads`) or its quote+URL-per-invariant format —
  another confirmation that the corpus predates that convention.

## Which sets have a matching source checkout under `repos/clean/`

Only a doc set with **both** gathered docs here **and** a source checkout under `repos/clean/` can
be used for a full requirements-derivation test (derive from source, validate against docs).
Verified directly against both directory listings — exactly **20** projects have both:

`apollo11, axum, bus-tracker, chi, claude-api, cobra, cpython, edgequake, express, gson, httpx,
javalin, jq, pdf, pydantic, redis, serde, skill-creator, virtio, zod`

Everything else in this directory (`addressable, adonisjs-http-server, avro, budibase, click,
compliance-trestle, dasel, ech0, erb, evervault-go, gogs, jsPDF, keras, quality-playbook,
setuptools, spark`) has gathered docs but **no** matching entry in `repos/clean/` — these can't
support a full derive-and-validate test against this benchmark's source tree today. (`casbin` is
the inverse case — it has a source checkout in `repos/clean/casbin` but no correctly-placed doc
set here; see "The nested `docs_gathered/docs_gathered/` directory" below.)

## Doc-set depth (file counts, matched-20 projects)

| Project | Files | Notes |
|---|---|---|
| apollo11 | 6 | thin |
| avro* | 10 | *no source checkout |
| axum | 10 | |
| bus-tracker | 11 | |
| chi | 18 | Feature C fixture — see caution below |
| claude-api | 10 | |
| cobra | 20 | |
| cpython | 13 | |
| edgequake | 3 | very thin |
| express | 19 | Feature C fixture — see caution below |
| gson | 20 | |
| httpx | 19 | |
| javalin | 16 | |
| jq | 10 | |
| pdf | 8 | |
| pydantic | 10 | |
| redis | 10 | |
| serde | 13 | |
| skill-creator | 8 | |
| virtio | 6 | thin — Feature C fixture, see caution below |
| zod | 10 | |

Thin sets (`apollo11`, `edgequake`, `virtio`, and to a lesser extent `pdf`/`skill-creator`/
`claude-api`) make coverage-completeness effectively unmeasurable: there isn't enough documented
surface area to tell whether a derivation run's gaps are real misses or just areas the doc set
never touched. Treat a "clean" result against a thin set with a scored asterisk, not full
confidence.

## Caution: chi, express, and virtio are the Feature C fixture repos

`QPB_v1.6.0_Design.md` §1.2 built the "generated spec is not a well-organized document" analysis
(coherence defects C-1 through C-7 — scrambled identifiers, degenerate sections, pipeline internals
leaking into the render, bug-shaped requirements, etc.) directly from the 2026-06-19 benchmark
runs against `chi`, `express`, and `virtio` (`repos/chi-1.5.8/quality/REQUIREMENTS.md` and
siblings). Because the defects Feature C is meant to fix were *diagnosed on these three repos*,
running the fixed pipeline against them again measures **regression** (did the known defects come
back?), not **generalization** (does the fix work on repos it wasn't tuned against). Any coverage
or coherence claim for v1.6.0 needs at least one clean project outside this trio to mean anything
about generalization.

## The nested `docs_gathered/docs_gathered/` directory (casbin)

`docs_gathered/docs_gathered/` currently holds 8 casbin files (`casbin-adapters-watchers.md`,
`casbin-cves.md`, `casbin-github-issues.md`, `casbin-matchers.md`, `casbin-model-reference.md`,
`casbin-multitenancy.md`, `casbin-perm-model.md`, `casbin-policy-effects.md`). This looked at first
like a simple path error (a set that should be `docs_gathered/casbin/`), and there is no existing
top-level `casbin/` entry to conflict with a move.

**But investigation surfaced a reason to leave it alone rather than just fix the path.** QPB's own
git history (commit `ee9bf3c`, "security blind benchmark v2 rebuild: quarantine contaminated
corpus...") shows that a `repos/docs_gathered/casbin/` directory — plausibly this same content —
was deliberately **quarantined** (renamed to `repos/docs_gathered.contaminated/casbin/`) after a
2026-06-02 Contamination Council audit found the original security-benchmark corpus had been
"gathered backwards from the known CVE, so corpus shape itself encoded the answer," and explicitly
named casbin as one of three repos (with `openfga`, `nats-server`) "never scrubbed at all." The
methodology doc's own follow-up list still carries this as an **open, undecided item**: "Decide
what to do with openfga/casbin/nats-server (Goal A real-world runs, not blind benchmark)" — as of
that writing, unresolved. `docs_gathered.contaminated/` no longer exists in the working tree
(gitignored, and this leftover copy predates that whole event, per its 2026-04-22 mtime — before
even the quarantine commit existed), so this nested folder cannot be confirmed as *the exact*
quarantined copy, but it is undeniably casbin material sitting outside the normal
`docs_gathered/<project>/` convention, tangled up with a separate, still-open contamination
question from an unrelated research track (CVE-blind-benchmark work, not the v1.6.0
requirements-validation oracle this directory otherwise serves).

**Recommendation:** do not fold this into `docs_gathered/casbin/` without Andrew's explicit call.
The content may be perfectly fine for requirements-validation purposes even though it was flagged
for a different reason (backward-gathering bias specific to blind CVE-detection scoring) — but
that's a judgment call belonging to the person who ran the Contamination Council, not something to
resolve by moving files. Left in place, undeleted, pending that decision.

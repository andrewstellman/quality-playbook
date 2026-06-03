# Quality Playbook — Documentation Gathering Prompt

*TL;DR: Copy the prompt block below, open your project in Claude Code, Codex, Copilot, Cursor, Windsurf (or any capable AI tool), paste it in, and run it. It walks you through gathering documentation for the project.*

The Quality Playbook (QPB) works best when it can read background documentation about the project it's auditing. QPB derives the project's **intended behavior** — especially its security and other non-functional invariants — from this material, then checks the code against it. Good gathered docs are the difference between catching the high-value "code does the wrong thing" defects (authorization gaps, tenant-isolation leaks, consistency violations) and only catching shallow ones.

This file is a **reusable prompt** that turns any capable AI tool into a documentation-gathering assistant. Open a brand-new chat — even in an empty folder — paste the block below, and it walks you through the rest. The only thing you have to supply is a project name (e.g. *Ory Keto*); everything else it figures out or asks about as it goes. Tools with web search plus file creation can do the public-source gathering; tools with enterprise connectors or MCP (Slack, Teams, Discord, Jira, Confluence, Bitbucket, SharePoint) can also mine internal sources, which are often where the real intent lives.

**How to use it**

1. Paste the prompt block into a fresh chat (Cowork, Codex, OpenClaw, Claude, etc.).
2. It confirms the project, explains what it's about to gather, and asks whether to add any sources (specific URLs, or MCP/enterprise connectors like Jira/Confluence/Slack) — then waits for your reply. Answer it, and it runs a deep, exhaustive crawl by default (no need to specify a depth).
3. Review the files it writes before you run QPB. You're the editor; it's the researcher.

You can split one project across tools — e.g. a Cowork chat for public docs + CVEs and a Codex chat for your internal Jira/Confluence/Slack — as long as they write to the same output folder.

---

## The prompt (copy everything in this block)

```
You are a documentation-gathering assistant for the Quality Playbook (QPB), an automated
code-quality and requirements analysis. Your job is to gather background documentation about a
software project so QPB can derive the project's intended behavior — and especially its
non-functional invariants (security, reliability, performance, etc.) — and check the code
against them. You capture INTENT: what the system is supposed to do, what guarantees it makes,
what must never happen. Work through the steps below conversationally; don't dump everything at
once. The downstream analysis is only as good as what you gather, so prefer primary sources and
cast a wide net.

STEP 0 — GROUND YOURSELF IN QPB (required; this is also a capability check).
Fetch QPB's TOOLKIT.md and read it before you gather anything. It defines what a QPB
requirement/invariant is, how the reference_docs/ corpus is used, and why intent matters —
without it you will gather the wrong documentation.
  - Fetch the raw file from:
    https://raw.githubusercontent.com/andrewstellman/quality-playbook/refs/heads/main/ai_context/TOOLKIT.md
    (the same file is browsable at
    https://github.com/andrewstellman/quality-playbook/blob/main/ai_context/TOOLKIT.md)
  - If the user explicitly handed you TOOLKIT.md or a local path to it, use that instead.
Read TOOLKIT.md from one of (in order): (a) the URL fetch above; (b) a user-provided
attachment or local path; (c) a repository copy at ai_context/TOOLKIT.md if you're inside a
QPB clone. If you cannot read TOOLKIT.md by ANY means, STOP and tell the user.

PROVE YOU READ IT. Your Step 0 confirmation line must quote the first non-blank sentence of
TOOLKIT.md verbatim, in single quotes, inline. Example:
  Read QPB TOOLKIT.md — first sentence: '<verbatim quote>'. I'll gather intent and invariants
  for a QPB audit.
This prevents URL-slug hallucination (a tool that didn't actually read the file can't reproduce
the first sentence) and makes the grounding step verifiable.

THEN REPORT YOUR GATHERING CAPABILITIES in one line: web search? page fetching? file creation?
repository/file-system access? issue tracker access? MCP / connector access (Jira / Confluence /
Slack / Teams)? Operators may have a tool with some-but-not-all of these — gather what you can,
and explicitly list the coverage gap in your Step 1 message so the user knows what won't be
covered. Then continue.

STEP 1 — IDENTIFY THE PROJECT, EXPLAIN THE PLAN, AND ASK ABOUT SOURCES — THEN STOP AND WAIT.
If the user hasn't named a project, ask for one (a name is enough). Web-search to find the
canonical repository, the official docs site, and the project's domain (what it does, what
security/correctness guarantees it's expected to make). Then, in ONE message to the user:
  - Show what you found: repo URL, one-line description, primary language, domain.
  - Explain what you're about to do: a DEEP, EXHAUSTIVE crawl across the SOURCES below (name the
    themes you'll produce), following additional relevant resources you discover along the way.
  - Ask THREE questions: (1) Is this the right project? (2) Are there any additional sources you
    should use — specific URLs, internal/enterprise documentation, or connector / MCP sources
    (Jira / Confluence / Slack / Teams / Bitbucket, OpenClaw-style gateways)? (3) Which version,
    branch, tag, release, product edition, or deployment mode should the gathered docs target?
    CVE applicability, deprecated behavior, and feature-flagged invariants all depend on this. If
    the user can't answer, gather against the latest stable release and record the assumption
    explicitly in ## Context of each file.
Then STOP and WAIT for the user's reply.

CRITICAL — mechanical stop: end your Step 1 message with exactly this sentence on its own line,
with nothing after it:

→ WAITING FOR YOUR REPLY BEFORE I BEGIN GATHERING.

Do not fetch any URL, write any file, or plan Step 2 in this turn. The next thing you do must be
reading the user's response.

Specifically forbidden in this turn:
- 'I'll go ahead and start with the official docs while you confirm' → don't do this.
- 'Let me at least fetch the README first' → don't do this.
- 'I'll assume this is the right project and proceed with the default sources' → don't do this.
- Any tool call to a URL other than the Step 0 TOOLKIT.md fetch that already happened in this turn.

If you output anything beyond Step 1 before the user replies, you have failed your instructions.
Do NOT ask about depth — a deep crawl is the default; you are only confirming the target, the
target version/branch if known (question 3 above), and collecting any extra sources before you
start.

STEP 2 — AFTER THE USER REPLIES, CRAWL DEEPLY (begin only once they've responded to Step 1).
Once the user has confirmed the project and named any additional sources (or told you to go
ahead), do a DEEP, EXHAUSTIVE crawl across every source type in SOURCES, plus any extra sources
they gave you, and look for additional relevant resources beyond that list — crawling any you
find and can reach.
Default OUTPUT_DIR: a reference_docs/ folder in the current directory (create it if needed). If the
user is working inside an actual target repo, write into that repo's reference_docs/ instead.
TIERING (important): reserve reference_docs/cite/ for AUTHORITATIVE specs/contracts the code is
expected to conform to — the official model/API spec, the security model, the project's own spec,
cited standards. Put CVE/advisory and issue-tracker/discussion material in the TOP-LEVEL
reference_docs/ (NOT cite/): it is background context, not an authoritative contract, and must not
be citable as one — treating an advisory as authoritative is a known false-positive trap.

STEP 3 — GATHER AND WRITE.
Crawl deeply and write one Markdown file per theme into OUTPUT_DIR. Be EXHAUSTIVE, not
representative — enumerate and fetch, don't sample. For the official docs, follow the site's
navigation and fetch every relevant section, not just the landing page. BE ESPECIALLY THOROUGH
WITH ISSUE TRACKERS — this is the source agents most often under-gather. Use the tracker's search
and label filters and page through MULTIPLE pages of OPEN and CLOSED issues; do not stop at the
first page or the most recent few. Closed bugs are gold — a fixed bug reveals an invariant that
was once violated. Sort by most-commented / most-reacted to surface recurring pain points, and
record the themes systematically, not just a handful of tickets. Treat the SOURCES list below as
a FLOOR, not a
ceiling: actively discover additional relevant material it doesn't name — follow links out of the
docs, the repo, and the issues; find release notes and changelogs, RFCs or standards the project
cites, security advisories of key dependencies, and maintainer blog posts or conference talks. If
you find a relevant source the list didn't anticipate, gather it too.

SOURCES — cast a wide net across public and (if you have access) internal sources. This list is a
floor, not a ceiling.
Public:
1. Official documentation and specifications — architecture, data model, API reference,
   configuration, and the security / authorization model specifically.
2. The repository itself — README, /docs, design docs, RFCs, ADRs, SECURITY.md, and code
   comments that state invariants.
3. Issue trackers — THE most commonly under-gathered source, so be thorough, not cursory. Use
   the tracker's search and label filters and page through MULTIPLE pages of OPEN and CLOSED
   issues (bug / security / authz / data-loss / "known issue" / regression). Don't stop at page
   one or the most recent few. Closed/fixed bugs are especially valuable — each reveals an
   invariant that was violated. Sort by most-commented / most-reacted to find recurring pain
   points, and record the themes (with representative issue links), not just individual tickets.
   Coverage ledger required. Create reference_docs/issue_tracker_coverage.md recording, for
   each tracker:
   - the query/filter you used
   - open/closed status + sort order
   - pages examined (numbered)
   - approximate result count
   - themes extracted (with representative issue links)
   - which output file the themes fed into
   Minimum public-GitHub pass when available:
   - 5+ pages of closed issues sorted by most-commented (or most-reacted)
   - 3+ pages of open issues sorted by most-commented, filtered to bug/security/regression
     labels (or equivalent — adapt to the project's label scheme)
   - keyword searches across: security, auth, authz, authorization, tenant, isolation,
     data-loss, consistency, race, regression, panic, crash (add domain-specific terms)
   Stop rule: stop paginating only after 2 consecutive pages produce no new invariant theme.
   Not before. If you cannot paginate or sort (e.g. the tracker doesn't expose those), record
   that limitation explicitly in the coverage file rather than pretend exhaustiveness.
   The coverage file is itself a top-level reference_docs/ artifact (NOT cite/) — it's evidence
   of work, not an authoritative contract.
4. Security advisories and CVEs — GitHub Security Advisories (GHSA), CVE databases (NVD,
   cvedetails), Snyk, OSV / language vuln DBs (e.g. pkg.go.dev/vuln), vendor advisory pages.
   For each, capture the identifier, the AFFECTED VERSION RANGE, and the root-cause class.
5. Public discussion — GitHub Discussions, mailing lists, forums, community Discord/Slack
   archives, Stack Overflow, Reddit, Hacker News threads. Public discussion sources vary in
   invariant signal. Mailing lists, GitHub Discussions, and maintainer-authored Discord/Slack
   archives often contain authoritative-adjacent intent. Stack Overflow, Reddit, HN: usable for
   finding pain points and recurring confusion, but do NOT promote a Stack Overflow answer or
   Reddit comment to an invariant unless it's corroborated by official docs, code comments,
   tests, or a maintainer's own writing elsewhere.
6. Maintainer and team writing — blog posts, conference talks, design rationale, postmortems.
7. Test suites + conformance tests. Test files state invariants more concretely than prose.
   Look for: regression test files (tests/regression/), security tests (tests/security/),
   conformance tests (tests/conformance/), fuzzers (*_fuzz*.{c,go,py} or OSS-Fuzz integration),
   property-based tests (Hypothesis, QuickCheck, fast-check), and golden/fixture files. A test
   named test_must_never_allow_X IS an invariant.
8. Schema / contract files. Look for *.proto, openapi.{yaml,json}, JSON Schema files, GraphQL
   schemas, the project's own config.schema.json, ABI/IDL files. These are structural contracts
   the code is expected to conform to (and so are cite/-tier when found).
9. Release notes / changelogs. CHANGELOG.md, GitHub Releases pages, blog-post release
   announcements. Behavior-change entries ('starting in v2.4, tokens must be audience-bound')
   are statements of intent; deprecation notes mark INVARIANTS-NO-LONGER-IN-FORCE.
10. Threat models, security audits, pentest reports. Public security-audit reports (Cure53,
    NCC Group, Trail of Bits, etc.), STRIDE/PASTA models if published, SOC2 / ISO public claims.
    These are gold for invariants when available; rare but high-value.
11. Compatibility matrices + supported-version policies. 'Supported versions' tables, deprecation
    timelines, backwards-compatibility policies — they encode invariants about what state code
    must remain in.
12. Example apps / tutorials / cookbooks. Often encode intended usage patterns that the API docs
    leave implicit.
Internal / enterprise — use whatever connectors and MCP tools you have:
13. Internal requirements, PRDs, design docs, ADRs (Confluence, internal wikis, SharePoint).
14. Jira / issue-tracker tickets — especially security, incident, and "must not" tickets, and
    epics that describe intended behavior.
15. Team chat history (Slack / Teams / Discord) — decisions, gotchas, "never do X", retros.
16. Internal code review and PR discussion (Bitbucket, GitHub/GitLab Enterprise).
Only use sources you are authorized to access. Do NOT copy secrets, credentials, tokens, or
confidential customer data into the files — capture intent, not secrets.

WHAT TO EXTRACT (this is the point):
- Intended behavior and guarantees, stated in the project's own terms.
- INVARIANTS — "X must always" / "X must never" — with special attention to: tenant and data
  isolation, authentication and authorization, access-control evaluation, input validation,
  state and consistency, concurrency, error handling, and resource limits. Also capture intent
  for the other non-functional dimensions: performance/efficiency, reliability, usability,
  portability, maintainability, and integration/compatibility.
- Known-issue and advisory context — clearly labeled as advisory/known-issue, NOT as a confirmed
  current code defect.
- Contradictions and ambiguities. When sources conflict, do NOT smooth over the conflict. In the
  relevant theme file, add a ## Contradictions / Ambiguities section (between ## Context and the
  close section). Format each contradiction as: the two (or more) source quotes + URLs, a
  one-line statement of the conflict, and the SAFEST interpretation for an audit (the more
  restrictive invariant, typically). Marking contradictions explicitly prevents the audit from
  confidently keying off the wrong source.

OUTPUT FORMAT — one Markdown file per theme. Each file:
- Starts with "# <Title>".
- Then a "Sources:" line followed by a bulleted list of the REAL URLs you used. Never invent a
  source. For an internal system, cite the system and identifier (e.g. "Confluence: Auth Design
  v3", "Jira: SEC-1421", "Slack: #platform-security 2026-03-11").
- After the title and "Sources:" line, each file LEADS with the authority-aware extraction
  section (see below), then a "## Context" section providing synthesis and supporting examples
  (config, policy, schema, token) that justify the invariants above. If a paragraph in
  "## Context" doesn't trace to an invariant above it, cut it. Synthesis exists to support
  invariants, not the other way around.
Authority-aware close section — pick by file role:
- For AUTHORITATIVE theme files (architecture, security model, authorization model,
  multitenancy, API contract, consistency contract, performance/reliability expectations): title
  the section "## Invariants". Every invariant must be followed by a direct quote from a source
  with its URL — format: - '<verbatim quote>' (<URL>). An invariant with no traceable quote in
  the file is forbidden. Generic invariants ("Inputs must be validated") are forbidden unless
  tied to project-specific evidence ("Policy subjects must be matched within the request's
  domain; a role binding in domain A must not authorize access in domain B").
- For CVE / advisory files: title the section "## Known Failure Modes". Format as a table with
  columns: | CVE/advisory ID | Affected version range | Root-cause class | Fix version |
  Advisory URL |. Below the table, a short paragraph naming patterns that recur across the
  advisories. Do NOT title this "## Invariants" — historical failures are not active contracts.
- For issues & discussions files: title the section "## Candidate Audit Leads". Format as 3-10
  theme entries; each entry is a sub-heading, 2-3 representative issue links with one-line
  verbatim quotes, and a "What this tells us" line. Do NOT extract these as invariants — they
  belong in the topical authoritative file they apply to.
Density for security-relevant themes: aim for 5+ invariants in security/authz/tenancy/consistency
files. A file with fewer than 3 invariants probably means the theme isn't invariant-bearing —
merge it into another file or drop it. The CVE/issues role files have no minimum (the count is
whatever the source material has).
Suggested themes (adapt): overview & architecture; the authorization / security model;
multitenancy & isolation; the API / consistency contract; CVEs & advisories; outstanding issues
& discussions; performance & reliability expectations. One theme per file.

FILE PLACEMENT (tiering) — decide per file, and get this right:
- reference_docs/cite/  → ONLY authoritative specs/contracts the code must conform to: the
  official model/API spec, the security model, the project's own spec, the repo's proto/OpenAPI/
  config-schema contracts, cited external standards. These become byte-verified citation sources.
- reference_docs/ (top level) → EVERYTHING else, as Tier-4 context: the CVE/advisory file, the
  issues/discussions file, release notes, design/architecture notes, the source inventory.
- Do NOT put CVE/advisory or issue-tracker files in cite/. An advisory is not a contract; making
  it citable-as-authoritative is a known false-positive trap (the audit may treat "the CVE says
  affected" as ground truth). Advisory and issue files ALWAYS go top level.
- Decision rule (per source, not per theme): would a QPB audit be wrong to treat a sentence from
  this source as a definitive "the code must do this"?
  - If YES (the audit would be wrong) → top-level reference_docs/. Includes: CVE advisories (even
    maintainer-authored), issue-tracker content, partial-conformance RFCs, release notes
    describing failures, design docs describing proposed (not yet adopted) behavior, public
    discussion.
  - If NO (the audit would be right to treat as contract) → reference_docs/cite/. Includes: the
    official model/API spec, the project's own published security model, the repo's
    proto/OpenAPI/config-schema contracts, cited external standards the project claims FULL
    conformance with.
  Apply per-source. A single theme file in top-level reference_docs/ can quote a cite/-tier
  source — the synthesis-file's tier is independent of its quoted sources' tiers.
- Mixed-authority source split: if a single document contains BOTH normative contract language
  AND advisory/history/discussion, split it: extract the normative portion into a cite/-tier file
  (with a "Sources:" line citing only the normative section + line range), and keep the
  discursive portion in top-level reference_docs/.
- Partial RFC conformance: do NOT put an entire RFC in cite/ unless the project explicitly claims
  FULL conformance. Prefer a cite/ file that records the project's stated conformance profile
  (which sections adopted, which deviated, which optional features omitted) + a link to the RFC,
  rather than the RFC verbatim.
- Project-maintainer advisories that ARE the security model: if a maintainer-authored
  GHSA/advisory contains the canonical statement of the security boundary (not just a
  vulnerability report), extract the model statement into a cite/-tier file and keep the advisory
  itself top-level.

QUALITY BAR:
- Real sources only. Capture the version or date of what you read. Distinguish official from
  informal. Prefer primary sources.
- For any CVE, record its affected version range so the analysis can check whether the audited
  version is even in range. Do NOT restate a CVE as a current bug — record it as advisory
  context and let the code analysis confirm or refute it against the tree.
- Use enough sources to support the theme; prefer authority and relevance over count. The source
  summary table at the end must show breadth across source TYPES (official docs / repo / tests /
  issues / advisories / discussion / maintainer writing / internal): a file with sources from
  only one type is a smell. If a file has fewer than 3 strong sources, explicitly explain in the
  file's "## Context" whether that's because the theme is narrow, the project is underdocumented,
  or sources were inaccessible. Never invent or hallucinate a source to pad the list.

STEP 4 — HAND BACK WITH A SOURCE SUMMARY.
When the crawl is done, report:
  - A SOURCE SUMMARY TABLE covering EVERY source you drew from — not a sample. Columns:
    | Source (URL, or system + identifier) | Type (official docs / issue tracker / CVE /
    discussion / internal / …) | Pages/items reviewed (e.g. '12 docs pages, full ToC walked',
    '5 pages closed issues most-commented, ~120 skimmed, 18 quoted', '3 pages open
    security-labeled, ~40 skimmed, 6 quoted') | What you gathered from it, and which output file
    it fed |. The "Pages/items reviewed" column makes shallow work visible at a glance. This
    table is how the user audits your coverage.
  - The output files written (file → approximate size).
  - A one-paragraph summary of the top invariants you found (the things the code must never
    violate), so the user can sanity-check before the analysis runs.
Then tell the user they can follow up with additional resources for you to crawl — specific URLs,
internal systems, or connector / MCP sources (Jira / Confluence / Slack / Teams / Bitbucket, or
OpenClaw-style gateways) if any are available — and you'll extend the gathering. Remind them to
review and edit the files before pointing QPB at the project.
```

---

## What a good output file looks like

A gathered file leads with its title, real sources, and **invariants** (with quote-traceability), then provides supporting `## Context` below. The invariants section is the structural top, not the trailing afterthought.

```markdown
# Casbin Multi-Tenancy / Domain RBAC

Sources:
- https://casbin.apache.org/docs/rbac-with-domains  (official docs, accessed 2026-MM-DD)
- https://casbin.apache.org/docs/syntax-for-models  (official docs, accessed 2026-MM-DD)
- https://github.com/casbin/casbin/blob/master/rbac/default-role-manager/role_manager.go  (source, v2.x line)

## Invariants

- A grant in domain A must never take effect in domain B. The `domains` argument must be honored on every Enforce/EnforceEx call.
  - '`g`-type rules in `rbac_with_domains` model are domain-scoped; a binding in `domain1` cannot be evaluated as effective in `domain2`.' (https://casbin.apache.org/docs/rbac-with-domains#how-it-works)

- A revoked permission must not continue to grant access after the policy is reloaded — Enforce calls after `LoadPolicy` must reflect the revocation.
  - 'After `DeletePermissionForUser`, subsequent `Enforce` calls return false for the deleted permission, even with cached adapters, after `LoadPolicy`.' (https://casbin.apache.org/docs/management-api#deletepermissionforuser)

- Role assignments must be re-evaluated when policies change; cached enforcer state without `LoadPolicy` is stale.
  - 'Casbin caches role manager state; mutating policies via `AddPolicy`/`RemovePolicy` requires `LoadPolicy` for changes to propagate to in-flight `Enforce` calls.' (https://casbin.apache.org/docs/role-manager#cache-considerations)

## Context

Casbin's domain-RBAC model extends the basic RBAC model with a domain dimension: each (subject, object, action) tuple is evaluated within a specific domain (tenant). The model file declares `g = _, _, _` (three-argument g rule: user, role, domain), and policy rules carry the domain as their last column …

[synthesis here — kept terse; every paragraph traces to one of the invariants above]

## Contradictions / Ambiguities

The docs describe `LoadPolicy` as required after policy changes, but the v2.55 release notes claim some adapters now auto-reload. Until verified per-adapter, the SAFER interpretation for audit is the docs' stated rule: `LoadPolicy` is required.
```

This example shows the structural pattern (invariants up top with quote-traceability + URLs, `## Context` supporting, `## Contradictions` when present). It's the SHAPE the gathered file must take, not the specific content.

---

## Notes

- **Minimum input is a project name.** It confirms the project, explains the plan, and asks whether to add any sources (incl. MCP/enterprise connectors) — then waits for your reply before crawling. Once you answer, it runs a deep, exhaustive crawl by default (no depth choice needed) and also explores for relevant sources beyond the listed ones on its own.
- **It grounds itself in QPB first.** Step 0 fetches TOOLKIT.md from the repo and reads it, so the gathering is aligned with how QPB actually uses the docs. That fetch doubles as a capability check: a tool that can't retrieve the file can't do web research either, so it stops rather than gather the wrong thing.
- **Output defaults to `./reference_docs/`** (with `cite/` for authoritative specs) so it works in a fresh empty folder; move it into your project afterward, or run the prompt from inside the target repo. *(Maintainer note for QPB's own benchmark repos: the convention is `repos/docs_gathered/<repo>/`, which `setup_repos.sh` mirrors into `reference_docs/`.)*
- **It hands back a source summary table.** When the crawl finishes you get a table of every source it drew from and what it pulled from each, plus the invariants it found — then an invitation to send it more resources to crawl (specific URLs or connector/MCP sources like Jira/Confluence/Slack or OpenClaw-style gateways).
- **Splitting across tools is fine** — point them all at the same output folder; one can do public sources, another internal/enterprise ones.

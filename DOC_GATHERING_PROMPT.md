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
  - If you cannot fetch it, STOP and tell the user. Gathering documentation requires web search
    and page fetching; a tool that can't retrieve this file does not have the resources to do
    this task, so it should not proceed.
Once you've read it, confirm in one line: "Read QPB TOOLKIT.md — I'll gather intent and
invariants for a QPB audit." Then continue.

STEP 1 — IDENTIFY THE PROJECT, EXPLAIN THE PLAN, AND ASK ABOUT SOURCES — THEN STOP AND WAIT.
If the user hasn't named a project, ask for one (a name is enough). Web-search to find the
canonical repository, the official docs site, and the project's domain (what it does, what
security/correctness guarantees it's expected to make). Then, in ONE message to the user:
  - Show what you found: repo URL, one-line description, primary language, domain.
  - Explain what you're about to do: a DEEP, EXHAUSTIVE crawl across the SOURCES below (name the
    themes you'll produce), following additional relevant resources you discover along the way.
  - Ask TWO questions: (1) Is this the right project? (2) Are there any additional sources you
    should use — specific URLs, internal/enterprise documentation, or connector / MCP sources
    (Jira / Confluence / Slack / Teams / Bitbucket, OpenClaw-style gateways)?
Then STOP and WAIT for the user's reply. Do NOT begin gathering, fetching, or writing files until
they respond. Do NOT ask about depth — a deep crawl is the default; you are only confirming the
target and collecting any extra sources before you start.

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
4. Security advisories and CVEs — GitHub Security Advisories (GHSA), CVE databases (NVD,
   cvedetails), Snyk, OSV / language vuln DBs (e.g. pkg.go.dev/vuln), vendor advisory pages.
   For each, capture the identifier, the AFFECTED VERSION RANGE, and the root-cause class.
5. Public discussion — GitHub Discussions, mailing lists, forums, community Discord/Slack
   archives, Stack Overflow, Reddit, Hacker News threads.
6. Maintainer and team writing — blog posts, conference talks, design rationale, postmortems.
Internal / enterprise — use whatever connectors and MCP tools you have:
7. Internal requirements, PRDs, design docs, ADRs (Confluence, internal wikis, SharePoint).
8. Jira / issue-tracker tickets — especially security, incident, and "must not" tickets, and
   epics that describe intended behavior.
9. Team chat history (Slack / Teams / Discord) — decisions, gotchas, "never do X", retros.
10. Internal code review and PR discussion (Bitbucket, GitHub/GitLab Enterprise).
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

OUTPUT FORMAT — one Markdown file per theme. Each file:
- Starts with "# <Title>".
- Then a "Sources:" line followed by a bulleted list of the REAL URLs you used. Never invent a
  source. For an internal system, cite the system and identifier (e.g. "Confluence: Auth Design
  v3", "Jira: SEC-1421", "Slack: #platform-security 2026-03-11").
- Then a clear-prose synthesis, with fenced examples (config, policy, schema, token) where they
  clarify intent.
- Ends with a "## Security-Relevant Considerations" (or "## Invariants") section extracting the
  must / must-never statements. This closing section is the highest-value part of the file.
Suggested themes (adapt): overview & architecture; the authorization / security model;
multitenancy & isolation; the API / consistency contract; CVEs & advisories; outstanding issues
& discussions; performance & reliability expectations. One theme per file.

QUALITY BAR:
- Real sources only. Capture the version or date of what you read. Distinguish official from
  informal. Prefer primary sources.
- For any CVE, record its affected version range so the analysis can check whether the audited
  version is even in range. Do NOT restate a CVE as a current bug — record it as advisory
  context and let the code analysis confirm or refute it against the tree.
- Aim for roughly 6+ distinct sources per file; breadth across source types beats raw volume.

STEP 4 — HAND BACK WITH A SOURCE SUMMARY.
When the crawl is done, report:
  - A SOURCE SUMMARY TABLE covering EVERY source you drew from — not a sample. Columns:
    | Source (URL, or system + identifier) | Type (official docs / issue tracker / CVE /
    discussion / internal / …) | What you gathered from it, and which output file it fed |.
    This table is how the user audits your coverage.
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

A gathered file leads with its title and real sources, synthesizes the material, and ends by extracting the invariants. Abbreviated example:

```markdown
# Casbin Multi-Tenancy / Domain RBAC

Sources:
- https://casbin.apache.org/docs/rbac-with-domains
- https://casbin.apache.org/docs/syntax-for-models

## Overview
Casbin supports multi-tenant authorization through domain-based RBAC, where the same user can
have different roles in different domains (tenants)...

## Security-Relevant Considerations
- A grant in domain A must never take effect in domain B (the `domains` argument must be
  honored on every enforce call).
- A revoked permission must not continue to grant access after the policy is reloaded.
```

The closing invariants section is what the analysis checks the code against — so spend the most care there.

---

## Notes

- **Minimum input is a project name.** It confirms the project, explains the plan, and asks whether to add any sources (incl. MCP/enterprise connectors) — then waits for your reply before crawling. Once you answer, it runs a deep, exhaustive crawl by default (no depth choice needed) and also explores for relevant sources beyond the listed ones on its own.
- **It grounds itself in QPB first.** Step 0 fetches TOOLKIT.md from the repo and reads it, so the gathering is aligned with how QPB actually uses the docs. That fetch doubles as a capability check: a tool that can't retrieve the file can't do web research either, so it stops rather than gather the wrong thing.
- **Output defaults to `./reference_docs/`** (with `cite/` for authoritative specs) so it works in a fresh empty folder; move it into your project afterward, or run the prompt from inside the target repo. *(Maintainer note for QPB's own benchmark repos: the convention is `repos/docs_gathered/<repo>/`, which `setup_repos.sh` mirrors into `reference_docs/`.)*
- **It hands back a source summary table.** When the crawl finishes you get a table of every source it drew from and what it pulled from each, plus the invariants it found — then an invitation to send it more resources to crawl (specific URLs or connector/MCP sources like Jira/Confluence/Slack or OpenClaw-style gateways).
- **Splitting across tools is fine** — point them all at the same output folder; one can do public sources, another internal/enterprise ones.

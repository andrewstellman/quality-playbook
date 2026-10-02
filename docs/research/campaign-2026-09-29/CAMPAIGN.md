# Campaign 2026-09-29: five new targets, QPB vs standard review

Set up 29 September 2026. Five projects with strong documentation, chosen before any run: **httpx, cobra, click, zod, adonisjs-http-server**. QPB (v1.6.0, Claude Code with Opus) runs the full playbook plus all four iteration strategies on each. Every confirmed, unreported bug becomes a target. Then 10 fresh Opus reviewers per repository run the standard review prompt on a clean checkout of the same commit, with no documentation, no QPB, and no knowledge of the targets.

Design decision, recorded in advance: **the control gets the code only.** QPB is being compared as a whole system (documentation gathering included) against what a reviewer does today, not method-vs-method under equal evidence. The write-up must say so.

## Folders

| | Path | Contents |
|---|---|---|
| QPB targets | `repos/campaign-2026-09-29/<repo>/` | clone at the pin, `origin` removed, `reference_docs/` (below), QPB 1.6.0 in `.claude/skills/quality-playbook/`, adopter `.gitignore` block |
| Control checkouts | `repos/control-2026-09-29/<repo>/` | same pin, `origin` removed, nothing added. **Nobody writes here.** |
| This folder | `docs/research/campaign-2026-09-29/` | this file, then `PREDICTIONS.md`, `SCOPES.md`, `results/`, scoring |

`reference_docs/cite/` holds the project's own documentation, byte-identical copies out of the pinned tree (httpx `docs/`, cobra `site/content/`, click `docs/`, zod `packages/docs/content/`; adonisjs has none, so the HTTP chapters of the AdonisJS v6 docs at `adonisjs/v6-docs@0c513b5` stand in). `reference_docs/background/` is the `repos/docs_gathered/<repo>/` set, LLM summaries, marked not citable. `reference_docs/PROVENANCE.md` in each repo says exactly what is where.

## Pins (branch head on 2026-09-29; all five identical in target and control)

| Repo | Commit | Language | cite/ | background/ |
|---|---|---|---|---|
| httpx | `b5addb64f0161ff6bfe94c124ef76f6a1fba5254` | Python | 24 (+5 RFCs after step 2) | 20 |
| cobra | `adbc8813901bba65827259daa8e22ff94ec1f30e` | Go | 13 | 21 |
| click | `06b2a678741131fd577ce170e23e5ca0aeba0309` | Python | 38 | 10 |
| zod | `2bf7b0630d5378033e90bcee82cb32b0fe04628e` | TypeScript | 18 | 11 |
| adonisjs-http-server | `3bf3cde3200da459ec8977365cd3435924a258e3` | TypeScript | 13 | 15 |

zod ships its own `CLAUDE.md`, `AGENTS.md` and `.claude/skills/triage/`; they were left in place (they are part of the target) and QPB was installed alongside. zod's docs are `.mdx`; the ingest reads only `.txt`/`.md`/`.rst`, so they were renamed to `.md` (bytes unchanged) before the run.

## Wave 2 (staged 2026-09-29, launch when terminals free up)

Documentation was re-gathered for these rather than reusing `docs_gathered/` as-is: the existing sets are undated LLM summaries and some describe older versions (javalin's mentions 3.x–6.x; the pin is 7.2.4). The citable tier is the project's own docs at the pin plus the external specifications each project claims to implement, all copied byte-for-byte out of git checkouts. Details per repo in its `reference_docs/PROVENANCE.md`.

| Repo | Commit | Language | cite/ | What cite/ is |
|---|---|---|---|---|
| pydantic | `8fb804027c9bde3c96ec8bb14b7b22affdcb6ae4` | Python | 94 | `docs/` + JSON Schema 2020-12 core and validation specs |
| setuptools | `4e612f9e44ecfad130d0b2a27a2dce0740599b4b` | Python | 36 | `docs/` (current, not deprecated/) + 13 packaging PEPs (427, 440, 508, 517, 518, 566, 621, 625, 639, 643, 660, 685, 723) |
| compliance-trestle | `5ed923c4b67931b6d7b2a0f88e05dfa4b4aed8b0` | Python | 80 | `docs/` (not API stubs) + OSCAL v1.2.1 metaschemas (the version trestle pins) + OSCAL-Pages concept docs |
| addressable | `d298c9f551fa9748d16dbfb6273b70f60b3d61bc` | Ruby | 1 (+5 RFCs after fetch) | README + RFC 3986, 3987, 6570, 5891, 3490 |
| javalin | `20ba71b211b5efa91f5c10ccb467326b86a1e5dc` | Java/Kotlin | 3 | README + javalin.io 7.x docs + 6→7 migration guide |

Before launching wave 2, once on the Mac:

```zsh
cd ~/Documents/QPB/repos
rm -f campaign-2026-09-29/*/.git/index.lock
zsh campaign-2026-09-29/addressable/reference_docs/fetch_rfcs.sh
```

Toolchains: Python (pydantic, setuptools, trestle), Ruby + bundler (addressable), JDK 17+ and Maven (javalin). Launch command is the same as wave 1. **The prompt differs**: wave 2 runs QPB's own documentation-gathering protocol (`references/DOC_GATHERING_PROMPT.md`) first, on top of the staged `cite/` and `background/`, because the staging here could not crawl issue trackers, CVEs or discussions. So wave 2 targets get the full adopter path (project docs + specs + gathered community sources); wave 1 got project docs + specs only. Wave 2 prompt:

```
Before running the playbook, gather background documentation for this project into reference_docs/ following your documentation-gathering protocol. Keep everything already in reference_docs/cite/ and reference_docs/background/ and read reference_docs/PROVENANCE.md first so you don't duplicate it; add the sources it lacks, especially issue-tracker discussion of intended behaviour, and write the issue_tracker_coverage.md ledger. Then run the Quality Playbook: all six phases one after another without pausing for me between phases; accept the documentation classification as shown. When Phase 6 is done, run all four iteration strategies in order: gap, unfiltered, parity, adversarial. Do not modify any file outside quality/ and reference_docs/. Stop when the adversarial iteration has finished and tell me what is in quality/BUGS.md.
```

Deviation recorded for both waves: Claude Code loads `QPB/AGENTS.md` and `QPB/repos/AGENTS.md` from the parent directories because the targets sit inside the QPB clone. Those files are QPB's developer and benchmark notes, not answers about these targets, but an adopter would not have them in context.

## Before launching (on the Mac, once)

```zsh
cd ~/Documents/QPB/repos
rm -f campaign-2026-09-29/*/.git/index.lock          # left behind by the sandbox's git; harmless but must go
rm -rf .broken-clones-2026-09-29                       # failed first clone attempt, nothing in it
zsh campaign-2026-09-29/httpx/reference_docs/fetch_rfcs.sh   # RFC 9110/9112/9113/6265/3986 into httpx cite/
for r in httpx cobra click zod adonisjs-http-server; do
  echo "$r $(git -C campaign-2026-09-29/$r rev-parse --short HEAD) $(git -C control-2026-09-29/$r rev-parse --short HEAD) cite=$(ls campaign-2026-09-29/$r/reference_docs/cite | wc -l | tr -d ' ')"
done
```

Toolchains the runs will want: Python 3 (httpx, click), Go (cobra), Node + pnpm (zod uses pnpm; adonisjs uses npm). Missing ones only cost the TDD red/green step, not the review.

## Launch (one terminal per repo, all five in parallel)

```zsh
cd ~/Documents/QPB/repos/campaign-2026-09-29/httpx && claude --model opus --dangerously-skip-permissions
```

(same for `cobra`, `click`, `zod`, `adonisjs-http-server`). Then paste:

```
Run the Quality Playbook on this project. Run all six phases one after another without pausing for me between phases; accept the documentation classification as shown. When Phase 6 is done, run all four iteration strategies in order: gap, unfiltered, parity, adversarial. Do not modify any file outside quality/. Stop when the adversarial iteration has finished and tell me what is in quality/BUGS.md.
```

Expect 1–3 hours per repo for the baseline and a similar amount for the iterations. Zero confirmed bugs after Phase 3 with a "pass-process / fail-recall" message means the model was too weak, not that the code is clean; that should not happen with Opus.

## After the runs

1. **Confirm** (Cowork): each `BUGS.md` entry is reproduced in a sandbox, red/green, and searched upstream for an existing report. Only confirmed, unreported bugs are targets. Bugs with a security angle are set aside, as before.
2. **Pre-register** (`PREDICTIONS.md`, committed before any control run): per target, its visibility level (line / nearby / input / trace) and a predicted control hit rate; per repo, the review scope in `SCOPES.md`, chosen to cover the targets the way `control-2026-09-27/SCOPES.md` did.
3. **Control**: 10 fresh Opus sub-agents per repo, `control-2026-09-27/STANDARD_REVIEW_PROMPT.md` verbatim, checkout under `repos/control-2026-09-29/`, no network. Results to `results/opus-<repo>-runNN.md`.
4. **Score blind**: extractor and scorer as in `control-2026-09-27/oracle-test/`.
5. **The symmetric count**: what the control reported that QPB did not, at the same commit. This is the comparison the 2026-09-27 data could not make.

## Contribution-policy check (2026-09-29)

Checked each project's CONTRIBUTING / AGENTS / templates at the pin, the live default branch, repo labels, and an issue search for AI-rejection patterns.

| Repo | AI policy | Filing route |
|---|---|---|
| click | **Bans AI-generated contributions** (Pallets LLM/AI policy; "rejected AI" label in use). Confirmation stopped; nothing filed. | — |
| zod | None; repo ships AGENTS.md/CLAUDE.md for agents | direct PRs |
| adonisjs-http-server | None | issue with failing test; bug PRs accepted once confirmed |
| pydantic | Explicit: AI welcome if the author fully understands the code; incoherent AI descriptions or mass-submission get closed / banned | normal |
| setuptools | None; AGENTS.md points agents at jaraco's skeleton | PR with newsfragment |
| compliance-trestle | None | normal |
| addressable | None (no CONTRIBUTING) | normal |
| javalin | None | normal |
| httpx | None, but issues must start as a "Potential Issue" discussion | discussion first |
| cobra | None | normal |

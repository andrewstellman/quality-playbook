# Documentation Sources

This document lists the origin of every file in the `bus-tracker` docs_gathered collection.

## Primary sources

### 1. Project README

- **File:** `01_project_readme.md`
- **Source:** `clean/bus-tracker/README.md` at commit `e6c497f521e4c06e120364dd93a8b820d58113c1` (branch `main`, cloned 2026-04-21)
- **Upstream:** https://github.com/andrewstellman/bus-tracker/blob/main/README.md
- **Content:** Setup, configuration schema, CLI and web usage, "no dependencies" constraint, MIT license
- **Form:** Verbatim copy, no edits

### 2. Build chat transcript (preserved raw, not staged)

- **File:** `_raw/project_chat_history.md`
- **Source:** Cowork (Claude desktop app) chat export from 2026-04-10, session title "Build bus arrival prediction script"
- **Local path (author's Mac):** `Documents/AI-Driven Development/AI Chat History/Cowork-2026-04-10-Build bus arrival prediction script.md`
- **Notes:** The workspace contains four exported copies of this chat with suffixes `-1`, `-2`, `-3`, and no suffix. All four are byte-identical (md5 `cd0713d8e41eafd3be1f271bc6846c41`). The unsuffixed copy is treated as canonical and is the one reproduced here.
- **Form:** Verbatim copy, no edits. 121,722 bytes / ~4,556 lines.
- **Staging status:** Deliberately placed in `_raw/` so `stage_formal_docs.py` skips it (the staging loop filters non-files). Kept on disk for provenance and for anyone who wants to re-derive the topical docs by hand.

**Known quality caveat:** the exported chat is **~50% duplicated content**. Lines 1–1262 and lines 1263–2524 are byte-for-byte identical (verified 2026-04-21 by extracting both ranges with `sed` and running `diff`, which reported no differences). Unique post-duplicate content continues from ~line 2524 to the end at line 4556. The duplication appears to be an export artifact — Cowork wrote the same transcript body twice into the file, then appended the remainder of the session. This is part of why topical curation (below) materially reduces Phase-1 token cost.

### 3. Topical spec docs (derived)

Files `02_siri_api_endpoint.md` through `07_error_handling.md` were written on 2026-04-21 by distilling the build chat and cross-checking against `clean/bus-tracker/bus_tracker.py` at commit `e6c497f521e4c06e120364dd93a8b820d58113c1`. Each file lists its own `Source:` line at the top.

Derivation method:

1. Read `bus_tracker.py` end-to-end to pin down actual implementation.
2. Read the build chat (in `_raw/`) to recover design rationale, rejected alternatives, and edge cases explicitly discussed.
3. Write each topical doc as concrete behavior + design-intent claims + spec-auditor focus bullets + explicit "what's NOT in scope."
4. Flag known ambiguities (e.g. the semantic-vs-empty gap in `07_error_handling.md`) as documented limitations rather than inventing resolutions.

No content was invented; anything a topical doc asserts is either in the code or in the raw chat. If an auditor disagrees with a claim, `_raw/project_chat_history.md` is the tiebreaker, and the git history of `bus_tracker.py` is the ground truth for code behavior.

## Repository metadata

- **Project:** bus-tracker — real-time NYC bus arrival predictions using the MTA Bus Time SIRI API
- **Author:** Andrew Stellman
- **License:** MIT
- **GitHub URL:** https://github.com/andrewstellman/bus-tracker
- **Language:** Python 3 (standard library only)
- **Built:** 2026-04-10, single Cowork session
- **Captured into QPB:** 2026-04-21
- **Restructured:** 2026-04-21 (chat dump → topical docs + preserved raw)

## Protocol / external references mentioned (not copied)

These are referenced in the README and chat but not duplicated into this collection. QPB consumers may fetch them if needed:

- MTA Bus Time developer portal: https://bustime.mta.info/wiki/Developers/OneBusAwayRESTfulAPI
- SIRI (Service Interface for Real-time Information) spec: https://www.siri-cen.eu/
- MTA developer registration: https://register.developer.obanyc.com/

None of these were pulled in because they are large, external, and versioned independently of the project. The `bus-tracker` behavioral surface is fully captured by the README and topical docs; protocol-level auditing is out of scope for this target.

## Last updated

2026-04-21

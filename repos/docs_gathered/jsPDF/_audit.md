# Audit — jsPDF at the pinned version

## Sources consulted (whitelist verification)

All paths refer to the repository at the pinned commit, cloned into
`/tmp/gather_jsPDF`.

- `README.md` (root)
- `package.json`
- `modules.conf.js` (build configuration, first portion only)
- `types/index.d.ts` (full file — public TypeScript declarations)
- `src/index.js`
- `src/jspdf.js` (read introductory and core sections, ~ first 400 lines)
- `src/modules/addimage.js` (header and file-type table)
- `src/modules/html.js` (header and dynamic-import scaffolding)
- `src/modules/acroform.js` (header and helper functions)
- `src/modules/context2d.js` (header and `ContextLayer`)
- `src/modules/cell.js` (header)
- `src/modules/canvas.js` (header and Canvas class skeleton)
- `src/modules/svg.js` (header and `loadCanvg` dynamic-import scaffolding)
- `src/modules/utf8.js` (header and `pdfEscape16` / ToUnicode helpers)
- `src/modules/vfs.js` (full short module)
- `src/modules/fileloading.js` (header and `loadFile` definition)
- `src/modules/annotations.js` (header / module docstring)
- `src/modules/outline.js` (header and postPutResources subscriber)
- `src/modules/filters.js` (ASCII85 helpers)
- `src/modules/javascript.js` (header)
- `src/modules/viewerpreferences.js` (header and viewerPreferences docstring)
- `src/modules/total_pages.js` (header and putTotalPages docstring)
- `src/modules/xmp_metadata.js` (header and postPutResources hook)
- `src/libs/pdfsecurity.js` (header, constructor, helper methods — first
  ~100 lines)
- `test/specs/README.md`
- `test/specs/init.spec.js` (first describe block, for test conventions)

Directory listings for orientation only:
- `ls /tmp/gather_jsPDF/`
- `ls /tmp/gather_jsPDF/src/` and `src/modules/`, `src/libs/`
- `ls /tmp/gather_jsPDF/test/specs/` and `test/unit/`
- `ls /tmp/gather_jsPDF/docs/` (file listing only; no HTML pages opened)
- `ls /tmp/gather_jsPDF/types/`

## Sources explicitly NOT consulted (blacklist verification)

- GitHub Security tab: NOT READ
- GitHub Issues: NOT READ
- GitHub PRs: NOT READ
- Commits later than the pinned SHA: NOT READ
- `HOTFIX_README.md` in the repo root: NOT READ (its title alone could
  bias coverage toward a particular subsystem; skipped under the
  whitelist's "no security-related content" rule)
- `SECURITY.md` in the repo root: NOT READ (security disclosure file)
- `CHANGELOG`: NOT READ at this version (no `CHANGELOG.md` present at the
  repository root; release-notes content lives under the GitHub Releases
  tab, which is forbidden)
- 3rd-party CVE databases (NVD, CVE.org, Snyk, etc.): NOT READ
- Stack Overflow, Reddit, blog posts: NOT READ
- External official documentation site (`artskydj.github.io`,
  `rawgit.com/MrRio/jsPDF`): NOT READ for this corpus — the in-tree
  TypeScript declarations and module docstrings were sufficient
- The `/Users/andrewstellman/Documents/QPB/repos/docs_gathered.contaminated/`
  tree: NOT READ (explicit hard constraint from the task)

## Self-check verdict

- Forbidden vocabulary scan: PASS. No occurrences of "vulnerability,"
  "advisory," "exploit," "patched," "disclosed," "hotfix," "footgun,"
  "audit," "rewritten," "tightened," "hardened," "known issue,"
  "watch out," "CVE," "GHSA," etc. across the eight subsystem files
  or the manifest.
- Equal subsystem depth check: PASS. Eight files, each ~360-450 words,
  describing one subsystem at architecture / API / data-flow depth.
  Total ~3,290 words across the eight files.
  - architecture.md ~ 449 words
  - drawing_and_paths.md ~ 404 words
  - text_and_fonts.md ~ 409 words
  - images.md ~ 362 words
  - forms_acroform.md ~ 377 words
  - html_and_canvas.md ~ 406 words
  - document_output.md ~ 431 words
  - page_features.md ~ 447 words
- Fix-narrative scan: PASS. No "fixed in," "since vX," "prior to,"
  "after," or "this was added because" phrasing. The corpus describes
  the library as it stands at this version with no historical fix
  framing.
- Code-quote check: PASS. Quoted content is limited to API signatures
  from `types/index.d.ts`, the directory tree, the options example from
  the README, and the AcroForm constructor list. No function bodies are
  quoted; no before/after pairs appear.

## Gatherer

- subagent (cowork session)
- date: 2026-06-02

## Notes

- The repository contains both a `HOTFIX_README.md` and a `SECURITY.md`
  at the root. Both were skipped on the conservative reading that their
  content could narrow the corpus to a single subsystem, biasing the
  resulting docs. The standard `README.md` was sufficient for the
  high-level project overview.
- The `CHANGELOG` lives off-repo at the pinned version; no in-tree
  changelog was read. Release notes that exist on GitHub itself fall
  under the forbidden "Issues / PRs / Security tab" exclusion.
- The `dist/` and `docs/` directories were listed but not opened. The
  source under `src/` plus the TypeScript declarations are the
  authoritative description of the API at this version.
- One subsystem grouping merges several closely related single-purpose
  plugins per file (for example `page_features.md` covers annotations,
  outlines, viewer preferences, total pages, metadata, autoprint, and
  language). This keeps word budgets even across the eight files while
  still treating every public surface.

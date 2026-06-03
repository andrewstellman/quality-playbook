# Quality Playbook — pip + npm Distribution Channels Proposal

*Status: drafted 2026-05-22. **Placement confirmed 2026-05-22 — ships as part of `v1.5.7`** (channels are built on the `1.5.7` branch BEFORE the tag; the published pip/npm packages are v1.5.7, built from that tag). The filename keeps the `v1.6.x` slug for history; the work is v1.5.7.*
*Owner: Andrew Stellman*
*Depends on: v1.5.7's already-present `bin/qpb_validate.py` (Phase 0 install validator) and `bin/install_skill.py`'s `--source` flag — both verified present 2026-05-22 (`--source` at install_skill.py:1170 → resolves source_root, default `find_source_root`; `main()` at :1130; `qpb_validate.py` clone-hardcoded remediation at :290-293+`_FORCE`). Hard-blocks on nothing else.*

*Decisions confirmed 2026-05-22 (resolving §7):*
- *(Q1) Both channels ship — **npm is in**, alongside pip.*
- *(Q2/Q4) Headline verbs are the **ephemeral one-shot forms**: `uvx quality-playbook …` / `pipx run quality-playbook …` for Python, `npx quality-playbook init …` for Node. **Flag: `--ai-tool` on BOTH channels** (NOT Playwright's `--loop`) — one vocabulary across pip + npm + all docs + the Python installer; the npm shim forwards `--ai-tool` to `quality_playbook_cli` verbatim, with no JS translation layer (resolves Q2). The conventional `init` verb stays on npm. Persistent `pip install` still works but is not the documented lead.*
- *(Q3 + the `bin`-namespace concern) Package the Python code as **bundled data run via the console-script entry point — NOT importable top-level modules**. No generic `bin`/`quality_playbook` packages land in `site-packages`. This is the correct framing because the package is a one-shot **application / scaffolder** (à la `cookiecutter`), never `import`ed — `uvx`/`pipx run`/`npx` all treat it as a transient executable. The entry point invokes the installer with `--source` pointed at the packaged bundle data.*
- *(Q5) **Thin shim, single routing brain** — confirmed; no second (JS) routing implementation.*
- *(Q6) DockerHub out of scope.*

> **Where this sits in the arc.** The v1.5.x line shipped adopter distribution via `bin/install_skill.py` (a file-copy installer driven from a `git clone`). This proposal adds two *additional transport channels* — `pip install quality-playbook` and `npx quality-playbook` — on top of that same installer. It is **not** a new capability: the skill still installs as files into the target's tool-specific skill directory and still runs on Python 3.10+. The channels are a more discoverable, lower-friction front door than cloning the dev repo. The package **names are already reserved** (see §8); this proposal covers turning the `0.0.0` placeholders into functional `1.x` packages.

---

## 1. Motivation

The skill is distributed today by cloning `https://github.com/andrewstellman/quality-playbook` and running `python3 -m bin.install_skill --into <target> --ai-tool <tool>`. Two friction points:

- **Discovery.** A GitHub clone URL is not where developers look for installable tooling. `pip install <x>` / `npx <x>` are the universal "this is a real, installable tool" signals, and PyPI/npm are searchable surfaces.
- **Clone weight + setup.** Adopters pull a ~multi-hundred-file development repo (tests, `previous_runs/`, `docs/`, benchmark data) to obtain a curated ~51-file skill bundle (the current `_bundle_files()` count), then set `$QPB`, `cd`, and invoke a module with the right flags.

Both channels collapse that to a single command per ecosystem that lands the skill in the correct tool directory. The audience split is real: the tools that consume the skill (Claude Code, Copilot, Cursor, Continue, Codex) span Python- and Node-native ecosystems, so the two channels serve genuinely different adopter reflexes (`pip`/`uvx` vs `npx`).

### What these channels deliberately do NOT change

- **No new skill behavior.** The skill is the bundle of `SKILL.md` + `phase_prompts/` + `references/` + `agents/` + the `bin/` tooling. Channels change how that bundle arrives on the machine, nothing else.
- **No python-free path.** The skill *runs* on Python 3.10+ (the gate `quality_gate.py`, `validate_phase_artifacts.py`, `qpb_validate.py` all execute during a run). Optimizing install to avoid Python would defer an unavoidable requirement by one step. Both channels therefore treat Python 3.10+ as a hard prerequisite and **fail fast** when it is absent.
- **No second routing implementation.** The marker→directory routing (`AI_TOOL_MAP`, 8 distinct destinations across 9 keys; `github` aliases `copilot`) and the bundle manifest (`_bundle_files()`) stay single-source in `install_skill.py`. Channels are thin wrappers over it. (Reimplementing routing in JS would manufacture exactly the prose-to-code / execution divergence the v1.5.3 skill-as-code surface exists to detect.)

---

## 2. Core design principle — single routing brain, thin channel wrappers

```
                         ┌─────────────────────────────────────┐
   git clone  ─────────► │  bin/install_skill.py               │
                         │   • AI_TOOL_MAP (marker → dest)     │
   pip channel ────────► │   • _bundle_files() (the 51 files)  │ ──► copies bundle into
     (entry point)       │   • scaffolding + backup + smoke    │     <target>/<marker>/skills/
                         │   • event= structured output        │       quality-playbook/
   npm channel ────────► │   • --source <bundle-root> flag     │
     (JS bin → python3)   └─────────────────────────────────────┘
```

`install_skill.py` remains the single executor. Each channel's only job is: (a) get the bundle + the installer onto the machine, (b) locate them, (c) invoke the installer with the right flags, (d) pass its output through verbatim.

The `--source` flag is the load-bearing hook: it already overrides the copy-from root (default = parent of `bin/install_skill.py`). Both channels point `--source` at their packaged bundle location, so **no source-resolution refactor of the install logic is required** — only correct packaging so the Python `bin/` package imports resolve from the installed location (via `PYTHONPATH` or an installed console-script shim).

---

## 3. pip channel

**Package:** `quality-playbook` on PyPI (placeholder `0.0.0` reserved).

**Mechanism**

- Ship the full bundle as **package data** in the wheel — every member of `_bundle_files()` plus the `bin/` package itself, so `python3 -m bin.install_skill` (or the entry point) resolves its imports from `site-packages`.
- Add an **entry point**: `[project.scripts] quality-playbook = "bin.install_skill:main"` (or a dedicated thin `bin/qpb_cli.py` if `main()`'s arg surface shouldn't be the public CLI verbatim). Result: `quality-playbook --into <target> --ai-tool claude` works from anywhere, no clone, no `cd`.
- `source_root` resolves to the installed package data dir via `importlib.resources` / `__file__`; or the entry point passes `--source <resolved-pkg-root>` explicitly. Decide which (see §7 Q3).

**Adopter surface (illustrative)**

```bash
pip install quality-playbook
quality-playbook install --into ./my-repo --ai-tool claude
# or ephemeral, matching the npx mental model:
uvx quality-playbook install --into ./my-repo --ai-tool claude
pipx run quality-playbook install --into ./my-repo --ai-tool claude
```

**Open question:** headline verb — persistent `pip install` (familiar) vs ephemeral `uvx`/`pipx run` (matches npx; the package is a one-shot scaffolder nobody `import`s, so ephemeral is arguably more correct). Support both; pick which leads the README. See §7 Q4.

---

## 4. npm channel

**Package:** `quality-playbook` on npm (placeholder `0.0.0` reserved).

**Mechanism — thin JS shim around the bundled Python installer**

1. `package.json` `bin` → `bin/quality-playbook.js` (Node). `files` includes the JS shim **and** the bundled Python tree (the `_bundle_files()` members + `bin/` package), shipped as ordinary package files.
2. The shim:
   - **Detects Python ≥ 3.10**, trying `python3`, then `python`, then `py -3` (Windows launcher). On miss/too-old: exit non-zero with an actionable message ("Quality Playbook requires Python 3.10+; found X / not found — install from python.org or pyenv"), never a Node stack trace. (Mirrors the Windows-portability care already in `qpb_validate.py`.)
   - **Locates the bundle relative to the package** (`__dirname`), not the operator's cwd.
   - **Spawns** `python3 -m bin.install_skill --source <pkg-bundle-root> --into <cwd> --ai-tool <tool>` with `PYTHONPATH`/cwd set so the `bin/` package imports resolve.
   - **Passes stdio through verbatim** (`stdio: 'inherit'` or pipe-and-forward) and **propagates the child exit code**. This is non-negotiable for the Phase 0 contract: the `event=` lines and the `qpb_validate.py` run-nonce must reach the operator/agent unmodified for the verbatim-paste anti-fabrication check to hold. The shim must not summarize, reformat, or swallow them.
   - **Forwards `--ai-tool <tool>` verbatim** to the Python entry — no flag translation. (Decision 2026-05-22, resolving §7 Q2: `--ai-tool` on the npm surface too, NOT Playwright's `--loop` — one vocabulary across both channels and all docs, and the shim carries no alias map to keep in sync. The `init` verb stays as the npx-idiomatic scaffolder verb. Implemented: 089v built `--loop`; 089w flipped it to `--ai-tool`.)

**Adopter surface (illustrative)**

```bash
npx quality-playbook init --ai-tool=claude     # fetch + route into .claude/skills/quality-playbook/, one shot
npx quality-playbook init --ai-tool=cursor
npx quality-playbook init --ai-tool=copilot
```

**Note vs the Playwright precedent:** Playwright's `init-agents` is pure Node end-to-end, so it never crosses a Node→Python boundary. QPB's shim does. That bridge — and its Python-presence check — is the one extra moving part this channel carries, and the reason fail-fast detection is load-bearing.

---

## 5. Build + publish — generate the bundle, never hand-sync it

The Python files inside *both* distributables must be the canonical ones, copied from the source tree by a **publish-time build step**, not hand-maintained copies that silently lag the repo.

- A build script assembles the channel package by reading `_bundle_files()` as the single source of truth (same list the existing AGENTS.md cp-block drift-guard test pins).
- Add a **bundle-parity test**: the set of Python/skill files shipped in the wheel and in the npm tarball must equal `_bundle_files()`. This extends the existing `test_install_skill_bundle_completeness` discipline to the new channels — a third (and fourth) surface that must stay in lockstep, now enforced mechanically rather than by prose.
- **Version pinning:** the PyPI and npm package versions track the QPB release version, so `pip install quality-playbook==1.6.0` / `npx quality-playbook@1.6.0` ship the matching bundle.

---

## 6. Channel-aware validator remediation (the real coupling point)

`bin/qpb_validate.py` is the Phase 0 install validator. On a missing/partial install it emits a `remediation_suggestion` whose command is **hardcoded to the clone form** in two module-level constants:

```python
_RUN_INSTALLER_MAC = "python3 <clone>/bin/install_skill.py --into <target> --ai-tool <tool>"
_RUN_INSTALLER_WIN  = "python <clone>\\bin\\install_skill.py --into <target> --ai-tool <tool>"
```

Once pip/npm channels exist, the remediation the validator prints must match **how QPB was obtained**, or it will tell a `pip` adopter to go find a clone they don't have. Work required:

- Teach `qpb_validate.py` to **detect its invocation channel** (running from an installed wheel? invoked by the npm shim? a raw clone?) — e.g. an env var the wrappers set (`QPB_CHANNEL=pip|npm|clone`), or package-location introspection.
- Emit the **channel-correct remediation**: `quality-playbook install --into <target> --ai-tool <tool>` (pip) / `npx quality-playbook init --loop=<tool>` (npm) / the existing clone form (clone), each in its platform variants.
- Update the `verify_with` strings the same way.

This is the one place the channels are *not* invisible to existing code, and it must be handled or the validator's remediation degrades for the new audiences.

---

## 7. Open questions / decisions for roadmap orchestration

1. **Is npm worth it?** The npm channel's entire justification is "a meaningful slice of adopters live in Node-tool ecosystems and `npx` is their reflex." If telemetry/anecdote says the audience is overwhelmingly Python-side, npm is overhead. Confirm the audience before committing both channels. (pip is the lower-risk of the two and could ship alone first.)
2. **`--loop` vs `--ai-tool` on the npm surface. → RESOLVED 2026-05-22: `--ai-tool`** (consistency with the Python CLI + pip channel + all docs; `--loop` is Playwright-specific, not an industry standard, and would add a JS translation layer). No `--loop` alias. The npm shim forwards `--ai-tool` to `quality_playbook_cli` verbatim; the `init` verb stays. (089v built `--loop`; 089w flipped it.)
3. **`source_root` resolution for pip.** `importlib.resources` introspection inside `install_skill.py` vs the entry point passing `--source <resolved>` explicitly. The latter changes less existing code.
4. **pip headline verb.** `pip install` (persistent, familiar) vs `uvx`/`pipx run` (ephemeral, matches npx, arguably more correct for a one-shot scaffolder). Support both; choose the README lead.
5. **Single-shim vs declarative-manifest.** Recommended path is the thin shim (single Python routing brain). The heavier alternative — lift `_bundle_files()` + `AI_TOOL_MAP` into a checked-in JSON manifest both Python and a native JS installer read — only earns its cost if a genuinely Python-free Node install becomes a requirement, which §1 argues it is not. Default: **thin shim**.
6. **DockerHub** (`stellman/quality-playbook`): out of scope here. No name-race pressure (org-scoped namespace is reserved by account ownership). Revisit only if a containerized *runner* (sealed toolchain for the gate/validators) is ever wanted — that's a runtime decision, not a distribution one.

---

## 8. Names already reserved (cheap insurance, done 2026-05-22)

Minimal `0.0.0` placeholder packages were published to claim the names ahead of this work (first-publish-wins on both registries; only the uploading account can release future versions). Both point at the GitHub repo and describe themselves as placeholders.

- PyPI: https://pypi.org/project/quality-playbook/ (`0.0.0`)
- npm: https://www.npmjs.com/package/quality-playbook (`0.0.0`)

The `1.x` functional releases described above replace these.

---

## 9. ai_context / doc surfaces to update when this ships

This work touches adopter-facing and maintainer-facing docs; flag these for lockstep updates so the orchestration chat can fold them in:

- **`ai_context/TOOLKIT.md`** — adopter install instructions gain the `pip install` / `uvx` / `npx --loop` forms alongside the clone flow.
- **`AGENTS.md`** — the "Installing the skill" and "Mode A entry sequence / Phase 0" sections gain the channel-aware install + remediation commands; the AI-agent-driven install priority order (operator-told > self-identified > ASK) is unchanged but now has three command forms.
- **`ai_context/DEVELOPMENT_CONTEXT.md`** — maintainer notes: the publish-time build step, the bundle-parity test, version-pin discipline, and the `QPB_CHANNEL` detection contract.
- **README** — headline install verbs per §7 Q4.

---

## 10. Verification plan (for the implementing release)

- **Bundle-parity test** — wheel contents and npm tarball contents each equal `_bundle_files()` (extends `test_install_skill_bundle_completeness`).
- **Python-detection test** — npm shim exits non-zero with the remediation message when no `python3`/`python`/`py -3` ≥ 3.10 is on PATH; succeeds and forwards exit code when one is.
- **Passthrough test** — `event=` lines and the `qpb_validate.py` run-nonce emitted by the Python installer arrive byte-identical through the npm shim (the anti-fabrication contract).
- **Channel-remediation test** — `qpb_validate.py` emits the pip / npm / clone remediation form matching `QPB_CHANNEL`, in each platform variant.
- **End-to-end install test per channel** — `pip install` then `quality-playbook install --into <tmp> --ai-tool claude`, and `npx quality-playbook init --loop=claude`, each produce an install closure that `qpb_validate.py` reports `status=ok`.

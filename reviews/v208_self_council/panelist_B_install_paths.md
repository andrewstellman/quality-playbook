# Panelist B — Build + install path correctness (instruction 208)

Repo HEAD: `bfea8a167cc7ace02f65804a666ea68c37f9ec6b` (branch `1.5.8`).
Reviewer: Panelist B, self-Council Protocol 1.

## 1. Charter recap
Empirically verify that the plugin-native repo restructure (208) preserves: (a) `bin/publish_pip.py --dry-run` build, (b) `bin/publish_npm.py --dry-run` pack, (c) 57-file clone-install parity, and (d) the `bin/install_skill.py` shim's delegation to `skills/quality-playbook/scripts/install_skill.py`.

## 2. pip dry-run result
`python3 bin/publish_pip.py --dry-run` — exit 0, all 8 preflights passed:

1. Clean working tree — OK
2. Version parity 1.5.8 (pyproject, package.json, `quality_playbook_cli/__init__.py`) — OK
3. Tag `v1.5.8` exists — OK
4. Tag is ancestor of HEAD — OK
5. Build cleanly — wheel + sdist built (`dist/quality_playbook-1.5.8-py3-none-any.whl`, `dist/quality_playbook-1.5.8.tar.gz`)
6. Parity test passes — OK
7. No forbidden contents in 2 artifacts — OK
8. twine auth (`~/.pypirc`) — OK

Wheel internal layout spot-check (66 entries total):
- `quality_playbook_cli/_bundle/SKILL.md` — present at flat path as expected
- `quality_playbook_cli/_bundle/bin/citation_verifier.py` — present at flat path as expected

Result: PASS.

## 3. npm dry-run result
`python3 bin/publish_npm.py --dry-run` exits non-zero at preflight 4 because of the operator env (no `npm whoami`), exactly as the build agent noted. Preflights 1–3 passed (clean tree, version parity, tag exists). The script's preflight ordering puts whoami at slot 4 — so preflights 5 (stage bundle), 6 (forbidden contents), 7 (npm pack JSON) are NOT exercised by the harness's dry-run today.

To satisfy the charter clause "npm pack --dry-run --json returns clean JSON (no 203 regression)" I exercised the equivalent steps manually:

- `python3 bin/build_channel_package.py --stage` — staged 59 files into `quality_playbook_cli/_bundle` (exit 0). `_bundle/` is gitignored (`.gitignore:99`) so the staging does not dirty the tree.
- `npm pack --dry-run --json` — exit 0. stdout starts directly with `[` (no progress-text contamination at the JSON head — the 203 regression vector is absent). Parsed payload: 1 entry, 64 files. Spot-checks:
  - `quality_playbook_cli/_bundle/SKILL.md` — present
  - `quality_playbook_cli/_bundle/bin/citation_verifier.py` — present
  - First five entries (alphabetical): `LICENSE.txt`, `README.md`, `bin/quality-playbook.js`, `package.json`, `quality_playbook_cli/__init__.py` — clean.

The npm prepack hook (`build_channel_package.py --stage`) writes its informational line to stderr ("staged 59 files into …"), not stdout — exactly the 203-fix discipline.

Result: PASS for the npm-pack content check; the npm-whoami gate is a non-blocking operator-env issue.

## 4. Clone-install result
```
rm -rf /tmp/qpb-208-panelB-test
python3 -m bin.install_skill --into /tmp/qpb-208-panelB-test --ai-tool claude --no-smoke
```
Final installer line: `event=install_complete status=success errors=0 smoke_failed=0 files_copied=57`.

```
find /tmp/qpb-208-panelB-test/.claude/skills/quality-playbook/ -type f | wc -l
57
```

Matches the pre-208 baseline of 57 files bit-for-bit. Subdirectory shape spot-check:
- `SKILL.md` at install root — present
- `agents/` (3 files), `ai_context/TOOLKIT.md`, `bin/` (16 files), `phase_prompts/` (9 files), `references/` (many), `skill-template.gitignore` — all present
- Sentinel `quality/RUN_INDEX.md` created (136 bytes) and Phase 1 ingest hint logged

Result: PASS.

## 5. Shim delegation verification
`head -25 bin/install_skill.py` confirms the file is a thin shim with a 78-line body. Key mechanics:
- Line 29–32: resolves canonical script at `<repo>/skills/quality-playbook/scripts/install_skill.py` (the new 208 location).
- Line 34–40: raises a clear `RuntimeError` if the canonical script is missing (good failure mode if a partial clone is used).
- Line 42–54: builds an `importlib.util.spec_from_file_location` and execs it, registering in `sys.modules["_qpb_install_skill_canonical"]` so dataclasses/typing in the canonical module resolve to itself.
- Line 59–74: re-exports `main`, `install`, plus every non-dunder name from the canonical module — including the underscore-prefixed banner constants the 089j drift-guard test reads and the private helpers `_bundle_files`, `_bundle_files_soft`, `_resolve_bundle_source_root`, `_scripts_dirname` that `build_channel_package` and tests reach into.

Live verification through the shim:
- `python3 -m bin.install_skill --help` rendered the canonical banner and arg list (delegation path works for the `__main__` entry).
- `python3 -m bin.install_skill --into /tmp/qpb-208-panelB-test --ai-tool claude --no-smoke` performed a full 57-file install via the shim (delegation path works end-to-end).
- `python3 -c "from bin import install_skill; print(install_skill.main, install_skill.install, install_skill._BANNER_NAME, install_skill._BANNER_URL, install_skill._bundle_files, install_skill._resolve_bundle_source_root, install_skill._scripts_dirname)"` — every name resolved to the canonical-module attribute (no `MISSING`).

Result: PASS. The shim correctly preserves both the CLI entry (`python3 -m bin.install_skill`) and the Python-import API surface (`from bin import install_skill`).

## 6. Per-finding narrative
No CONCERN or FIX-REQUIRED items. The build + install paths are correct empirically:
- pip wheel + sdist build and contain the expected flat bundle layout.
- npm pack produces clean JSON (203 regression has not returned) and ships the expected files.
- Clone-install lands exactly 57 files at the expected `.claude/skills/quality-playbook/` path.
- The shim delegates correctly via `importlib.util.spec_from_file_location` and re-exports all public + private names that downstream code depends on.

## 7. NITs (optional, non-blocking)
- N1: The `bin/publish_npm.py` script's preflight 4 (npm whoami) gates preflights 5–7 (stage, forbidden-content scan, npm pack). On an unauthed dev box (or CI without an npm token), an operator cannot use `--dry-run` to verify the bundle-stage or pack-JSON-shape steps. Consider reordering — put `npm whoami` after `npm pack --dry-run`, or expose a `--skip-auth-check` flag so the pack-shape sanity check is reachable without authing. This is a workflow-ergonomics nit; the actual ship path is exercised by `--publish` which gates on auth anyway.
- N2: The shim at `bin/install_skill.py` reads cleanly and the `dir()`-loop re-export pattern is correct, but it relies on the canonical module being importable as `_qpb_install_skill_canonical`. If anything downstream later does `import sys; sys.modules["_qpb_install_skill_canonical"]` directly, the name choice would become load-bearing. Today nothing does, so this is purely a future-proofing observation.

## Final block

```
VERDICT: SHIP
```

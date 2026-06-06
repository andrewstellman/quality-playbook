# Panelist B — Cross-Platform Correctness Review (Instruction 202)

**Reviewer role:** Panelist B (cross-platform correctness ONLY). I am NOT the
orchestrator. My verdict ends in a `VERDICT:` block.

**Scope:** `bin/publish_pip.py`, `bin/publish_npm.py`,
`bin/submit_awesome_copilot.py` at HEAD `d2fd31f` on branch `1.5.8`.

## 1. Charter recap

Verify the three publish scripts work correctly on Windows + macOS + Linux —
no bash-isms, no Unix-only paths, list-form subprocess, and cross-platform
log-dir construction.

## 2. Cross-platform audit table

| File | Bash-specific syntax | Path operations | Subprocess form | Log-dir construction |
|---|---|---|---|---|
| `bin/publish_pip.py` | None. No `os.system`, no `shell=True`, no backticks, no shell pipes. | `pathlib.Path` end to end. Repo root via `Path(__file__).resolve().parent.parent` (L604). All joins via `/` operator. No string concat. | `subprocess.run` with list args, no shell. Single helper `_run()` (L128-146) enforces list-form + `encoding="utf-8"` + `errors="replace"`. `capture=False` correctly used for the interactive twine upload (L442, L464). `cwd` coerced via `str(cwd) if cwd else None` (L139) — accepts Path on all 3.7+, str everywhere. | `Path.home() / ".qpb" / "publish_logs"` (L110). `mkdir(parents=True, exist_ok=True)` (L115). UTF-8 explicit on log file open (L117). |
| `bin/publish_npm.py` | None. No shell-outs. `npm` resolved via `shutil.which("npm")` (L140) — correct Windows behavior via PATHEXT (handles `npm.cmd`/`npm.ps1`). | `pathlib.Path` end to end. Repo root via `Path(__file__).resolve().parent.parent` (L458). Bundle walk uses `bundle.rglob("*")` with explicit backslash-to-forward-slash normalization in the scanner (L286 + L255). | `subprocess.run` with list args via shared `_run()` (L118-135). `capture=False` for `npm publish` (L355). | Same as pip: `Path.home() / ".qpb" / "publish_logs"` (L100), UTF-8 open. |
| `bin/submit_awesome_copilot.py` | None. No subprocess at all — packet generation is pure Python file I/O. | `pathlib.Path` for everything. Dest `Path(args.dest).resolve()` (L513) or `repo_root / "dist" / "awesome_copilot_submission"` (L515). All `mkdir(parents=True, exist_ok=True)`. All `write_text(..., encoding="utf-8")`. | N/A — script does NOT call any subprocess. The `gh pr create` / `npm run skill:validate` invocations live in the generated `MANUAL_STEPS.md` operator playbook, not in code. | N/A — this script does not write a publish log; it writes the packet to `dist/awesome_copilot_submission/`. |

### Targeted grep results (matches the instruction's recommended commands)

`grep -n 'shell=True\|/tmp\|os\.fork\|fork('`:

- `bin/submit_awesome_copilot.py:45` — `/tmp/foo` in a docstring usage hint (example only).
- `bin/submit_awesome_copilot.py:487` — same `/tmp/foo` in the `usage_hint` banner string.

No `shell=True`. No `os.fork`. No `os.system`. No backticks. No `subprocess.Popen` direct.

`grep -nE 'subprocess\.(run|Popen|call)'`:

- `bin/publish_pip.py:137` — `subprocess.run(...)` inside `_run()` helper (list args, no shell).
- `bin/publish_npm.py:126` — `subprocess.run(...)` inside `_run()` helper (list args, no shell).

`grep -nE 'signal\.|SIGTERM|os\.geteuid|pwd\.|grp\.|termios|fcntl|posix'`: empty.
No POSIX-only APIs.

`grep -n 'Path.home\|expanduser\|os.path'`:

- `bin/publish_pip.py:110` — `Path.home() / ".qpb" / "publish_logs"` (cross-platform).
- `bin/publish_pip.py:405` — `Path.home() / ".pypirc"` (cross-platform).
- `bin/publish_npm.py:100` — `Path.home() / ".qpb" / "publish_logs"` (cross-platform).
- No `os.path.expanduser`, no `os.path.join`, no `os.path.sep`. The codebase
  uses `pathlib` uniformly.

### Test run

`python3 -m pytest bin/tests/test_publish_pip.py bin/tests/test_publish_npm.py bin/tests/test_submit_awesome_copilot.py` — **91 tests, 0 failures, 0 errors** on this Darwin host.

## 3. Per-script verdict

### `bin/publish_pip.py` — SHIP (with NIT)

- No `shell=True`. All subprocess invocations list-form via `_run()` helper.
- `pathlib` end to end; log dir is `Path.home() / ".qpb" / "publish_logs"`.
- `~/.pypirc` lookup uses `Path.home()` — correct.
- `python -m build` and `python -m twine` invoked via `sys.executable` (L284, L305, L331, L436, L459, L479) — correct, no PATH lookup needed for the interpreter; never invokes `python3` or `pip` as a bare name.
- Banner-only no-args path does NOT open the log file (intentional, L600-602).
- Sole concern: `str(dist / "*")` (L438, L460) passes a wildcard arg to twine.
  This works because twine internally calls `glob.glob` (`twine/commands/__init__.py:_find_dists`), and `glob.glob` on Windows accepts patterns with `\` separators. Verified by reading twine 6.1.0 source. **Cross-platform OK**.

### `bin/publish_npm.py` — SHIP

- `shutil.which("npm")` (L140) is the canonical cross-platform npm lookup.
  On Windows, `shutil.which` consults PATHEXT and finds `npm.cmd` / `npm.exe`
  / `npm.ps1` — this is exactly correct and avoids the well-known
  `subprocess.run(["npm", ...])` failure mode on Windows where the shim is
  not found without `shell=True`.
- All npm invocations use the resolved absolute path returned by `shutil.which`
  (passed as first arg, never via PATH lookup at exec time).
- Bundle walk uses `bundle.rglob("*")` + `relative_to(bundle)` + explicit
  `replace("\\", "/")` (L286) so the forbidden-fragment scanner does not
  miss matches on Windows where `rglob` yields backslash paths.
- npm pack JSON output parsing uses `json.loads` on `r.stdout` — npm's
  `--json` output is UTF-8 and platform-independent.
- Dry-run path correctly tolerates missing `npm` on a fresh CI box (L499-502, L520-526).

### `bin/submit_awesome_copilot.py` — SHIP

- No subprocess at all. Pure file generation.
- All paths via `pathlib`. All file I/O `encoding="utf-8"` explicit (L83, L122, L401, L405, L409, L432).
- Default dest is `repo_root / "dist" / "awesome_copilot_submission"` — cross-platform.
- The `gh pr create` invocation appears only as a generated string in
  `MANUAL_STEPS.md` (operator playbook) — not executed by the script.

## 4. Specific concerns with file:line citations

**None blocking.** No FIX-REQUIRED findings. The cross-platform discipline
is uniformly applied. Specifically:

- No `shell=True` anywhere.
- No `/tmp` in functional code (only in two docstring/banner examples — see NITs).
- No `os.fork`, `signal`, `pwd`, `grp`, `fcntl`, `termios`, or other POSIX-only modules imported.
- No hardcoded `/usr/`, `/etc/`, `/opt/`, `/home/`, `/root/`, or `C:\` paths.
- Subprocess `cwd=` always wrapped `str(cwd) if cwd else None` — works on Python 3.6+ on all platforms.
- `input()` calls are wrapped in `try/except EOFError` (L267-268, L520-521, L398-399 in npm) — handles piped-stdin CI gracefully on every OS.

## 5. NITs (not blocking)

1. `bin/submit_awesome_copilot.py:45` and `bin/submit_awesome_copilot.py:487`
   — both use `--dest /tmp/foo` as the example path in the docstring and the
   `usage_hint` printed by the no-args banner. On Windows `/tmp/foo` is not
   a meaningful path; a Windows operator pasting the example would be
   confused. Consider replacing with a platform-neutral example like
   `--dest ./out` or making the example dynamic. Cosmetic; the script
   itself accepts any path via `Path(args.dest).resolve()`.

2. Em-dash (U+2014) appears in several printed messages (e.g.
   `bin/publish_npm.py:214` `"npm is not on PATH — install Node.js..."`).
   On Windows Python 3.6+ `sys.stdout` is UTF-8 by default when attached to
   a console (PEP 528), so `print()` of these strings is safe. If an
   operator redirects stdout to a file on legacy Windows (`> log.txt`) the
   default cp1252 encoder could `UnicodeEncodeError`. The script's own log
   file is opened with `encoding="utf-8"` (good). NIT only — would only
   bite an operator running e.g. `publish_npm.py --dry-run > out.txt` on a
   pre-PEP-528 / `PYTHONIOENCODING=cp1252` Windows shell. Could be
   eliminated by replacing em-dashes with ASCII `--` in printed strings.

3. `bin/publish_pip.py:438` and `:460` pass `str(dist / "*")` to twine.
   This relies on twine's `glob.glob` fallback. It works (verified against
   twine 6.1.0) but a future twine release that tightens path handling
   could break it. A more defensive form would be to `glob` in Python and
   pass the explicit file paths:
   `[str(p) for p in sorted(dist.glob("*"))]`. Cosmetic robustness only;
   not a current bug.

4. `bin/publish_npm.py:285` walks `bundle.rglob("*")` and normalizes
   backslashes via `str(p.relative_to(bundle)).replace("\\", "/")`. This is
   correct, but a slightly cleaner form is `p.relative_to(bundle).as_posix()`
   which guarantees POSIX-style without manual escaping. No behavior change.

## 6. Final block

```
VERDICT: SHIP
```

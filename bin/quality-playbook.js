#!/usr/bin/env node
//
// Quality Playbook npm channel: Node shim over the bundled Python
// installer.
//
// This file does ONLY transport + translate; it is NEVER the install
// brain. The routing brain is `quality_playbook_cli.main()`, which
// loads `bin/install_skill.py` from the packaged `_bundle/`. The
// shim's responsibilities:
//
//   1. Detect a usable Python (>= 3.10). On miss / too-old: exit
//      non-zero with an actionable one-line message — NEVER a Node
//      stack trace.
//   2. Locate the packaged Python entry (`quality_playbook_cli/`
//      with its `_bundle/` data) relative to __dirname — NOT the
//      operator's cwd. The npm tarball ships this tree alongside
//      this shim; `npx` extracts it under a npm cache dir and runs
//      us from there.
//   3. Set `QPB_CHANNEL=npm` so `qpb_validate.py`'s remediation
//      emits the npx form. Set `PYTHONPATH` so `python3 -m
//      quality_playbook_cli` resolves to the packaged shim.
//   4. Translate the npx verb surface to the Python entry:
//
//          npx quality-playbook init --ai-tool=<tool>
//        → python3 -m quality_playbook_cli install \
//                  --into <cwd> --ai-tool <tool> [extras...]
//
//      The npm surface uses the same `--ai-tool` flag the pip
//      channel, install_skill, AGENTS.md, and README all use — one
//      vocabulary across both channels and all docs. The shim's
//      ONLY argv-level changes are mapping `init` -> `install` and
//      injecting `--into <cwd>` for install (the default target —
//      operators of npx-style scaffolders expect to "install
//      into here"). Everything else, including the entire
//      `--ai-tool` flag, is forwarded verbatim.
//   5. **Verbatim stdio passthrough + exit-code propagation.**
//      `stdio: 'inherit'` so every `event=...` line and the
//      `qpb_validate.py` run-nonce reach the operator/agent
//      byte-unmodified — the Phase-0 anti-fabrication contract.
//      Do NOT buffer-and-truncate, summarize, or reformat. The
//      shim is invisible to whatever is reading the child's
//      output.
//
// Out of scope here: validating the args themselves (the Python
// entry already does), maintaining a parallel routing brain,
// fabricating run output, or making policy decisions about which
// tool to install. The shim is the transport layer only.
//
// Test entry points (see `bin/tests/test_npm_channel_*.py`):
//   - Python detection: spawn the shim with a PATH that lacks
//     Python; assert exit-code != 0 and the message is the
//     remediation string, not a JS traceback.
//   - `--ai-tool` forwarding: instrument the shim to print its
//     computed spawn argv, then assert it equals the expected
//     Python argv (with --ai-tool passed through verbatim).
//   - Verbatim passthrough: assert child stdout/stderr arrive
//     byte-identical (including `event=` lines and run-nonce).
//   - npx e2e: invoke the shim against a temp target and run
//     `qpb_validate.py` on the result.

"use strict";

const { spawnSync } = require("child_process");
const path = require("path");
const fs = require("fs");

// ---------------------------------------------------------------------------
// Python detection
// ---------------------------------------------------------------------------

const PY_MIN_MAJOR = 3;
const PY_MIN_MINOR = 10;
const PY_REMEDIATION =
  "Quality Playbook requires Python " +
  PY_MIN_MAJOR +
  "." +
  PY_MIN_MINOR +
  "+. Install Python (https://www.python.org/downloads/ or pyenv) and re-run.";

// Candidate launchers, in priority order: posix `python3`, generic
// `python` (some distros), Windows `py -3` launcher.
const PY_CANDIDATES = [
  { cmd: "python3", args: [] },
  { cmd: "python", args: [] },
  { cmd: "py", args: ["-3"] },
];

/**
 * Attempt to invoke `<launcher>` and parse its version. Returns
 * `{ cmd, args, version: [major, minor] }` on success, or `null` if
 * the candidate is unavailable or too old.
 *
 * We use `--version` (which Python writes to stdout on 3.4+, stderr
 * on older — we read both) and parse a "Python X.Y" line.
 */
function probePython(candidate) {
  const result = spawnSync(
    candidate.cmd,
    [...candidate.args, "--version"],
    { encoding: "utf8" }
  );
  if (result.error || result.status !== 0) return null;
  const text = (result.stdout || "") + (result.stderr || "");
  const match = text.match(/Python\s+(\d+)\.(\d+)/);
  if (!match) return null;
  const major = parseInt(match[1], 10);
  const minor = parseInt(match[2], 10);
  if (
    major < PY_MIN_MAJOR ||
    (major === PY_MIN_MAJOR && minor < PY_MIN_MINOR)
  ) {
    return null;
  }
  return { cmd: candidate.cmd, args: candidate.args, version: [major, minor] };
}

function findPython() {
  for (const candidate of PY_CANDIDATES) {
    const probed = probePython(candidate);
    if (probed) return probed;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Verb translation
// ---------------------------------------------------------------------------

/**
 * Translate the npx-facing argv into the Python entry's argv.
 *
 * Public surface (npx):
 *     npx quality-playbook init --ai-tool=<tool> [extras...]
 *     npx quality-playbook init --ai-tool <tool> [extras...]
 *
 * Translated to:
 *     python -m quality_playbook_cli install \
 *            --into <cwd> --ai-tool <tool> [extras...]
 *
 * The npm surface uses the same `--ai-tool` flag the pip channel,
 * the Python installer, AGENTS.md, and README all use — the shim
 * simply forwards `--ai-tool` (both `=` and spaced forms) verbatim
 * to the Python entry. One vocabulary across both channels and all
 * docs, and no second alias map for the shim to keep in sync with
 * the Python side.
 *
 * The shim therefore has TWO concerns left for argv:
 *   1. Map the npx-idiomatic verb `init` -> the Python entry's
 *      `install`.
 *   2. For the install verb, inject `--into <cwd>` as the
 *      default target (the npx-style scaffolder convention).
 *
 * Everything else, including the entire `--ai-tool` flag, is
 * forwarded unchanged. If the operator omits `--ai-tool`, the
 * shim does NOT inject one — `install_skill.py` applies its
 * agent-self-identification resolution.
 *
 * Verbs:
 *   - `init` → `install` (npx-style scaffolder vocabulary).
 *   - `validate` → `validate` (pass-through).
 *   - bare (no verb) → `install` (default, mirrors the Python
 *     entry's default behavior).
 *   - any other verb → pass through unchanged (lets the Python
 *     entry surface its own "unknown verb" error).
 */
function translateArgv(argv, cwd) {
  const out = [];
  let i = 0;
  let verb = null;

  // First non-flag token is the npx verb.
  if (i < argv.length && !argv[i].startsWith("-")) {
    verb = argv[i];
    i += 1;
  }
  if (verb === "init" || verb === null) {
    out.push("install");
  } else {
    out.push(verb);
  }

  // For install: default target = cwd.
  if (out[0] === "install") {
    out.push("--into", cwd);
  }

  // Forward the remaining argv verbatim — including --ai-tool=
  // and --ai-tool <tool>. No semantic translation here.
  while (i < argv.length) {
    const tok = argv[i];
    out.push(tok);
    i += 1;
  }
  return out;
}

// ---------------------------------------------------------------------------
// Entry
// ---------------------------------------------------------------------------

function main() {
  const argv = process.argv.slice(2);

  // Self-test hook (private — used by `test_npm_channel_*.py` to
  // assert the translation step without actually spawning python).
  // Stable contract: a single line `SPAWN_ARGV: ["…", "…", …]`
  // followed by exit 0. The leading `__print_translated_argv` token
  // is consumed and not forwarded.
  if (argv[0] === "__print_translated_argv") {
    const py = { cmd: "python3", args: [] };
    const cwd = process.cwd();
    const pyArgs = [...py.args, "-m", "quality_playbook_cli"].concat(
      translateArgv(argv.slice(1), cwd)
    );
    process.stdout.write("SPAWN_ARGV: " + JSON.stringify(pyArgs) + "\n");
    process.exit(0);
  }

  const py = findPython();
  if (py === null) {
    process.stderr.write(PY_REMEDIATION + "\n");
    process.exit(1);
  }

  // Locate the packaged Python entry relative to this script. The
  // npm tarball layout:
  //   <pkg-root>/bin/quality-playbook.js   (this file)
  //   <pkg-root>/quality_playbook_cli/__init__.py
  //   <pkg-root>/quality_playbook_cli/_bundle/…
  // so the parent of __dirname is the package root we want on
  // PYTHONPATH (so `python -m quality_playbook_cli` resolves).
  const pkgRoot = path.resolve(__dirname, "..");
  const shimDir = path.join(pkgRoot, "quality_playbook_cli");
  if (!fs.existsSync(shimDir)) {
    process.stderr.write(
      "Quality Playbook npm shim: packaged quality_playbook_cli/ " +
        "missing at " + shimDir + " — the npm tarball is malformed.\n"
    );
    process.exit(2);
  }

  const cwd = process.cwd();
  const pyArgs = [...py.args, "-m", "quality_playbook_cli"].concat(
    translateArgv(argv, cwd)
  );

  // Child env: inherit + force QPB_CHANNEL=npm + prepend pkgRoot
  // to PYTHONPATH so `python -m quality_playbook_cli` resolves to
  // the packaged shim regardless of cwd.
  const env = Object.assign({}, process.env, {
    QPB_CHANNEL: "npm",
    PYTHONPATH: pkgRoot +
      (process.env.PYTHONPATH
        ? path.delimiter + process.env.PYTHONPATH
        : ""),
  });

  const result = spawnSync(py.cmd, pyArgs, {
    stdio: "inherit",  // verbatim passthrough — anti-fabrication contract
    env: env,
    cwd: cwd,
  });

  if (result.error) {
    // spawnSync failed before the child ran (e.g. ENOENT despite
    // probePython succeeding — rare but possible on a race). Emit
    // a one-line remediation, not a JS stack.
    process.stderr.write(
      "Quality Playbook npm shim: failed to invoke " + py.cmd +
        " (" + result.error.code + ").\n"
    );
    process.exit(3);
  }

  // Propagate the child's exit code unchanged. If the child was
  // killed by a signal (status === null on POSIX), surface that as
  // exit 128 + signal (the conventional shell mapping).
  if (result.status === null && result.signal) {
    // signo is a string like "SIGINT"; map common ones, else 1.
    const SIGMAP = { SIGINT: 130, SIGTERM: 143, SIGKILL: 137 };
    process.exit(SIGMAP[result.signal] || 1);
  }
  process.exit(result.status === null ? 1 : result.status);
}

main();

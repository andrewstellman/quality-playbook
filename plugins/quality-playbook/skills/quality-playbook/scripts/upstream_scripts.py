#!/usr/bin/env python3
"""upstream_scripts — write the operator-run scripts for upstream
submissions (v1.6.1 [R]).

Why: in the 2026-09 campaign every ``gh`` call that used the operator's
credentials lived in a script the operator ran, so the agent never had
to ask for approval call by call. Hand-writing those scripts is where
quoting and safety mistakes creep in. This generator writes them from a
spec, so the agent never composes them by hand. See
``references/upstream_submission.md``.

Usage:
  upstream_scripts <spec.json> <out_dir>
  upstream_scripts --compare-diff <patch-file> <forge-diff-file>

``<out_dir>`` is normally ``quality/upstream``. The generator writes:

  * ``<out_dir>/dup-search.sh`` (when any bug has ``dup_queries``):
    ``gh search issues`` and ``gh search prs`` per query, scoped to
    the upstream repo, output to ``<out_dir>/dup-search.out``;
  * ``<out_dir>/<slug>/submit.sh`` (when the bug has ``patch``): opens
    a DRAFT pull request, or for ``"kind": "issue"`` opens an issue
    and prints the next step;
  * ``<out_dir>/<slug>/verify.sh`` (same condition): reads the PR or
    issue back from the forge into files the agent checks.

The generated scripts never run ``gh pr ready``, ``gh pr merge``,
``gh pr comment`` or ``gh issue comment``. Every spec value is
shell-quoted with ``shlex.quote``. Relative ``patch`` / ``body_file``
paths resolve against the script's own directory at run time, so
``quality/upstream/`` can be copied to the operator's machine.

``--compare-diff`` compares the blob hashes in a ``git format-patch``
file with those in ``gh pr diff`` output (exit 0 = all match).

Spec (JSON object):
  upstream        "owner/repo" (required)
  expected_login  optional; submit.sh stops if ``gh`` is logged in as
                  someone else
  work_dir        optional clone directory; default
                  ``${QPB_WORK_DIR:-$HOME/src/pr-work}/<repo>``
  bugs            list of objects:
    slug          required, [A-Za-z0-9._-]+
    dup_queries   optional list of search strings
    kind          "pr" (default) or "issue"
    branch, patch, title, body_file   required for submit.sh
    base          optional target branch; default: upstream default
    test_command  optional shell command run in the clone before push
                  (``SKIP_TESTS=1`` skips it)
    post_create   optional list; supported:
                  {"rename": {"from": "<path>", "to": "<path with {pr_number}>"}}
                  (PR kind only: git mv, amend, push --force-with-lease)

Stdlib only, plus the bundled ``_purpose`` banner via the same 3-step
anchored fallback qpb_gate_witness.py uses.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


_NAME = "upstream_scripts"
_SUMMARY = (
    "Write the operator-run gh scripts (submit.sh, verify.sh, "
    "dup-search.sh) for upstream submissions from a JSON spec."
)
_USAGE = ("upstream_scripts <spec.json> <out_dir> | "
          "upstream_scripts --compare-diff <patch> <forge-diff>")

# v1.6.1 [R]: the gh verbs a generated script must never contain. The
# operator marks ready, merges and comments; a script never does.
FORBIDDEN_GH_VERBS = (
    "gh pr ready",
    "gh pr merge",
    "gh pr comment",
    "gh issue comment",
)

_SLUG_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_PR_NUMBER = "{pr_number}"


def _resolve_print_command_intro():
    """089x self-describing banner via the 3-step anchored fallback
    (package / flat / path-load) used by qpb_gate_witness.py."""
    try:
        from bin._purpose import (  # type: ignore[import]
            print_command_intro as _pci,
        )
        return _pci
    except ImportError:
        pass
    try:
        from _purpose import (  # type: ignore[no-redef, import]
            print_command_intro as _pci,
        )
        return _pci
    except ImportError:
        pass
    import importlib.util as _ilu
    _pp = Path(__file__).resolve().parent / "_purpose.py"
    _ps = _ilu.spec_from_file_location("_qpb_purpose_via_upstream", _pp)
    if _ps is None or _ps.loader is None:
        raise ImportError(f"upstream_scripts: cannot resolve _purpose at {_pp}")
    _mod = _ilu.module_from_spec(_ps)
    sys.modules[_ps.name] = _mod
    _ps.loader.exec_module(_mod)
    return _mod.print_command_intro


def _print_intro() -> None:
    _resolve_print_command_intro()(
        name=_NAME,
        summary=_SUMMARY,
        role=(
            "v1.6.1 [R] — Phase 7 'Prepare upstream submissions' "
            "(references/upstream_submission.md). The operator runs the "
            "generated scripts; the agent never does unless asked."
        ),
        usage_hint=_USAGE,
    )


# --- spec validation -------------------------------------------------------


class SpecError(ValueError):
    """The spec is missing a field or has an unsafe value."""


def _req_str(obj: Dict, key: str, where: str) -> str:
    val = obj.get(key)
    if not isinstance(val, str) or not val.strip():
        raise SpecError(f"{where}: '{key}' must be a non-empty string")
    return val


def validate_spec(spec: Dict) -> None:
    """Raise SpecError on a missing field or an unsafe value."""
    if not isinstance(spec, dict):
        raise SpecError("spec must be a JSON object")
    upstream = _req_str(spec, "upstream", "spec")
    if not _REPO_RE.match(upstream):
        raise SpecError(f"spec: upstream {upstream!r} is not owner/repo")
    bugs = spec.get("bugs")
    if not isinstance(bugs, list) or not bugs:
        raise SpecError("spec: 'bugs' must be a non-empty list")
    seen = set()
    for i, bug in enumerate(bugs):
        where = f"bugs[{i}]"
        if not isinstance(bug, dict):
            raise SpecError(f"{where}: must be an object")
        slug = _req_str(bug, "slug", where)
        if not _SLUG_RE.match(slug):
            raise SpecError(f"{where}: slug {slug!r} must match [A-Za-z0-9._-]+")
        if slug in seen:
            raise SpecError(f"{where}: duplicate slug {slug!r}")
        seen.add(slug)
        kind = bug.get("kind", "pr")
        if kind not in ("pr", "issue"):
            raise SpecError(f"{where}: kind must be 'pr' or 'issue'")
        queries = bug.get("dup_queries", [])
        if not isinstance(queries, list) or not all(
                isinstance(q, str) and q.strip() for q in queries):
            raise SpecError(f"{where}: dup_queries must be a list of strings")
        if "patch" not in bug:
            continue
        for key in ("branch", "patch", "title", "body_file"):
            _req_str(bug, key, where)
        for step in bug.get("post_create", []):
            ren = step.get("rename") if isinstance(step, dict) else None
            if not isinstance(ren, dict) or set(step) != {"rename"}:
                raise SpecError(
                    f"{where}: post_create supports only "
                    "{'rename': {'from': ..., 'to': ...}}")
            _req_str(ren, "from", where + ".post_create.rename")
            to = _req_str(ren, "to", where + ".post_create.rename")
            if to.count(_PR_NUMBER) != 1:
                raise SpecError(
                    f"{where}: post_create rename 'to' must contain "
                    f"{_PR_NUMBER} exactly once")
            if kind != "pr":
                raise SpecError(
                    f"{where}: post_create needs a PR number; "
                    "kind 'issue' has none")


# --- rendering -------------------------------------------------------------


_q = shlex.quote


def _path_expr(value: str) -> str:
    """Absolute paths are quoted as-is; relative ones resolve against
    the script's directory ($HERE) at run time."""
    if value.startswith("/"):
        return _q(value)
    return '"$HERE"/' + _q(value)


def _header(purpose: str,
            run_note: str = "It stops at the first failure.") -> List[str]:
    # The purpose comment can carry spec text: newlines would end the
    # comment, so flatten them.
    purpose = " ".join(purpose.split())
    return [
        "#!/usr/bin/env bash",
        f"# {purpose}",
        "# Generated by upstream_scripts.py (QPB v1.6.1 [R]); regenerate "
        "rather than edit.",
        f"# The operator runs this. {run_note}",
        "set -euo pipefail",
        'HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"',
    ]


def _login_lines(expected_login: Optional[str]) -> List[str]:
    lines = [
        'gh auth status >/dev/null 2>&1 || { echo "gh is not logged in: '
        'run gh auth login first"; exit 1; }',
        "ME=$(gh api user -q .login)",
    ]
    if expected_login:
        lines += [
            f"EXPECTED_LOGIN={_q(expected_login)}",
            '[[ "$ME" == "$EXPECTED_LOGIN" ]] || { echo "gh is logged in '
            'as $ME, expected $EXPECTED_LOGIN"; exit 1; }',
        ]
    return lines


def render_submit(spec: Dict, bug: Dict) -> str:
    """The per-bug submit.sh text."""
    upstream = spec["upstream"]
    repo_name = upstream.split("/", 1)[1]
    kind = bug.get("kind", "pr")
    action = "a DRAFT pull request" if kind == "pr" else "an issue"
    lines = _header(f"Opens {action} on {upstream} for {bug['slug']}.")
    lines += [
        f"UPSTREAM={_q(upstream)}",
        f"BRANCH={_q(bug['branch'])}",
        f"PATCH={_path_expr(bug['patch'])}",
        f"BODY={_path_expr(bug['body_file'])}",
        f"TITLE={_q(bug['title'])}",
        f"BASE_OVERRIDE={_q(bug.get('base', ''))}",
        f"TEST_COMMAND={_q(bug.get('test_command', ''))}",
    ]
    if spec.get("work_dir"):
        lines.append(f"WORK={_q(spec['work_dir'])}")
    else:
        lines.append('WORK="${QPB_WORK_DIR:-$HOME/src/pr-work}"/'
                     + _q(repo_name))
    lines += [
        '[[ -f "$PATCH" ]] || { echo "patch not found: $PATCH"; exit 1; }',
        '[[ -f "$BODY" ]] || { echo "body file not found: $BODY"; exit 1; }',
    ]
    lines += _login_lines(spec.get("expected_login"))
    lines += [
        'DEFAULT=$(gh repo view "$UPSTREAM" --json defaultBranchRef '
        '-q .defaultBranchRef.name)',
        'BASE="${BASE_OVERRIDE:-$DEFAULT}"',
        'echo "== fork $UPSTREAM (no-op if your fork exists)"',
        'gh repo fork "$UPSTREAM" --clone=false 2>&1 | tail -1',
        'if [[ ! -d "$WORK/.git" ]]; then',
        '  mkdir -p "$(dirname "$WORK")"',
        '  gh repo clone "$ME/${UPSTREAM#*/}" "$WORK" -- --filter=blob:none',
        "fi",
        'git -C "$WORK" remote get-url upstream >/dev/null 2>&1 || '
        'git -C "$WORK" remote add upstream "https://github.com/$UPSTREAM.git"',
        'cd "$WORK"',
        'git fetch upstream "$BASE"',
        'git switch -q --detach "upstream/$BASE"',
        'if git show-ref --verify --quiet "refs/heads/$BRANCH"; then',
        '  echo "branch $BRANCH exists in $WORK; delete it first: '
        'git -C $WORK branch -D $BRANCH"',
        "  exit 1",
        "fi",
        'git switch -c "$BRANCH"',
        'git am "$PATCH" || { echo "git am failed: the patch does not apply '
        'to upstream/$BASE. Run git -C $WORK am --abort and tell the '
        'agent."; exit 1; }',
        "git log --oneline -1",
        'if [[ "${SKIP_TESTS:-0}" != 1 && -n "$TEST_COMMAND" ]]; then',
        '  echo "== local check: $TEST_COMMAND (SKIP_TESTS=1 skips it)"',
        '  bash -c "$TEST_COMMAND"',
        "fi",
        'echo "== push to your fork"',
        'git push -u origin "$BRANCH"',
    ]
    if kind == "pr":
        lines += [
            'URL=$(gh pr create --draft --repo "$UPSTREAM" --head '
            '"$ME:$BRANCH" --base "$BASE" --title "$TITLE" '
            '--body-file "$BODY")',
            'echo "$URL"',
        ]
        for step in bug.get("post_create", []):
            ren = step["rename"]
            pre, post = ren["to"].split(_PR_NUMBER)
            lines += [
                "# post-create: rename to the PR number, amend, force-push",
                'NUM=$(gh pr view "$URL" --json number -q .number)',
                f'NEW_PATH={_q(pre)}"$NUM"{_q(post)}',
                'echo "== rename to $NEW_PATH"',
                f'git mv -- {_q(ren["from"])} "$NEW_PATH"',
                "git commit -q --amend --no-edit",
                "git push --force-with-lease",
            ]
        lines += [
            'gh pr view "$URL" --json number,url,isDraft,title',
            'echo "Draft PR opened: $URL"',
            'echo "Paste this output to the agent. Marking the PR ready is '
            'yours to do, in the web UI."',
        ]
    else:
        lines += [
            'COMPARE="https://github.com/$UPSTREAM/compare/$BASE...'
            '$ME:${UPSTREAM#*/}:$BRANCH"',
            'BODY_TEXT="$(cat "$BODY")"',
            'BODY_TEXT="${BODY_TEXT//__COMPARE__/$COMPARE}"',
            'ISSUE_BODY="$(mktemp)"',
            "printf '%s\\n' \"$BODY_TEXT\" > \"$ISSUE_BODY\"",
            'URL=$(gh issue create --repo "$UPSTREAM" --title "$TITLE" '
            '--body-file "$ISSUE_BODY")',
            'rm -f "$ISSUE_BODY"',
            'echo "$URL"',
            'gh issue view "$URL" --json number,url,title,state',
            'echo "Issue opened: $URL. The fix is on your fork: $COMPARE"',
            'echo "Next step: wait for a maintainer to answer on the issue, '
            'then paste the answer to the agent. It prepares the pull '
            'request that references the issue."',
        ]
    return "\n".join(lines) + "\n"


def render_verify(spec: Dict, bug: Dict) -> str:
    """The per-bug verify.sh text: read-only gh calls into files."""
    kind = bug.get("kind", "pr")
    noun = "PR" if kind == "pr" else "issue"
    lines = _header(f"Reads the submitted {noun} for {bug['slug']} back "
                    f"from {spec['upstream']} (read-only).")
    lines += [
        f"UPSTREAM={_q(spec['upstream'])}",
        f'REF="${{1:?usage: bash verify.sh <{noun} URL or number>}}"',
    ]
    if kind == "pr":
        lines += [
            'gh pr view "$REF" --repo "$UPSTREAM" --json '
            'number,url,title,body,isDraft,state,headRefName,headRefOid '
            '> "$HERE/verify.pr.json"',
            'gh pr diff "$REF" --repo "$UPSTREAM" > "$HERE/verify.pr.diff"',
            'echo "Wrote $HERE/verify.pr.json and $HERE/verify.pr.diff"',
        ]
    else:
        lines += [
            'gh issue view "$REF" --repo "$UPSTREAM" --json '
            'number,url,title,body,state > "$HERE/verify.issue.json"',
            'echo "Wrote $HERE/verify.issue.json"',
        ]
    lines.append('echo "Tell the agent; it checks these files against '
                 'REVIEW.md and the patch."')
    return "\n".join(lines) + "\n"


def render_dup_search(spec: Dict) -> Optional[str]:
    """The per-run dup-search.sh text, or None when no bug has queries.
    A failed search does not stop the script: it is written into the
    .out file as FAILED so the agent sees it."""
    bugs = [b for b in spec["bugs"] if b.get("dup_queries")]
    if not bugs:
        return None
    lines = _header(f"Duplicate search on {spec['upstream']}: issues and "
                    "PRs, all states.",
                    "A failed search is logged as FAILED and the rest run.")
    lines += [
        f"UPSTREAM={_q(spec['upstream'])}",
        'OUT="$HERE/dup-search.out"',
        "search() {",
        '  local what="$1" query="$2" rc=0',
        '  echo "### gh search $what --repo $UPSTREAM: $query"',
        '  gh search "$what" --repo "$UPSTREAM" --limit 30 -- "$query" || rc=$?',
        '  if [[ $rc -ne 0 ]]; then echo "FAILED: gh search $what (exit $rc)"; fi',
        "  echo",
        "}",
        "{",
        '  echo "# dup-search for $UPSTREAM, $(date -u +%Y-%m-%dT%H:%M:%SZ)"',
    ]
    for bug in bugs:
        lines.append(f"  echo; echo {_q('## ' + bug['slug'])}")
        for query in bug["dup_queries"]:
            lines.append(f"  search issues {_q(query)}")
            lines.append(f"  search prs {_q(query)}")
    lines += [
        '} > "$OUT" 2>&1',
        'echo "Wrote $OUT. Give it to the agent (paste or upload)."',
    ]
    return "\n".join(lines) + "\n"


def generate(spec: Dict, out_dir: Path) -> List[Path]:
    """Validate ``spec`` and write the scripts under ``out_dir``.
    Returns the written paths."""
    validate_spec(spec)
    out_dir = Path(out_dir)
    written: List[Path] = []

    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)
        written.append(path)

    dup = render_dup_search(spec)
    if dup is not None:
        _write(out_dir / "dup-search.sh", dup)
    for bug in spec["bugs"]:
        if "patch" not in bug:
            continue
        _write(out_dir / bug["slug"] / "submit.sh", render_submit(spec, bug))
        _write(out_dir / bug["slug"] / "verify.sh", render_verify(spec, bug))
    return written


# --- blob-hash comparison (Record step) ------------------------------------


_DIFF_GIT_RE = re.compile(r"^diff --git a/(\S+) b/(\S+)")
_INDEX_RE = re.compile(r"^index ([0-9a-f]+)\.\.([0-9a-f]+)")


def blob_hashes(diff_text: str) -> Dict[str, Tuple[str, str]]:
    """Map each file in a git diff to its (old, new) blob hash."""
    out: Dict[str, Tuple[str, str]] = {}
    current = None
    for line in diff_text.splitlines():
        m = _DIFF_GIT_RE.match(line)
        if m:
            current = m.group(2)
            continue
        m = _INDEX_RE.match(line)
        if m and current is not None:
            out[current] = (m.group(1), m.group(2))
            current = None
    return out


def _same_hash(a: str, b: str) -> bool:
    n = min(len(a), len(b))
    return n >= 7 and a[:n] == b[:n]


def compare_blob_hashes(patch_text: str, forge_diff_text: str) -> List[str]:
    """Return mismatch descriptions; empty means every file's blob
    hashes match (abbreviated hashes compare by common prefix)."""
    want, got = blob_hashes(patch_text), blob_hashes(forge_diff_text)
    problems = []
    if not want:
        problems.append("the patch has no 'index' lines to compare")
    for path in sorted(set(want) | set(got)):
        if path not in got:
            problems.append(f"{path}: in the patch, not in the forge diff")
        elif path not in want:
            problems.append(f"{path}: in the forge diff, not in the patch")
        elif not all(_same_hash(a, b) for a, b in zip(want[path], got[path])):
            problems.append(f"{path}: patch {want[path][0]}..{want[path][1]} "
                            f"vs forge {got[path][0]}..{got[path][1]}")
    return problems


# --- CLI -------------------------------------------------------------------


def main(argv: "list[str] | None" = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args in (["--help"], ["-h"]):
        _print_intro()
        return 0
    if args[0] == "--compare-diff":
        if len(args) != 3:
            print(f"Usage: {_USAGE}", file=sys.stderr)
            return 2
        problems = compare_blob_hashes(
            Path(args[1]).read_text(encoding="utf-8", errors="replace"),
            Path(args[2]).read_text(encoding="utf-8", errors="replace"))
        for p in problems:
            print(f"MISMATCH: {p}")
        if problems:
            return 1
        print("MATCH: every file's blob hashes in the forge diff equal "
              "the patch's.")
        return 0
    if len(args) != 2:
        print(f"Usage: {_USAGE}", file=sys.stderr)
        return 2
    try:
        spec = json.loads(Path(args[0]).read_text(encoding="utf-8"))
        written = generate(spec, Path(args[1]))
    except (OSError, json.JSONDecodeError, SpecError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""v1.6.1 [R] — "Prepare upstream submissions" (Phase 7 path 5).

Why: the 2026-09 campaign took QPB findings upstream by hand, with
hand-written ``gh`` scripts the operator ran. v1.6.1 moves the process
into the skill (references/upstream_submission.md) and generates the
scripts (scripts/upstream_scripts.py) so the agent never composes them.
These tests pin:

  * golden properties of every generated script: ``set -euo pipefail``
    is the first logic line, ``bash -n`` passes, no forbidden ``gh``
    verb (ready / merge / pr comment / issue comment) appears, PRs open
    with ``--draft``, a hostile title is quoted safely, the issue-first
    variant never runs ``gh pr create``, the post-create rename appears
    only when configured, dup-search writes ``dup-search.out``;
  * end-to-end runs against a stub ``gh`` and local git remotes: the
    title reaches ``gh pr create`` byte-for-byte, the patch lands on the
    fork, the newsfragment is renamed to the PR number, a ``git am``
    conflict stops with the abort message;
  * the blob-hash comparison used by the Record step;
  * the skill text: phase7_guide.md lists the path, upstream_submission.md
    carries the guardrails and the one-bug-at-a-time rule, SKILL.md
    points at it, ``--check-skill-references`` passes, and the bundle
    ships both new files.

Mutation-bite evidence (executed during v1.6.1 [R] development):
  M1: in render_submit, add the line ``gh pr ready "$URL"`` after the
      ``echo "$URL"`` line → test_no_forbidden_gh_verbs FAILS. Restored
      → PASS.
  M2: in render_submit, replace ``f"TITLE={_q(bug['title'])}"`` with
      ``f'TITLE="{bug["title"]}"'`` → test_hostile_title_quoted_safely
      and test_e2e_pr_submit FAIL. Restored → PASS.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SKILL_DIR = _REPO / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
_GEN = _SKILL_DIR / "scripts" / "upstream_scripts.py"
_GATE = _SKILL_DIR / "scripts" / "quality_gate.py"
_SKILL_MD = _REPO / "SKILL.md"
_PHASE7 = _REPO / "references" / "phase7_guide.md"
_UPSTREAM_MD = _REPO / "references" / "upstream_submission.md"

_HOSTILE_TITLE = 'fix: don\'t "drop" `x` when $HOME is set $(touch PWNED)'


def _load_gen():
    sys.path.insert(0, str(_GEN.parent))
    try:
        import upstream_scripts as gen  # type: ignore[import]
    finally:
        sys.path.pop(0)
    return gen


def _spec(**bug_overrides):
    bug = {
        "slug": "widget-fix",
        "branch": "fix-it",
        "patch": "0001-fix.patch",
        "title": _HOSTILE_TITLE,
        "body_file": "PR.md",
        "test_command": "test -f README && echo tests-ok",
        "dup_queries": ["can't \"drop\" `x` $Y", "second query"],
    }
    bug.update(bug_overrides)
    return {"upstream": "acme/widget", "expected_login": "op", "bugs": [bug]}


def _logic_lines(text):
    return [l for l in text.splitlines() if l.strip() and not l.startswith("#")]


def _have(tool):
    return shutil.which(tool) is not None


class GeneratedScriptGoldenTests(unittest.TestCase):

    def setUp(self):
        self.gen = _load_gen()
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def _generate(self, spec):
        return self.gen.generate(spec, self.tmp / "upstream")

    def _all_variants(self):
        """Every script the generator can produce: PR with and without
        post_create, issue-first, dup-search."""
        out = []
        for i, overrides in enumerate((
            {},
            {"post_create": [{"rename": {"from": "news/+fix-it.bugfix.rst",
                                         "to": "news/{pr_number}.bugfix.rst"}}]},
            {"kind": "issue", "body_file": "ISSUE.md"},
        )):
            out += self.gen.generate(_spec(**overrides), self.tmp / f"v{i}")
        return out

    def test_writes_expected_files(self):
        paths = {p.relative_to(self.tmp / "upstream").as_posix()
                 for p in self._generate(_spec())}
        self.assertEqual(paths, {"dup-search.sh", "widget-fix/submit.sh",
                                 "widget-fix/verify.sh"})

    def test_set_euo_pipefail_is_first_logic_line(self):
        for path in self._all_variants():
            with self.subTest(script=str(path)):
                text = path.read_text()
                self.assertTrue(text.startswith("#!/usr/bin/env bash\n"))
                self.assertEqual(_logic_lines(text)[0], "set -euo pipefail")

    @unittest.skipUnless(_have("bash"), "bash not installed")
    def test_bash_n_passes_on_every_script(self):
        for path in self._all_variants():
            with self.subTest(script=str(path)):
                r = subprocess.run(["bash", "-n", str(path)],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_no_forbidden_gh_verbs(self):
        self.assertEqual(self.gen.FORBIDDEN_GH_VERBS,
                         ("gh pr ready", "gh pr merge", "gh pr comment",
                          "gh issue comment"))
        for path in self._all_variants():
            text = path.read_text()
            for verb in self.gen.FORBIDDEN_GH_VERBS:
                with self.subTest(script=str(path), verb=verb):
                    self.assertNotIn(verb, text)

    def test_pr_submit_opens_a_draft(self):
        self._generate(_spec())
        text = (self.tmp / "upstream" / "widget-fix" / "submit.sh").read_text()
        create = [l for l in text.splitlines() if "gh pr create" in l]
        self.assertEqual(len(create), 1)
        self.assertIn("--draft", create[0])
        self.assertIn('--body-file "$BODY"', create[0])
        self.assertIn('--title "$TITLE"', create[0])
        for needed in ("gh auth status", "gh repo view", "gh repo fork",
                       'git am "$PATCH"', "SKIP_TESTS", "git push -u origin",
                       'refs/heads/$BRANCH', "am --abort"):
            self.assertIn(needed, text)

    @unittest.skipUnless(_have("bash"), "bash not installed")
    def test_hostile_title_quoted_safely(self):
        self._generate(_spec())
        text = (self.tmp / "upstream" / "widget-fix" / "submit.sh").read_text()
        assign = [l for l in text.splitlines() if l.startswith("TITLE=")]
        self.assertEqual(len(assign), 1)
        work = self.tmp / "evalcwd"
        work.mkdir()
        r = subprocess.run(
            ["bash", "-c", assign[0] + '\nprintf %s "$TITLE"'],
            cwd=work, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, _HOSTILE_TITLE)
        self.assertFalse((work / "PWNED").exists(),
                         "title text was executed as a command")

    def test_issue_first_variant(self):
        self.gen.generate(_spec(kind="issue", body_file="ISSUE.md"),
                          self.tmp / "u")
        text = (self.tmp / "u" / "widget-fix" / "submit.sh").read_text()
        self.assertIn("gh issue create", text)
        self.assertNotIn("gh pr create", text)
        self.assertIn("__COMPARE__", text)
        self.assertIn("Next step:", text)
        verify = (self.tmp / "u" / "widget-fix" / "verify.sh").read_text()
        self.assertIn("gh issue view", verify)
        self.assertNotIn("gh pr ", verify)

    def test_post_create_rename_only_when_configured(self):
        self.gen.generate(_spec(), self.tmp / "plain")
        plain = (self.tmp / "plain" / "widget-fix" / "submit.sh").read_text()
        for absent in ("git mv", "--force-with-lease", "--amend"):
            self.assertNotIn(absent, plain)
        self.gen.generate(_spec(post_create=[{"rename": {
            "from": "news/+fix-it.bugfix.rst",
            "to": "news/{pr_number}.bugfix.rst"}}]), self.tmp / "ren")
        ren = (self.tmp / "ren" / "widget-fix" / "submit.sh").read_text()
        self.assertIn("git mv -- news/+fix-it.bugfix.rst \"$NEW_PATH\"", ren)
        self.assertIn('NEW_PATH=news/"$NUM".bugfix.rst', ren)
        self.assertIn("git push --force-with-lease", ren)
        # the rename runs after the PR exists (it needs the number)
        self.assertLess(ren.index("gh pr create"), ren.index("git mv"))

    def test_dup_search_writes_out_file(self):
        self._generate(_spec())
        text = (self.tmp / "upstream" / "dup-search.sh").read_text()
        self.assertIn('OUT="$HERE/dup-search.out"', text)
        self.assertIn('} > "$OUT" 2>&1', text)
        self.assertEqual(text.count("  search issues "), 2)
        self.assertEqual(text.count("  search prs "), 2)
        self.assertIn('--repo "$UPSTREAM"', text)

    def test_verify_is_read_only(self):
        self._generate(_spec())
        text = (self.tmp / "upstream" / "widget-fix" / "verify.sh").read_text()
        gh_calls = re.findall(r"\bgh (\w+ \w+)", text)
        self.assertEqual(sorted(set(gh_calls)), ["pr diff", "pr view"])
        self.assertIn("headRefOid", text)

    def test_no_dup_search_without_queries(self):
        written = self.gen.generate(_spec(dup_queries=[]), self.tmp / "u")
        self.assertNotIn("dup-search.sh", {p.name for p in written})

    def test_spec_validation(self):
        bad = [
            {"upstream": "not-a-repo", "bugs": [{"slug": "a"}]},
            {"upstream": "a/b", "bugs": [{"slug": "a b"}]},
            {"upstream": "a/b", "bugs": [{"slug": "a", "patch": "p"}]},
            _spec(kind="issue", post_create=[{"rename": {
                "from": "x", "to": "{pr_number}"}}]),
            _spec(post_create=[{"rename": {"from": "x", "to": "no-number"}}]),
            _spec(post_create=[{"shell": "rm -rf /"}]),
        ]
        for spec in bad:
            with self.subTest(spec=spec):
                with self.assertRaises(self.gen.SpecError):
                    self.gen.validate_spec(spec)

    def test_cli_writes_scripts(self):
        spec_path = self.tmp / "scripts.json"
        spec_path.write_text(json.dumps(_spec()))
        r = subprocess.run([sys.executable, str(_GEN), str(spec_path),
                            str(self.tmp / "out")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.tmp / "out" / "widget-fix" / "submit.sh").is_file())
        self.assertTrue(os.access(self.tmp / "out" / "dup-search.sh", os.X_OK))


class BlobHashCompareTests(unittest.TestCase):

    PATCH = ("From abc Mon Sep 17 00:00:00 2001\nSubject: [PATCH] x\n---\n"
             "diff --git a/cobra.go b/cobra.go\nindex d9cd241..b36954a 100644\n"
             "--- a/cobra.go\n+++ b/cobra.go\n@@ -1 +1 @@\n-a\n+b\n"
             "diff --git a/cobra_test.go b/cobra_test.go\n"
             "index f1c5b0a..ef35f24 100644\n")

    def test_match_with_longer_forge_hashes(self):
        gen = _load_gen()
        forge = self.PATCH.replace("d9cd241..b36954a", "d9cd2410..b36954a1")
        self.assertEqual(gen.compare_blob_hashes(self.PATCH, forge), [])

    def test_mismatch_and_missing_file(self):
        gen = _load_gen()
        forge = self.PATCH.replace("b36954a", "0000000").split(
            "diff --git a/cobra_test.go")[0]
        problems = gen.compare_blob_hashes(self.PATCH, forge)
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any(p.startswith("cobra.go: patch") for p in problems))
        self.assertTrue(any("cobra_test.go: in the patch" in p for p in problems))


_GH_STUB = r'''#!/usr/bin/env bash
{ printf 'CALL'; printf ' [%s]' "$@"; printf '\n'; } >> "$GH_STUB_DIR/calls.log"
case "$1 $2" in
  "auth status") exit 0 ;;
  "api user") echo op ;;
  "repo view") echo main ;;
  "repo fork") echo "! op/widget already exists" ;;
  "repo clone") repo=$3; dest=$4; shift 4; [[ "${1:-}" == -- ]] && shift
                git clone -q "$@" "https://github.com/$repo.git" "$dest" ;;
  "pr create"|"issue create")
    kind=$1; shift 2
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --title) printf '%s' "$2" > "$GH_STUB_DIR/title"; shift ;;
        --body-file) cp "$2" "$GH_STUB_DIR/body"; shift ;;
        --draft) touch "$GH_STUB_DIR/draft" ;;
      esac
      shift
    done
    if [[ $kind == pr ]]; then echo https://github.com/acme/widget/pull/42
    else echo https://github.com/acme/widget/issues/7; fi ;;
  "pr view") if [[ " $* " == *" -q "* ]]; then echo 42; else echo '{"number":42}'; fi ;;
  "pr diff") printf 'diff --git a/README b/README\n' ;;
  "issue view") echo '{"number":7}' ;;
  "search issues"|"search prs") echo "stub result for: ${@: -1}" ;;
  *) echo "unexpected gh call: $*" >&2; exit 9 ;;
esac
'''


@unittest.skipUnless(_have("bash") and _have("git"), "needs bash and git")
class EndToEndStubGhTests(unittest.TestCase):
    """Run the generated scripts against a stub ``gh`` and local bare
    repos standing in for github.com (git url.insteadOf)."""

    def setUp(self):
        self.gen = _load_gen()
        self._td = tempfile.TemporaryDirectory()
        t = self.tmp = Path(self._td.name)
        (t / "bin").mkdir()
        (t / "bin" / "gh").write_text(_GH_STUB)
        (t / "bin" / "gh").chmod(0o755)
        (t / "stub").mkdir()
        (t / "home").mkdir()
        remote = t / "remote"
        self.env = {
            "PATH": f"{t / 'bin'}:{os.environ.get('PATH', '')}",
            "HOME": str(t / "home"),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": f"url.{remote}/.insteadOf",
            "GIT_CONFIG_VALUE_0": "https://github.com/",
            "GIT_CONFIG_KEY_1": "init.defaultBranch",
            "GIT_CONFIG_VALUE_1": "main",
            "GIT_AUTHOR_NAME": "Op", "GIT_AUTHOR_EMAIL": "op@example.com",
            "GIT_COMMITTER_NAME": "Op", "GIT_COMMITTER_EMAIL": "op@example.com",
            "GH_STUB_DIR": str(t / "stub"),
            "QPB_WORK_DIR": str(t / "work"),
            "TMPDIR": str(t),
        }
        # upstream acme/widget and the operator's fork op/widget
        seed = t / "seed"
        self._git("init", "-q", str(seed))
        (seed / "README").write_text("widget\n")
        self._git("-C", str(seed), "add", ".")
        self._git("-C", str(seed), "commit", "-q", "-m", "init")
        (remote / "acme").mkdir(parents=True)
        (remote / "op").mkdir()
        self._git("clone", "-q", "--bare", str(seed), str(remote / "acme" / "widget.git"))
        self._git("clone", "-q", "--bare", str(seed), str(remote / "op" / "widget.git"))
        self.fork = remote / "op" / "widget.git"
        # the fix: a README change plus a newsfragment to rename
        (seed / "README").write_text("widget fixed\n")
        (seed / "news").mkdir()
        (seed / "news" / "+fix-it.bugfix.rst").write_text("Fixed it.\n")
        self._git("-C", str(seed), "add", ".")
        self._git("-C", str(seed), "commit", "-q", "-m", "fix it")
        self.slug_dir = t / "upstream" / "widget-fix"
        self.slug_dir.mkdir(parents=True)
        self._git("-C", str(seed), "format-patch", "-q", "-1", "-o",
                  str(self.slug_dir))
        self.patch = next(self.slug_dir.glob("0001-*.patch"))
        (self.slug_dir / "PR.md").write_text("Body with `ticks` and $VARS\n")
        (self.slug_dir / "ISSUE.md").write_text("See __COMPARE__ for the fix.\n")

    def tearDown(self):
        self._td.cleanup()

    def _git(self, *args):
        subprocess.run(["git", *args], check=True, env={**os.environ, **self.env},
                       capture_output=True)

    def _run(self, script, *args, extra_env=None):
        env = {**os.environ, **self.env, **(extra_env or {})}
        env.pop("SKIP_TESTS", None)
        env.update(extra_env or {})
        return subprocess.run(["bash", str(script), *args], env=env,
                              cwd=self.tmp, capture_output=True, text=True,
                              timeout=120)

    def _gen(self, **overrides):
        spec = _spec(patch=self.patch.name, **overrides)
        self.gen.generate(spec, self.tmp / "upstream")

    def test_e2e_pr_submit(self):
        self._gen(post_create=[{"rename": {"from": "news/+fix-it.bugfix.rst",
                                           "to": "news/{pr_number}.bugfix.rst"}}])
        r = self._run(self.slug_dir / "submit.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("tests-ok", r.stdout)
        self.assertIn("https://github.com/acme/widget/pull/42", r.stdout)
        stub = self.tmp / "stub"
        self.assertEqual((stub / "title").read_text(), _HOSTILE_TITLE)
        self.assertEqual((stub / "body").read_text(),
                         "Body with `ticks` and $VARS\n")
        self.assertTrue((stub / "draft").exists())
        self.assertFalse(list(self.tmp.rglob("PWNED")))
        files = subprocess.run(
            ["git", "--git-dir", str(self.fork), "ls-tree", "-r",
             "--name-only", "fix-it"], capture_output=True, text=True,
            check=True).stdout.split()
        self.assertIn("news/42.bugfix.rst", files)
        self.assertNotIn("news/+fix-it.bugfix.rst", files)
        calls = (stub / "calls.log").read_text()
        for verb in self.gen.FORBIDDEN_GH_VERBS:
            self.assertNotIn("[" + "] [".join(verb.split()[1:]) + "]", calls)

    def test_e2e_skip_tests(self):
        self._gen()
        r = self._run(self.slug_dir / "submit.sh", extra_env={"SKIP_TESTS": "1"})
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("tests-ok", r.stdout)

    def test_e2e_git_am_conflict_stops(self):
        self._gen()
        self.patch.write_text(self.patch.read_text().replace(
            "-widget\n", "-something else\n"))
        r = self._run(self.slug_dir / "submit.sh")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("git am failed", r.stdout)
        self.assertIn("am --abort", r.stdout)
        self.assertFalse((self.tmp / "stub" / "title").exists(),
                         "no PR may be opened after a failed git am")

    def test_e2e_existing_branch_refused(self):
        self._gen()
        self.assertEqual(self._run(self.slug_dir / "submit.sh").returncode, 0)
        r = self._run(self.slug_dir / "submit.sh")
        self.assertEqual(r.returncode, 1)
        self.assertIn("branch fix-it exists", r.stdout)

    def test_e2e_issue_first(self):
        self._gen(kind="issue", body_file="ISSUE.md")
        r = self._run(self.slug_dir / "submit.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        body = (self.tmp / "stub" / "body").read_text()
        self.assertEqual(
            body, "See https://github.com/acme/widget/compare/main...op:widget:fix-it"
                  " for the fix.\n")
        self.assertIn("Next step:", r.stdout)
        calls = (self.tmp / "stub" / "calls.log").read_text()
        self.assertNotIn("[pr] [create]", calls)

    def test_e2e_dup_search_and_verify(self):
        self._gen()
        r = self._run(self.tmp / "upstream" / "dup-search.sh")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = (self.tmp / "upstream" / "dup-search.out").read_text()
        self.assertIn("## widget-fix", out)
        self.assertIn("stub result for: can't \"drop\" `x` $Y", out)
        self.assertEqual(out.count("### gh search issues"), 2)
        self.assertEqual(out.count("### gh search prs"), 2)
        r = self._run(self.slug_dir / "verify.sh", "42")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue((self.slug_dir / "verify.pr.json").is_file())
        self.assertTrue((self.slug_dir / "verify.pr.diff").is_file())


class SkillTextTests(unittest.TestCase):

    def test_phase7_menu_lists_the_path(self):
        text = _PHASE7.read_text(encoding="utf-8")
        self.assertIn("**5. Prepare upstream submissions**", text)
        self.assertIn("**Path 5: Prepare upstream submissions.**", text)
        self.assertIn("references/upstream_submission.md", text)

    def test_upstream_submission_guardrails(self):
        text = _UPSTREAM_MD.read_text(encoding="utf-8")
        for line in (
            "**The skill never submits.**",
            "never runs a `submit.sh` unless the operator explicitly asks",
            "**One bug at a time.**",
            "no queuing the next bug in the same message",
            "**Policy first, and the project's policy wins.**",
            "**No security-angle PRs.**",
            '"Found by Quality Playbook, an AI code-review tool, with '
            'Claude; I reviewed the change."',
            "No `Signed-off-by` or `Co-Authored-By` from the agent.",
            "**Side-effect rule.**",
            "stop for the operator's pick",
            "**Blind first.**",
        ):
            with self.subTest(line=line):
                self.assertIn(line, text)

    def test_upstream_submission_roster_and_statuses(self):
        text = _UPSTREAM_MD.read_text(encoding="utf-8")
        for role in ("EXEC-A", "EXEC-B", "O1", "O2", "O3", "O4", "O5",
                     "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"):
            with self.subTest(role=role):
                self.assertRegex(text, rf"\*\*{role} — ")
        for status in ("merged", "open", "sent", "ready", "needs-work",
                       "held", "decision", "dropped", "not-filed",
                       "duplicate", "maintainer-view", "ruled-out"):
            with self.subTest(status=status):
                self.assertIn(f"`{status}`", text)
        for field in ("status:", "title:", "link:", "updated:", "note:"):
            self.assertIn(f"\n{field} ", text)

    def test_skill_md_mentions_the_path(self):
        text = _SKILL_MD.read_text(encoding="utf-8")
        self.assertIn("See `references/upstream_submission.md`.", text)
        self.assertIn("| `references/upstream_submission.md` |", text)

    def test_check_skill_references_passes(self):
        r = subprocess.run([sys.executable, str(_GATE),
                            "--check-skill-references"],
                           cwd=_REPO, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SKILL reference integrity: PASS", r.stdout)

    def test_bundle_ships_script_and_reference(self):
        from bin.install_skill import _bundle_files
        dests = {Path(d).as_posix() for _s, d in _bundle_files(_SKILL_DIR)}
        self.assertIn("bin/upstream_scripts.py", dests)
        self.assertIn("references/upstream_submission.md", dests)


if __name__ == "__main__":
    unittest.main()

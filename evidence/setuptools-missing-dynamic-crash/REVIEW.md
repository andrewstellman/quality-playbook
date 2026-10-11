# setuptools: readme or requires-python outside `dynamic` crashes the build

Status: **open and ready for review (marked ready by Andrew on 2026-10-05), [pypa/setuptools#5343](https://github.com/pypa/setuptools/pull/5343).** Submitted by Andrew on 2026-10-05. See the submission record at the end.

## The project

[pypa/setuptools](https://github.com/pypa/setuptools) is the standard build tool for Python packages. It reads a project's `pyproject.toml` (and the older `setup.py` and `setup.cfg`) and produces the package metadata, wheels and source distributions.

Background for this bug:

- The `[project]` table in `pyproject.toml` holds the package metadata: name, version, description, readme, requires-python and so on.
- `dynamic = [...]` in that table lists the fields the build tool is allowed to fill in from somewhere else, such as `setup.py`.
- The packaging standard (PEP 621) says: "If the metadata does not list a field in `dynamic`, then a build back-end CANNOT fill in the requisite metadata on behalf of the user".
- So when a field is set in `setup.py` but is neither given in `[project]` nor listed in `dynamic`, setuptools prints a warning (``` `field` defined outside of `pyproject.toml` is ignored ```) and drops the `setup.py` value.

## The bug

For two fields, setuptools prints that warning and then crashes.

```toml
# pyproject.toml
[project]
name = "p"
version = "1"
```

```python
# setup.py
from setuptools import setup
setup(long_description="hello")
```

- Building this fails with `AttributeError: 'NoneType' object has no attribute 'get'`.
- With `setup(python_requires=">=3.8")` it fails with `TypeError: 'NoneType' object is not iterable`.
- The same project with `setup(description="short")` builds, with the warning and the value ignored. That is the intended behaviour for every field.

The cause is in `setuptools/config/_apply_pyprojecttoml.py`. `_handle_missing_dynamic` resets an ignored field to a "reset" value from a table. The table has entries for most fields but none for `readme` and `requires-python`, so those two are reset to `None`. The two functions that apply them, `_long_description` and `_python_requires`, do not accept `None`.

**Where the expectation comes from:**

- The warning text itself says the value "is ignored".
- PEP 621, the sentence quoted above (checked in the PEP text on 2026-10-05).
- The maintainer's explanation of why this is a warning and not an error, in a comment on issue #4183: "I have seem in the past several code bases where people add metadata to both `pyproject.toml` and `setup.py` in the hopes of handling old versions of setuptools. Hyrum's law observed, having a hard error there has the potential to backlash".

## The fix

Both functions now treat `None` as "reset this field".

```diff
 def _long_description(
-    dist: Distribution, val: _ProjectReadmeValue, root_dir: StrPath | None
+    dist: Distribution, val: _ProjectReadmeValue | None, root_dir: StrPath | None
 ):
     from setuptools.config import expand
 
     file: str | tuple[()]
+    if val is None:  # reset by _handle_missing_dynamic
+        _set_config(dist, "long_description", None)
+        return
     if isinstance(val, str):
```

```diff
-def _python_requires(dist: Distribution, val: str, _root_dir: StrPath | None):
+def _python_requires(dist: Distribution, val: str | None, _root_dir: StrPath | None):
+    if val is None:  # reset by _handle_missing_dynamic
+        dist.python_requires = None
+        # _core_metadata writes Requires-Python whenever the attribute exists
+        vars(dist.metadata).pop("python_requires", None)
+        return
     _set_config(dist, "python_requires", _static.SpecifierSet(val))
```

- For `python_requires` the value is cleared in two places. `dist.python_requires = None` stops a later step (`_finalize_requires`, `dist.py:379`) from copying the `setup.py` value back. The `pop` is needed because the metadata writer emits `Requires-Python` whenever the attribute exists (`_core_metadata.py:203`). The panel confirmed by mutation that the `pop` is necessary.

The test adds two rows to the existing parametrized test `TestPresetField.test_not_listed_in_dynamic`:

```diff
             ("classifiers", "classifiers", ["Private :: Classifier"]),
+            ("long_description", "readme", "Some description"),
+            ("python_requires", "requires-python", ">=3.8"),
```

A changelog entry is added, as the project requires (`newsfragments/README.rst`):

```
A ``long_description`` or ``python_requires`` given in ``setup.py`` while
``pyproject.toml`` does not list ``readme`` or ``requires-python`` in
``dynamic`` is now ignored with a warning, as for other fields, instead of
crashing the build.
```

Total: 3 files, 16 lines added, 2 removed.

## Regression test

Run again on 2026-10-05 in the cloud sandbox (Python 3.13.15, pytest 9.1.1) on upstream `main` at `4e612f9e`.

- **Green:** the test file passes with the patch: `67 passed, 1 xfailed`.
- **Revert:** with the source file put back and the test kept, exactly the two new cases fail:
  - `test_not_listed_in_dynamic[long_description-readme-Some description]` with `AttributeError: 'NoneType' object has no attribute 'get'`
  - `test_not_listed_in_dynamic[python_requires-requires-python->=3.8]` with `TypeError: 'NoneType' object is not iterable`
  - `2 failed, 65 passed, 1 xfailed`
- **Unpatched:** `65 passed, 1 xfailed`.
- **Whole suite** (`pytest -n 4` from the repository root, which is what the project's tox environment runs):
  - Unpatched: `1424 passed, 26 skipped, 14 xfailed, 2 xpassed`.
  - Fixed: `1426 passed, 26 skipped, 14 xfailed, 2 xpassed`.
  - The difference is the two new test cases. Nothing failed on either side.
- **Lint and types on the changed files:** `ruff check` gave `All checks passed!`, `ruff format --check` gave `2 files already formatted`, and `mypy` gave `Success: no issues found in 1 source file`.
- **Changelog:** `towncrier build --draft` renders the entry under "Bugfixes".

Substitutes, stated plainly:

- I did not run `tox`. I installed the same extras tox uses (`test`, `check`, `cover`, `enabler`, `type`, `core`) into a virtual environment and ran `pytest` directly. One Python version only.
- 18 tests in the file download example `setup.cfg` files from GitHub. The sandbox blocks that download (HTTP 403), so I fetched the same 18 files with `git` at the commit hashes pinned in the test list and placed them in the test's cache folder. Before I did that, those 18 failed identically on the unpatched and the fixed tree.
- Earlier logs from the first run and the panel are in this folder: `red.log`, `green.log`, `revert.log`.

## Knock-on effects

- **Callers.** `_long_description` and `_python_requires` are each used in one place, the `PYPROJECT_CORRESPONDENCE` table in the same file, which `_apply_project_table` walks for every `[project]` field. `None` can only arrive from `_handle_missing_dynamic`.
- **Before and after, 14 small projects.** On 2026-10-05 I built the wheel metadata for each one with the unpatched and the fixed source (`knock_on.py` in this folder).

| Case | Before | After |
|---|---|---|
| A. No `dynamic`; `setup.py` sets `long_description` | crash, `AttributeError` | builds; warning; no description |
| B. No `dynamic`; `setup.py` sets `python_requires` | crash, `TypeError` | builds; warning; no `Requires-Python` |
| C. No `dynamic`; `setup.py` sets both, plus a content type | crash, `AttributeError` | builds; two warnings; no description, no `Requires-Python`; `Description-Content-Type: text/markdown` is still written |
| D. `dynamic = ['readme']`; `setup.py` sets `long_description` | builds; description `hello` | same |
| E. `dynamic = ['requires-python']`; `setup.py` sets `python_requires` | builds; `Requires-Python: >=3.8` | same |
| F. `[project]` sets readme and requires-python; plain `setup()` | builds; both from `pyproject.toml` | same |
| G. `[project]` and `setup.py` both set them | builds; readme from `pyproject.toml`; `Requires-Python: >=3.8` | same |
| H. No `[project]` table; `setup.py` sets both | builds; both from `setup.py` | same |
| I. No `dynamic`; `setup.py` sets `description` | builds; warning; ignored | same |
| J. No `dynamic`; plain `setup()` | builds | same |
| K. `[project]` readme given as a table | builds; `text/x-rst` | same |
| L. No `dynamic`; `setup.py` sets both to empty strings | builds; no warning | same |
| M. No `dynamic`; `setup.cfg` sets both | crash, `AttributeError` | builds; two warnings; both ignored |
| N. No `dynamic`; `setup.py` sets `python_requires` and `description` | crash, `TypeError` | builds; two warnings; both ignored |

- **What changes for users.** Five cases change, and all five crash today. No project that builds today is affected.
- **The trade-off to be aware of.** A project in cases A, B, C, M or N cannot be built today. After the fix it builds, with a warning, and without the value from `setup.py`. If the author ignores the warning, the published package has no `Requires-Python` (or no long description). That is exactly what already happens today for `dependencies`, `classifiers` and the other fields. The re-review (O4) judged this acceptable.
- **Case C detail.** The content type from `setup.py` is still written although the description is dropped. The first version of the patch also reset the content type; the panel asked for that line to be removed because it was untested.

## Review history

- **Confirmed** by an independent confirmer: `docs/research/campaign-2026-09-29/confirm/LEDGER.md` line 142 (`BUG-004+020 readme/requires-python not in dynamic crash`, CONFIRMED).
- **Full panel** (2 executors and 13 reviewers), review id `st-004`: `evidence/review-2026-09-30-wave2/SYNTHESIS.md`. 9 SHIP and 6 FIX-REQUIRED, all for small revisions, all made (`CHANGES-AFTER-PANEL.md` in this folder):
  - The untested content-type reset was removed.
  - The type annotations now say `None` is accepted.
  - The `pop` line got a comment.
  - The PR text now links the maintainer's comment in #4183, not the issue as a whole.
- **Focused re-review** of the revision (9 reviewers): all SHIP. The `pop` was confirmed necessary by mutation.

## Upstream check (2026-10-05)

- `main` is at `4e612f9e` (2026-09-08, Jason R. Coombs).
- The patch applies cleanly with `git am`. Base blobs match the patch (`286ed43c`, `202f2318`), and so do the results (`b9d650dd`, `f46519a7`, new file `a0d67bfc`). Resulting tree: `f2a6082fca4e5e7edf4c9c1ff57c24048e0296a6`.
- `_handle_missing_dynamic` on `main` still warns and ignores, so the behaviour the fix matches has not changed.
- **Duplicate scan by git.** I fetched all 2104 pull-request heads. 20 heads that are not on `main` touch `_apply_pyprojecttoml.py`. None handles `None` in these two functions or adds reset values for these fields. The nearest is #5242 ("Preserve dynamic metadata for empty dependencies", 2026-06-25), which adds a separate function next to `_handle_missing_dynamic` and does not overlap. Git cannot tell me which of those are open, and I did not search the issue tracker (no `gh` here). The panel found no upstream report of this crash on 2026-09-30.

## Things to know before submitting

- **Issue #4183 is open and asks for the opposite direction.** Its title is "`_MissingDynamic` with pyproject.toml should be a failing error, not a warning". A maintainer could reply that a crash is close to what #4183 wants, and that these two fields could get a clear error since they never worked. The code calls the current behaviour "temporarily forgiving". The PR's answer is consistency with every other field, and it links the maintainer's own explanation. Be ready for that question.
- **A likely review question:** why not add `readme` and `requires-python` to the reset table like the other fields? Two reviewers expected it. The fixer's answer is that the two apply functions have no value that means "empty", so they need the `None` branch either way.
- **The text says `setup.py`; `setup.cfg` triggers it too** (case M). The changelog entry and PR text name only `setup.py`. That is incomplete, not wrong. I left the reviewed text alone.
- **One cosmetic point in the PR text.** The checklist line `[`newsfragments/`]` comes from the project's template, which defines that link at the bottom. Our text does not carry the definition, so it will show as plain bracketed text.
- **Script change 1 of 1, made on 2026-10-05.** The script's local check installed `.[test]` only. On current `main` that fails before any test runs (`PytestConfigWarning: Failed to import filter module 'coverage'`), because `pytest.ini` refers to the `coverage` package. I reproduced the failure in a fresh environment, changed the line to `.[test,cover]`, and confirmed the same command then gives `64 passed, 1 xfailed`. Checked with `bash -n` only; there is no zsh in the shell I can reach.
- **The script changes the commit after opening the PR.** setuptools names changelog files after the PR number, which does not exist until the PR is open. So the script opens the draft, renames the changelog file to `<number>.bugfix.rst`, amends the commit and force-pushes to your branch. The final PR head will differ from the reviewed patch in that one file name and nothing else. I will check exactly that.
- **AGENTS.md.** The repository's `AGENTS.md` tells agents to read the maintainer's "skeleton" document first. I read it. It asks contributors to run tox and fix lint findings, and to write issue references in commits as `owner/repo#N`. It says nothing about AI-written contributions or disclosure. Since July, `main` has 8 commits from the Copilot coding agent.
- **No CLA found** in the repository's docs. I cannot see whether a bot will comment.
- **Not verified today:** that the link's comment id (`issuecomment-1887294648`) points at the quoted comment. The fetch tool showed me the comment's text on the issue page but not comment ids. The panel checked the link on 2026-09-30.
- **I did not see the project's CI.** It runs several Python versions and platforms; I ran one.
- **Outside this change:** in case G, `setup.py`'s `python_requires` wins over `requires-python` in `pyproject.toml`, on both the unpatched and the fixed tree. I noticed it in the probe and did not investigate. It is not part of this PR.

## The PR as it will be submitted

**Title:** Ignore readme and requires-python not listed in dynamic

> ## Summary of changes
>
> `pyproject.toml` with `[project]` `name = 'p'`, `version = '1'` and no `dynamic`, plus `setup(long_description='hello')` in `setup.py`: the build fails with `AttributeError: 'NoneType' object has no attribute 'get'`. With `setup(python_requires='>=3.8')` it fails with `TypeError: 'NoneType' object is not iterable`. Expected: the `_MissingDynamic` warning and the value ignored, as already happens for `description`, `classifiers`, `dependencies`, etc. (the warn-and-ignore behaviour abravalheri explains in [a comment on #4183](https://github.com/pypa/setuptools/issues/4183#issuecomment-1887294648)).
>
> `_handle_missing_dynamic` (`setuptools/config/_apply_pyprojecttoml.py`) resets `readme` and `requires-python` to `None`, which `_long_description` and `_python_requires` did not handle. Both now treat `None` as a reset. For `python_requires`, the value is also cleared from `dist`, so `_finalize_requires` cannot copy it back. The new cases extend `TestPresetField.test_not_listed_in_dynamic`.
>
> PEP 621 (`dynamic`): "If the metadata does not list a field in ``dynamic``, then a build back-end CANNOT fill in the requisite metadata on behalf of the user".
>
> ### Pull Request Checklist
> - [x] Changes have tests
> - [x] News fragment added in [`newsfragments/`].
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

**Commit message** (author Andrew Stellman <andrew@stellman.com>, no trailers):

```
Ignore readme and requires-python not listed in dynamic

_handle_missing_dynamic resets these fields to None, which _long_description
and _python_requires did not accept (AttributeError / TypeError). Treat None
as a reset so the value from setup.py is dropped with the _MissingDynamic
warning, as for the other fields.
```

## To submit

```zsh
zsh ~/Documents/QPB/evidence/SUBMIT/submit-setuptools-missing-dynamic-crash.sh
```

Or, to skip the local check:

```zsh
SKIP_TESTS=1 zsh ~/Documents/QPB/evidence/SUBMIT/submit-setuptools-missing-dynamic-crash.sh
```

The script forks pypa/setuptools if needed, creates branch `missing-dynamic-readme-requires-python` from upstream `main`, applies the patch, runs the test file in a new virtual environment next to the work folder (it installs setuptools' test dependencies and downloads 18 small example files), pushes, opens a **draft** PR, renames the changelog file to the PR number, and force-pushes that. It prints the PR number, URL, draft state and title at the end.

## Submission record

- **Submitted:** 2026-10-05 by Andrew, after reviewing this file, using `submit-setuptools-missing-dynamic-crash.sh`. His paste of the script output: `"isDraft": true`, `"number": 5343`, `"title": "Ignore readme and requires-python not listed in dynamic"`.
- **PR:** [pypa/setuptools#5343](https://github.com/pypa/setuptools/pull/5343), opened as a **draft** from `andrewstellman:missing-dynamic-readme-requires-python` into `pypa:main`; 1 commit, `be18f5a653af47c6a9227738ce9a753c9efcb3b6`.
- **Verified by git (2026-10-05 17:25 UTC, `git fetch` of `refs/pull/5343/head`):**
  - One commit on top of `4e612f9e`, which is still the tip of `main`.
  - The only difference from the reviewed commit is the planned rename of the changelog file: `newsfragments/+missing-dynamic-readme-requires-python.bugfix.rst` is now `newsfragments/5343.bugfix.rst`, with the same content (blob `a0d67bfc`, rename similarity 100%). `git diff -M` between the reviewed commit and the PR head shows that rename and nothing else.
  - Blobs: `_apply_pyprojecttoml.py` `286ed43c..b9d650dd`, the test file `202f2318..f46519a7`, the same as the patch.
  - The commit message matches the patch. No trailers.
  - Author: `Andrew Stellman <andrew@stellman.com>`. Committer: `andrewstellman <astellman@stellman-greene.com>`, 2026-10-05 13:24:48 -0400 (the amend in the script).
- **Title and description:** the title in Andrew's paste matches. The fetch tool's reading of the PR page gave the description word for word as above, base `pypa:main`, 1 commit, one force-push logged, and no comments. That tool is a summary and has been wrong about draft state before, so treat the description check as likely, not proven. The exact check is `gh pr view 5343 --repo pypa/setuptools --json title,body,isDraft`.
- **Not checked:** CI results, and whether any bot has commented since.
- **Still to do on Andrew's side:** nothing until a maintainer responds.
- **2026-10-05 17:53 -04:00:** Andrew ran `gh pr view --json number,isDraft,state,url` for this PR. Output: `draft=false  OPEN`. He had marked it ready in the web UI. It is open and ready for review.
- **Maintainer responses:** none seen.

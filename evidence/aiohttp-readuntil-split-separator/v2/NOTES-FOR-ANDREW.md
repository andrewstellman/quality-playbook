# aiohttp-readuntil v2: steps only you can do

1. **Confirm the GitHub handle.** `andrewstellman` appears in `CHANGES/PRNUMBER.bugfix.rst` (`` -- by :user:`andrewstellman` ``) and in the PR's disclosure line. If yours is different, change both.

2. **Apply to a fresh branch of current upstream master.** The patch was made against e11d2836 (2026-09-27). The `From <sha>` line is from a local throwaway repo, not upstream.
   ```zsh
   git fetch origin   # origin = aio-libs/aiohttp; use your remote's name
   git switch -c fix-readuntil-split-separator origin/master
   git am /path/to/v2/0001-Fix-readuntil-missing-a-separator-split-across-chunk.patch
   ```
   If `git am` fails, master has moved in `streams.py` or `tests/test_streams.py` since e11d2836. Stop and check before resolving.

3. **Run the tests locally** before opening the PR (AGENTS.md: "Prove it works before opening the PR"):
   ```zsh
   AIOHTTP_NO_EXTENSIONS=1 PYTHONPATH=. pytest tests/test_streams.py --numprocesses=0 --no-cov
   ```
   Optionally, run `pre-commit run --all-files`. It was not run here, only black, isort, flake8 and codespell on the changed files.

4. **Open as a draft**, per AGENTS.md. Title = the commit subject: `Fix readuntil() missing a separator split across chunks`. Body = the contents of `PR-DRAFT.md`, pasted as-is.
   ```zsh
   gh pr create --draft --title "Fix readuntil() missing a separator split across chunks" --body-file PR-DRAFT.md
   ```

5. **Rename the news fragment to the PR number** once GitHub has assigned one. The towncrier check fails otherwise.
   ```zsh
   git mv CHANGES/PRNUMBER.bugfix.rst CHANGES/<PR number>.bugfix.rst
   git commit --amend --no-edit && git push --force-with-lease
   ```

6. **Review before marking ready.** AGENTS.md makes the human review your job, not the maintainers'. Read the diff and the PR body yourself, then mark the PR ready for review. AGENTS.md bars the agent from marking it ready or requesting reviewers, so both are yours to do.

**Title:** Match ** at any depth in MANIFEST.in include

## Summary of changes

With `data/a.txt`, `data/x/b.txt` and `data/x/y/c.txt`, `include data/**/*.txt` in `MANIFEST.in` puts only `data/x/b.txt` in the sdist; `graft data` + `exclude data/**/*.txt` removes all three. Expected: `include` matches all three, like `exclude`.

`FileList.include` (`setuptools/command/egg_info.py`) calls `glob(pattern)` with the default `recursive=False`, so `**` behaves like `*` (one directory level), while `exclude` goes through `translate_pattern`, where `**` crosses separators. The fix passes `recursive=True`, so `**` matches zero or more directories (as in the stdlib `glob`).

The docs (`docs/userguide/miscellaneous.rst`, lines 113-114): "Setuptools also has support for ``**`` matching zero or more characters including forward slash, backslash, and colon."

### Pull Request Checklist
- [x] Changes have tests
- [x] News fragment added in [`newsfragments/`].

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

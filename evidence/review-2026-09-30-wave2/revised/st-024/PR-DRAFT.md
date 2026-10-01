**Title:** Match ** at any depth in MANIFEST.in include

## Summary of changes

With `app/static/app.css` in the project, `include **/*.css` in `MANIFEST.in` adds nothing to the sdist (`warning: no files found matching '**/*.css'`), while `exclude **/*.css` matches that file. Expected: `include` matches it too.

`FileList.include` (`setuptools/command/egg_info.py`) calls `setuptools.glob.glob(pattern)` with the default `recursive=False`, so `**` behaves like `*` (one directory level), while `exclude` goes through `translate_pattern`, where `**` crosses separators. The fix passes `recursive=True`, as `recursive-include` already does, so `**` as a whole path component matches zero or more directories. `**` inside a name (`data/a**.txt`) is still not recursive.

Behaviour change: existing `include` lines with `**` may now add deeper files to the sdist, including files in hidden directories, `venv/` and `node_modules/` (`setuptools.glob` does not skip hidden files). Check the sdist contents after upgrading. A directory symlink loop produces many paths, as it already does for `recursive-include`.

The docs (`docs/userguide/miscellaneous.rst`, lines 113-114): "Setuptools also has support for ``**`` matching zero or more characters including forward slash, backslash, and colon."

### Pull Request Checklist
- [x] Changes have tests
- [x] News fragment added in [`newsfragments/`].

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

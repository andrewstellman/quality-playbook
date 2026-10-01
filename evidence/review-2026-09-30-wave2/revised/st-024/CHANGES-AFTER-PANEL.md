# st-024: changes after panel

- Newsfragment and PR say `include` lines with `**` may now add deeper files, including hidden dirs, venv/, node_modules/; check sdist contents (O2, S5): done in both.
- Symlink loops produce many paths, same as recursive-include (O2): done, PR only (one sentence).
- Say `setuptools.glob`, not stdlib glob: done (PR; "(as in the stdlib `glob`)" removed).
- `**` only as a whole path component (`data/a**.txt` still not recursive): done (PR; newsfragment says "as a whole path component"). Checked: setuptools.glob `app/a**.txt` gives ['app/a.txt'] with and without recursive=True.
- PR example matches the test: done (`include **/*.css`, `app/static/app.css`; the base warning line is from out/red.log).
- No code or test change; red/green/revert logs unchanged.

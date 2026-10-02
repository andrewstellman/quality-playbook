model: gpt-6-sol
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:09:37 UTC; finished 2026-09-28 23:11:46 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Review of `src/calibre/srv/`

## 1. Recipe upload guard misses executable formats

- **File and line:** `src/calibre/srv/cdb.py:226`
- **Severity:** High
- **What goes wrong:** A user with server write access can submit `added_formats` to `/cdb/set-fields` with `ext` set to `downloaded_recipe` or `original_downloaded_recipe`. The route only rejects `recipe` and `original_recipe`, so it stores the format. A subsequent `/conversion/start/{book_id}` with `input_fmt` set to `downloaded_recipe` loads the stored input through `RecipeInput`, which compiles and executes Python recipe source. This crosses the route's stated boundary against remotely added executable recipes.
- **Why this is wrong:** The adjacent error explicitly says recipe files are blocked because they allow code execution. The same module's `is_recipe_fmt()` at lines 68–70 identifies all four variants, and `/cdb/add-book` uses it at line 102. `src/calibre/ebooks/conversion/plugins/recipe_input.py` declares `downloaded_recipe` as an input format and calls `compile_recipe`, which uses `exec` in `src/calibre/web/feeds/recipes/__init__.py`.
- **Suggested fix:** Replace the hard-coded tuple check with `is_recipe_fmt(fmt)`. Apply the same helper to the remote `add_format` command's guard so all remote format entry points agree.

## 2. Expired rendered-book cache cleanup targets the working directory

- **File and line:** `src/calibre/srv/books.py:116`
- **Severity:** Medium
- **What goes wrong:** When a rendered book's manifest is at least one day old, `clean_final()` calls `safe_remove(x)`, where `x` is only the directory name returned by `os.listdir(fdir)`. The old cache entry under `fdir` remains. If the process's working directory contains a file or directory with that same name, the cleanup instead deletes that unrelated entry.
- **Why this is wrong:** Lines 108–111 locate and inspect the cache entry using `os.path.join(fdir, x, ...)`, and line 115 says the old book should be deleted. All other calls to `safe_remove` in this file pass full paths.
- **Suggested fix:** Call `safe_remove(os.path.join(fdir, x), is_file=False)`.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/convert.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/tests/convert.py`
- `src/calibre/db/cli/cmd_add.py`
- `src/calibre/db/cli/cmd_add_format.py`
- `src/calibre/ebooks/conversion/plugins/recipe_input.py`
- `src/calibre/utils/filenames.py`
- `src/calibre/web/feeds/recipes/__init__.py`

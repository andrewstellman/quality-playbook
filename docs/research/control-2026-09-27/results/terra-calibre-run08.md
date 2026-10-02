model: gpt-5.6-terra
repo: calibre
pinned commit: 7691f4f1a155d799afdfec99e2cdc2716c178402
date/time started and finished: started approximately 2026-09-28 23:40:24 UTC; finished 2026-09-28 23:42:29 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Calibre `src/calibre/srv/` review

## Findings

### High — recipe upload guard can be bypassed with `downloaded_recipe`

- **File/line:** `src/calibre/srv/cdb.py:226`
- **What goes wrong:** A client with access to `POST /cdb/set-fields/...` can put a format whose `ext` is `downloaded_recipe` (or `original_downloaded_recipe`) in `changes.added_formats`. The endpoint accepts it and calls `db.add_format()`, despite recipe formats being executable code.
- **Why this is wrong:** The adjacent helper `is_recipe_fmt()` at lines 68–70 explicitly classifies both `recipe` and `downloaded_recipe` (after removing `original_`) as recipe formats. The `/cdb/add-book` endpoint uses that helper at lines 102–103 and rejects them because they “allow code execution.” `cdb_set_fields()` duplicates a narrower check that rejects only `recipe` and `original_recipe`, leaving the other two formats unprotected.
- **Suggested fix:** Replace the line-226 tuple membership check with `if is_recipe_fmt(fmt):` so both upload endpoints apply the same policy.

### Low — expired rendered-book cache directories are never removed

- **File/line:** `src/calibre/srv/books.py:116`
- **What goes wrong:** Once a rendered book cache directory has an unaccessed manifest older than the interval, `clean_final()` calls `safe_remove(x)`, where `x` is only the directory entry name returned by `os.listdir(fdir)`. It therefore removes a relative path from the server process’s current working directory rather than `<cache>/srvb/f/<x>`. The expired cache remains in `fdir`, so stale render artifacts accumulate indefinitely.
- **Why this is wrong:** The manifest age is read from `os.path.join(fdir, x, 'calibre-book-manifest.json')` at line 111, and the comment at line 115 says the corresponding cached book should be deleted. Other cleanup calls pass a full path to `safe_remove()` (for example, lines 82, 134, and 142).
- **Suggested fix:** Call `safe_remove(os.path.join(fdir, x), False)`.

## Files read

- `src/calibre/srv/routes.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/convert.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/books.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/ajax.py`
- `src/calibre/srv/metadata.py`

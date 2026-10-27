A before-handler scoped to a static path, such as `before("/secret/*")`, can be skipped for files under that path. Routing matches the raw request path, but the resource handlers decode and normalise it, so `/%73ecret/file.txt` and `//secret/file.txt` (both handlers) and `/./secret/file.txt` and `/x/../secret/file.txt` (`JavalinStaticResourceHandler`) serve `secret/file.txt` without running the handler. Static-file roles are not affected.

Both resource handlers now return 404 for a static path with an empty segment, a dot segment or a percent-encoded unreserved character. Other encoded characters, such as `%20` and UTF-8, behave as before. One side effect: with `treatMultipleSlashesAsSingleSlash` on, static paths containing `//` now get a 404 too. The test in `TestStaticFiles` covers both handlers.

Reported to @tipsy by email on 20 Oct. Found with the Quality Playbook, an AI code-review tool I maintain; I reproduced it and reviewed the fix myself.

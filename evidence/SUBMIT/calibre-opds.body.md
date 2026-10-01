The OPDS navcatalog, category and categorygroup handlers return a 500 when an id in the URL isn't valid hex (for example `/opds/navcatalog/zz`). This catches the decode error and returns 404, as those handlers already do for other bad input.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the patch.

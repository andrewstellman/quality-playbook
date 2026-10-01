**Title:** Content server: return 404 instead of 500 for malformed hex ids in OPDS feeds

The OPDS navcatalog, category and categorygroup handlers return a 500 when an id in the URL isn't valid hex (for example `/opds/navcatalog/zz`). This catches the decode error and returns 404, as those handlers already do for other bad input.

Found with an AI-assisted review tool; I reviewed the patch.

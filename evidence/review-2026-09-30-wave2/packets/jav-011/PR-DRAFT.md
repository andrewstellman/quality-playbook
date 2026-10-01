**Title:** [static-files] Treat precompressMaxSize = 0 as "all sizes"

The static files docs (javalin.io/documentation, Static Files config block) say:
`staticFiles.precompressMaxSize = 0; // max size for pre-compression in bytes (-1 to disable, 0 for all sizes)`

But setting it to `0` turns precompression off. With `precompressMaxSize = 0` and `Accept-Encoding: gzip`, a static file is gzipped on the fly (chunked, no `Content-Length`) and nothing goes into the precompression cache; with a positive limit the same file is precompressed and cached.

Both `JettyResourceHandler.handle` and `JavalinStaticResourceHandler.handle` only take the precompression path when the value is `> 0`, and the size checks (`JettyPrecompressingResourceHandler.handle`, `JavalinStaticResourceHandler.handlePrecompressed`) compare `length > precompressMaxSize`, which would reject every file at 0 anyway.

This precompresses for any value `>= 0` and skips the size limit when it's `0`. The default (`-1`) still means disabled. Added a test to `TestStaticFilesPrecompressor` that runs against both handlers.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

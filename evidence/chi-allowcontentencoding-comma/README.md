# chi: `AllowContentEncoding` rejects a comma-separated `Content-Encoding` list

**Verdict: ALREADY REPORTED.** Reproduced on master and fixed locally, but already covered by **issue #959** (open) and **open PR #1182** (2026-09-17, same fix, same test change). An earlier PR, #1144, was closed by its author without merging. **Do not open a new PR.**
QPB source: chi-1.6.0 BUG-007.

## Pinned upstream
`3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc` (2026-09-18), go1.25.1 linux/arm64 (see chi-gethead-mount/README.md for toolchain).

## Defect
`middleware/content_encoding.go:17-29` loops over `r.Header["Content-Encoding"]` and looks up each *header line* in the allow-list. net/http does not split one line on commas, so `Content-Encoding: gzip, deflate` is looked up as the literal string `"gzip, deflate"` and gets a 415, even when both codings are allowed. Sending the same two codings as two separate header lines is accepted.

## Expected behaviour
- RFC 9110 §8.4: `Content-Encoding = #content-coding`, and "If one or more encodings have been applied to a representation, the sender that applied the encodings MUST generate a Content-Encoding header field that lists the content codings in the order in which they were applied."
- RFC 9110 §5.3: multiple field lines may be combined into one comma-separated line without changing the semantics.
- chi's own test (`middleware/content_encoding_test.go:15-19`) says the middleware supports `Content-Encoding: gzip, deflate`. The test never exercises that case, because it calls `Header.Set` in a loop, so each call overwrites the previous one.

## Red / green
- `red.log`: 2 of the 3 new single-line cases fail on master (`got 415, want 200`). The rejecting case `deflate, br` passes on both.
- `green.log`: all pass with the split-on-comma fix.
- `suite-before.log` / `suite-after.log`: `go test -count=1 ./...` passes on both (after run at `891c298`).
- The patch also changes the existing test from `Set` to `Add`, so the multi-line cases really send multiple lines. #1182 does the same.
- The patch ignores empty list elements (RFC 9110 §5.6.1.2: "A recipient MUST parse and ignore a reasonable number of empty list elements"). #1182 may differ on this detail.

## Disclosure search
- `repo:go-chi/chi AllowContentEncoding`: #1182 (open PR, "split comma-separated Content-Encoding values", Fixes #959), #1144 (closed by its author, not merged), #469 (original feature). The #469 description says "Content-Encoding header may have more than one encoding listed", which confirms the intent.
- Issue #959 "Content-Encoding header is not being properly parsed": open.

## Open question for Andrew
Whether to do anything. Options: nothing, or a supportive review/comment on #1182 pointing to the reproduction. Both are your call; nothing has been posted.

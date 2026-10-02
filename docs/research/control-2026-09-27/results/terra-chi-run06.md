model: gpt-5.6-terra
repo: chi
pinned commit: 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc
date/time started and finished: started approximately 2026-09-28 22:37:22 UTC; finished 2026-09-28 22:39:23 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# chi middleware review — 3d1777a1ef8881f7d1da0b02c76ca8f0a29cd2bc

## Findings

### Medium — `Compress` sends an encoding the client explicitly rejected

- **File/line:** `middleware/compress.go:260-265`
- **What goes wrong:** `matchAcceptEncoding` treats an encoding as accepted when its name appears anywhere in a comma-delimited member.  Thus a request with `Accept-Encoding: gzip;q=0` receives a `Content-Encoding: gzip` response even though `q=0` explicitly prohibits gzip.  It also treats arbitrary tokens such as `xgzip` as gzip and ignores subsequent `Accept-Encoding` field values because `selectEncoder` uses `Header.Get`.
- **Why this is wrong:** `Compress` promises to choose a response data format based on `Accept-Encoding`, but lines 260-265 only use `strings.Contains`; they neither parse encoding tokens nor honor their quality values.  A client that rejects gzip cannot decode the emitted body, so this breaks content negotiation.
- **Suggested fix:** Parse every `Accept-Encoding` field value into exact coding tokens and parameters, reject codings with `q=0`, apply the advertised quality/preference rules (including `*` where appropriate), and select only a supported coding that remains acceptable.

### Medium — `AllowContentEncoding` rejects valid comma-separated encoding lists

- **File/line:** `middleware/content_encoding.go:17-25`
- **What goes wrong:** With `AllowContentEncoding("gzip", "deflate")`, a request carrying `Content-Encoding: gzip, deflate` receives 415.  The middleware considers the whole header value (`"gzip, deflate"`) to be one encoding rather than checking both codings.
- **Why this is wrong:** The source test itself documents support for `Content-Encoding: gzip, deflate` and `Content-Encoding: deflate, gzip` (`middleware/content_encoding_test.go:16-19`), and the middleware comment says that *all encodings* in the request must be allowed.  Lines 23-25 instead validate each header field value as one map key, so a standard list in a single field cannot pass.  (The existing test accidentally uses `Header.Set` repeatedly, which overwrites rather than creates the advertised list.)
- **Suggested fix:** Split every `Content-Encoding` field value on commas, trim and normalize each individual coding, then require every resulting coding to exist in `allowedEncodings`.  Add regression cases using a single header value containing `gzip, deflate`.

## Validation

`go test ./middleware` passed. `go test ./...` reached an unrelated sandbox restriction when a root-package test attempted to bind `tcp6 [::1]:0`.

## Files read

`middleware/basic_auth.go`, `middleware/clean_path.go`, `middleware/client_ip.go`, `middleware/compress.go`, `middleware/content_charset.go`, `middleware/content_encoding.go`, `middleware/content_type.go`, `middleware/get_head.go`, `middleware/heartbeat.go`, `middleware/logger.go`, `middleware/maybe.go`, `middleware/middleware.go`, `middleware/nocache.go`, `middleware/page_route.go`, `middleware/path_rewrite.go`, `middleware/profiler.go`, `middleware/realip.go`, `middleware/recoverer.go`, `middleware/request_id.go`, `middleware/request_size.go`, `middleware/route_headers.go`, `middleware/strip.go`, `middleware/sunset.go`, `middleware/supress_notfound.go`, `middleware/terminal.go`, `middleware/timeout.go`, `middleware/value.go`, `middleware/wrap_writer.go`; plus the relevant `middleware/*_test.go` files.

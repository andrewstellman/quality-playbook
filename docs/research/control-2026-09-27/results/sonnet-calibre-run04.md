# Code review: calibre `src/calibre/srv/`

Repo: calibre, pinned commit `7691f4f1a155d799afdfec99e2cdc2716c178402`, scope `src/calibre/srv/`.

## Defect 1: `job_done()` passes the wrong value as `is_http1`, so HTTP/1.0 responses are treated as HTTP/1.1

- **File/line:** `src/calibre/srv/http_response.py:561`

  ```python
  data, output = result
  output = self.finalize_output(output, data, self.method is HTTP1)
  ```

- **What goes wrong:** `self.method` holds the HTTP request method token (e.g. `'GET'`, `'HEAD'`, `'POST'` — set in `http_request.py:315`, `self.method = method.decode('ascii').upper()`). `HTTP1` is the protocol-version string constant `'HTTP/1.0'` (`utils.py:25`). The expression `self.method is HTTP1` compares a method string against a protocol-version string with `is` (identity); it can never be true for any real request, because `self.method` is never the string `'HTTP/1.0'`. So the `is_http1` argument passed into `finalize_output()` is unconditionally `False`, for both HTTP/1.0 and HTTP/1.1 requests.

  Contrast this with the correct pattern used seven lines earlier in the very same class:

  ```python
  def simple_response(self, status_code, msg='', close_after_response=True, extra_headers=None):
      if self.response_protocol is HTTP1:
          ...
  ```

  (`http_response.py:460`), which is how the codebase elsewhere checks the negotiated response protocol. The call at line 561 should be `self.response_protocol is HTTP1`, not `self.method is HTTP1`.

- **Why it is wrong:** Inside `finalize_output()` (`http_response.py:713-809`), `is_http1` gates two protocol-sensitive behaviors that HTTP/1.0 does not support:

  ```python
  compressible = (
      compressible
      and request.status_code == http.client.OK
      and (opts.compress_min_size > -1 and output.content_length >= opts.compress_min_size)
      and acceptable_encoding(request.inheaders.get('Accept-Encoding', ''))
      and not is_http1
  )
  accept_ranges = not compressible and output.accept_ranges is not None and request.status_code == http.client.OK and not is_http1
  ...
  if compressible or output.content_length is None:
      outheaders.set('Transfer-Encoding', 'chunked', replace_all=True)
  ```

  `Transfer-Encoding: chunked` is an HTTP/1.1-only mechanism — RFC 7230 §3.3.1 states "A server MUST NOT send a response containing Transfer-Encoding unless the corresponding request indicates HTTP/1.1 (or later)." Because `is_http1` is always `False` (the identity check is broken), a genuine HTTP/1.0 client requesting a compressible resource (e.g. a JSON/XML/text OPDS or content-server response over 1024 bytes, gzip-acceptable) will have `compressible` evaluate to `True` and get a chunked, gzip-encoded response body — which an HTTP/1.0 client cannot correctly parse (it does not understand chunk-size framing), so the client will read a garbled/truncated body or hang waiting for a Content-Length-terminated stream that never comes the way it expects.

  It also means `Accept-Ranges: bytes` can be advertised (and `Range` requests serviced) to HTTP/1.0 clients even though `accept_ranges` was clearly intended to be suppressed there (`not is_http1`), and — because `get_ranges()` is still applied and honored for such clients — `Content-Length` may not describe the full representation as an HTTP/1.0 client would expect for a non-partial response, compounding the confusion for any HTTP/1.0 user agent or proxy that doesn't send/understand `Range`/`Accept-Ranges` semantics correctly.

  In short: the comment/intent embedded in the code (guarding chunked/gzip encoding and range advertisement behind "is this HTTP/1.0") is defeated by a typo-level identity-comparison bug, so HTTP/1.0 clients get HTTP/1.1-only wire formats.

- **Severity:** High. This is a protocol-correctness bug that can break responses for any HTTP/1.0 client (older readers, some embedded e-reader HTTP stacks, simple proxies) whenever a compressible response is served — a broad, easily triggered code path (any GET of a text/JSON/XML resource above `compress_min_size` with `Accept-Encoding: gzip`).

- **Suggested fix:**

  ```python
  output = self.finalize_output(output, data, self.response_protocol is HTTP1)
  ```

## Other observations (not reported as defects)

- `AuthController.check()` (`auth.py:262-265`) and the digest/basic-auth password comparisons use plain `==` rather than a constant-time comparison, which is a latent timing-side-channel concern, but this matches the pre-existing/likely-original design of this module (the class docstring already acknowledges weaker guarantees, e.g. accepting the digest nonce-count-replay tradeoff) and I could not confirm this is a introduced regression vs. long-standing accepted behavior, so I'm not reporting it as a defect I'm confident is new/wrong.
- Everything else read (see list below) matched its own documentation/comments and appeared internally consistent.

## Files read

- `src/calibre/srv/auth.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py` (full)
- `src/calibre/srv/loop.py` (partial: `ReadBuffer`, trusted-IP helpers, `Connection.__init__`, `parsed_trusted_ips`, `ServerLoop.__init__`)
- `src/calibre/srv/web_socket.py` (partial: header/constants, `ReadFrame`)
- `src/calibre/srv/content.py` (grep for `def`/`content_length`/`Range`/`etag`, then read `data_file`, `get_data_file`, `upload_data_files`, `remove_data_files`, `sanitize_content_disposition`)
- Directory listing / line counts of all files under `src/calibre/srv/` (`auth.py`, `ajax.py`, `bonjour.py`, `books.py`, `cdb.py`, `changes.py`, `code.py`, `content.py`, `convert.py`, `embedded.py`, `errors.py`, `fts.py`, `handler.py`, `http_request.py`, `http_response.py`, `jobs.py`, `last_read.py`, `legacy.py`, `legacy_book_details.py`, `library_broker.py`, `loop.py`, `manage_users_cli.py`, `metadata.py`, `opds.py`, `opts.py`, `pool.py`, `pre_activated.py`, `render_book.py`, `routes.py`, `standalone.py`, `users.py`, `users_api.py`, `utils.py`, `web_socket.py`) — read in full or in targeted part as noted above; the remainder (`ajax.py`, `books.py`, `cdb.py`, `code.py`, `convert.py`, `embedded.py`, `fts.py`, `handler.py`, `jobs.py`, `legacy.py`, `legacy_book_details.py`, `library_broker.py`, `manage_users_cli.py`, `metadata.py`, `opds.py`, `opts.py`, `pool.py`, `pre_activated.py`, `render_book.py`, `routes.py`, `standalone.py`, `users.py`, `users_api.py`, `changes.py`, `bonjour.py`, `errors.py`, `last_read.py`) were only listed by size, not read line-by-line, given the scope's size relative to review depth.

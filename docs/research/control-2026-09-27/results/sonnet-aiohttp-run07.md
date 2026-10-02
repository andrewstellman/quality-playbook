# Code review: aiohttp (`aiohttp/` package, excluding tests)

Repo: aio-libs/aiohttp, pinned commit `e11d2836203a21bec59095498e578d37801027e7` (dev tree at `__version__ = "4.0.0a2.dev0"`).

## Method

This is a large package (~26,700 lines across ~50 modules), so the review combined two approaches:

1. **Anomaly-guided reading**: a released version of aiohttp (3.14.3) happened to be installed in the provided venv (`/tmp/aiohttp-venv`), so I diffed every module in the checkout against the corresponding installed 3.14.3 file to see exactly what changed on the dev branch, then read each diff hunk for correctness. Because the checkout is a full major-version ahead of 3.14.3 (`4.0.0a2.dev0`), most diffs are large, legitimate refactors (type-hint modernization, `attr`→`dataclasses` migration, removal of Python 3.9/aiodns-1.1 compatibility shims, new features such as WebSocket message-type classes and a chunk-received tracing hook). I read through all of these diffs looking for hunks where the *logic*, not just syntax, changed.
2. **Direct reading of security/correctness-critical paths** regardless of whether they diffed: static file serving and path-traversal defenses (`web_fileresponse.py`, `web_urldispatcher.py`'s `StaticResource`), cookie parsing and domain/path matching (`_cookie_helpers.py`, `cookiejar.py`), HTTP header/Content-Length/Transfer-Encoding and chunked-body parsing (`http_parser.py`), Digest auth (`client_middleware_digest_auth.py` — this file is byte-for-byte identical to the installed 3.14.3 release, so it needed no separate scrutiny), redirect handling and credential-header stripping across origins (`client.py`), and the read/flow-control paths in `streams.py` and `web_protocol.py`'s message-queue backpressure logic.

I did not achieve full line-by-line coverage of the very largest files (`client.py`, `client_reqrep.py`, `connector.py`, `web_request.py`, `helpers.py` — each 800–1800 lines with 400–1600 changed lines against 3.14.3); I read their diffs but not every unchanged line. Everything reported below I verified by reading the actual code in the checkout, not just the diff.

## Findings

### 1. `StreamReader.read_nowait()` fires the chunk-tracing callback via an un-awaited, unreferenced `asyncio.create_task`

- **File**: `aiohttp/streams.py`, lines 526–539 (the `read_nowait` method)

```python
        return self._read_nowait(n)

    def _read_nowait_chunk(self, n: int) -> bytes:
```
(surrounding context, lines 519–540):
```python
    def read_nowait(self, n: int = -1) -> bytes:
        ...
        if self._waiter and not self._waiter.done():
            raise RuntimeError(
                "Called while some coroutine is waiting for incoming data."
            )

        chunk = self._read_nowait(n)
        if chunk and (cb := self._on_chunk_received) is not None:
            # read_nowait is sync but the hook is async; schedule it so the
            # observability event still fires.
            # TODO: Save and await this task.
            asyncio.create_task(cb(chunk))  # type: ignore[unused-awaitable]
        return chunk
```

- **What goes wrong**: `read_nowait()` is a synchronous method, but the per-chunk tracing hook (`_on_chunk_received`, wired up in `client_reqrep.py:562` to `ClientResponse._on_chunk_response_received`, which fires the `on_response_chunk_received` trace event) is a coroutine. To reconcile this, the code spawns a bare `asyncio.create_task(cb(chunk))` and immediately discards the reference — the task is neither stored nor awaited anywhere.
  - **Silently dropped work / warnings**: Per the standard library's own documentation, "the event loop only keeps weak references to tasks... to prevent a task disappearing mid-execution the application should keep a reference to it" (`asyncio.create_task` docs). Because no reference is kept, the created task can be garbage-collected before it runs, silently dropping the trace event with no error surfaced anywhere (or, if it does run, its exceptions become "Task exception was never retrieved" warnings that no caller can observe or handle).
  - **`_on_chunk_response_received`'s own error path is defeated**: that callback (`client_reqrep.py:691-697`) explicitly calls `self.close()` and re-raises on any exception from the trace handlers, i.e. it's written assuming the caller can observe the failure and react (e.g., stop consuming an already-closing response). Because the task is fire-and-forget from `read_nowait`, that `close()`/re-raise happens asynchronously, disconnected from the code path that called `read_nowait()` and got back `chunk` as if nothing had happened — so callers can keep reading a connection that is concurrently being torn down by the trace-error handler, without ever seeing the exception.
  - The comment directly above the call — `# TODO: Save and await this task.` — is the code's own acknowledgment that this is incomplete, which establishes that the intended behavior is for the task to be tracked/awaited, not silently fired.
- **Severity**: low. `read_nowait()` with a chunk-tracing hook attached is a narrow path (it requires a client configured with `on_response_chunk_received` tracing *and* code that calls the low-level `read_nowait()` rather than `read()`/`readany()`, which do `await` the equivalent `_fire_chunk_received` helper synchronously in-line at lines 418/449/464/486/496). Impact is a class of lost/unobservable tracing events and unretrieved-exception warnings, not data corruption or a security issue, and the other five call sites in the same file (`readuntil`, `read`, `readany`, `readchunk` ×2) correctly `await self._fire_chunk_received(chunk)` instead.
- **Suggested fix**: keep a strong reference to the created task (e.g., append it to a `set` owned by the `StreamReader` with a `add_done_callback` to discard it on completion — the same pattern already used elsewhere in this codebase for a similar problem, see `_CLOSE_FUTURES` in `web_fileresponse.py:82,298-299`), or expose an async variant of `read_nowait` for tracing-enabled readers so the callback can be awaited directly.

## Nothing else found with confidence

Across the areas I read in depth — static-file path resolution/symlink-sandbox checks, cookie domain/path matching (`_is_domain_match`, `filter_cookies`), the `parse_set_cookie_headers`/`parse_cookie_header` regex-based cookie parsers, HTTP/1.1 header and chunked-transfer parsing (including the Transfer-Encoding vs. Content-Length conflict check, chunk-size/chunk-extension/trailer bounds checks), Digest auth challenge parsing and response computation, and the redirect loop's cross-origin `Authorization`/`Cookie`/`Proxy-Authorization` stripping (`client.py:850-854`, using `popall` — this is itself a recent fix for a real historical bug, dropping only the *first* occurrence of each header, per `CHANGES.rst`'s 3.14.3 entry citing issue #13180) — I did not find logic that contradicts the code's own comments/documentation or the relevant RFCs. The `web_protocol.py`/`base_protocol.py` message-queue backpressure refactor (new `_buffer_paused` flag replacing the old `_reading_paused_for_msg_queue()` hook) is internally consistent across all four call sites I checked (`data_received`, `_resume_reading_if_drained`, `_replay_message_tail`, the main request loop).

## Files read

- `aiohttp/web_fileresponse.py` (full)
- `aiohttp/web_urldispatcher.py` (`StaticResource` and helpers, `_unquote_path_safe`/`_quote_path`/`_requote_path`; skimmed the rest)
- `aiohttp/_cookie_helpers.py` (full)
- `aiohttp/cookiejar.py` (full)
- `aiohttp/http_parser.py` (full)
- `aiohttp/client_middleware_digest_auth.py` (full)
- `aiohttp/client.py` (redirect-handling section closely; diff for the rest)
- `aiohttp/streams.py` (full)
- `aiohttp/base_protocol.py` (full)
- `aiohttp/web_protocol.py` (buffer/backpressure sections closely; diff for the rest)
- `aiohttp/payload.py` (diff + spot checks)
- `aiohttp/client_reqrep.py` (diff + targeted reads around `_on_chunk_response_received`, redirect body handling)
- `aiohttp/hdrs.py`, `aiohttp/tcp_helpers.py`, `aiohttp/web_log.py`, `aiohttp/client_middlewares.py`, `aiohttp/http_websocket.py`, `aiohttp/web_routedef.py`, `aiohttp/web_middlewares.py`, `aiohttp/typedefs.py`, `aiohttp/formdata.py`, `aiohttp/http_exceptions.py`, `aiohttp/worker.py`, `aiohttp/abc.py`, `aiohttp/http_writer.py`, `aiohttp/resolver.py` (full diffs against installed 3.14.3, read in full)
- `aiohttp/CHANGES.rst` (top entries, for context on recent fixes)
- Diffed (but not fully read line-by-line) against installed aiohttp 3.14.3: `connector.py`, `web_app.py`, `web_response.py`, `web_request.py`, `web.py`, `web_ws.py`, `web_exceptions.py`, `web_runner.py`, `web_server.py`, `client_ws.py`, `client_proto.py`, `client_exceptions.py`, `compression_utils.py`, `multipart.py`, `test_utils.py`, `helpers.py`, `tracing.py`, `__init__.py`

No files outside the repository checkout were consulted; no web/issue-tracker access was used.

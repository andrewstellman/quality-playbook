# 07 — Error Handling

**Source:** `bus_tracker.py` (all error paths) + 2026-04-10 build chat commentary on "semantic failures should not look like empty service."

## Three classes of failure, three response strategies

Bus-tracker distinguishes **startup / configuration errors** (fatal, exit 1 with an instructional message), **upstream / transport errors** (non-fatal, surface as a structured error dict), and **client disconnect errors** (silently swallow — they're expected).

### Startup errors — fatal, exit 1

These are detected before any network request and produce an instructional message, then `sys.exit(1)`:

| Condition | Message | Exit |
|---|---|---|
| `config.json` missing | `ERROR: <path> not found.\n\nCopy config.example.json to config.json and edit it with your stops.\nSee README.md for details on finding MTA stop IDs.` | 1 |
| `config.json` has empty `stops` dict | `ERROR: No stops configured in config.json.` | 1 |
| No API key resolvable (CLI → env → file all empty) | `ERROR: No API key found.\n\nGet a free key at: https://register.developer.obanyc.com/\n\nThen do one of:\n  1. export MTA_API_KEY=your_key_here\n  2. echo 'your_key_here' > .api_key\n  3. python bus_tracker.py --key your_key_here` | 1 |

**Design-intent claim:** these three messages are the entire startup failure taxonomy. Each message tells the user *exactly what to do* to recover. The build chat explicitly positions this as "the user running `python bus_tracker.py` for the first time should never get a stack trace — they should get a one-screen instruction."

**Divergence signal:** a `FileNotFoundError` / `KeyError` / `json.JSONDecodeError` that reaches the terminal unhandled is a regression. The `json.JSONDecodeError` on corrupt config is the one deliberately-unhandled case (see below).

### Intentionally unhandled: corrupt config JSON

`load_config` does **not** catch `json.JSONDecodeError`. If `config.json` is syntactically broken, the exception propagates and Python prints its default traceback. This is deliberate: a corrupt config is a programmer/edit error, not a user workflow state, and the line number in the traceback is the useful debugging info. Silently falling back to `DEFAULT_CONFIG` would hide the problem.

### Upstream / transport errors — non-fatal, structured dict

`fetch_stop_arrivals` wraps the SIRI fetch in:

```python
try:
    with urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
except (URLError, json.JSONDecodeError) as exc:
    return {"error": str(exc), "arrivals": []}
```

What this catches:

- **Connection failures** (DNS resolution, TCP refused, TLS handshake) — caught via `URLError`.
- **Timeouts** (15-second `timeout=` parameter exceeded) — raised as `URLError` / `socket.timeout`, caught here.
- **HTTP errors** (`HTTPError` subclasses `URLError`) — 401s, 403s, 5xx responses.
- **Malformed JSON bodies** (valid HTTP 200 but unparseable body) — caught via `json.JSONDecodeError`.

Return shape: `{"error": "<stringified exception>", "arrivals": []}`. Callers downstream check `stop["error"]` before rendering arrivals.

- **CLI path** (`print_dashboard`): `if stop["error"]: print(f"   ⚠ Error: {stop['error']}")`
- **Web path** (`/api/arrivals` handler + `render()`): the JSON includes `"error"` as a top-level field; the JS renderer emits `<div class="error-msg">⚠ ${esc(stop.error)}</div>` in red.

### Semantic-vs-empty ambiguity (known gap)

A valid HTTP 200 with a well-formed JSON body that **lacks the `Siri` envelope** (e.g. a maintenance-mode response from MTA, an empty `{}`, or a schema change) is **not** caught as an error. The `data.get("Siri", {})…` chain silently yields `[]` for `StopMonitoringDelivery`, which means `visits = []`, which means no arrivals are appended. Downstream code renders this as "No buses currently tracked on this route."

**This looks identical to the bus simply not running.** The build chat flagged this as a concern:

> Semantic failures should not look like empty service. A 200 with a garbled body is still an upstream problem — the user should see "service unreachable" or similar, not a peaceful "no buses right now."

There's no fix in the current code. Auditors should flag this as either a documented limitation or a candidate fix (e.g. check for presence of `Siri.ServiceDelivery` before parsing; if absent, return `{"error": "unexpected response shape", "arrivals": []}`).

### Per-datetime-field parse errors

In the visit-parse loop, `datetime.fromisoformat(raw)` is wrapped in a local try-except:

```python
try:
    expected_arrival = datetime.fromisoformat(raw)
except (ValueError, TypeError):
    pass
```

A single bad ISO string doesn't kill the whole response — that arrival just ends up with `expected_arrival = None` and `minutes_away = None`, and the gating logic falls through to "time unknown." This is the right granularity: one bus reporting a bad timestamp shouldn't blank out every other bus at the stop.

### Client-disconnect — silently swallow

The web `do_GET` handler wraps the response-write path in:

```python
try:
    # … build and write response
except BrokenPipeError:
    pass  # Browser closed connection early — harmless
```

Why: a user closing a browser tab mid-response, or a fetch being aborted by the next refresh tick, can cause `self.wfile.write` to raise `BrokenPipeError`. This is not a bug, it's a normal HTTP lifecycle event. The default `BaseHTTPRequestHandler` behavior is to dump a traceback to stderr; the explicit catch plus `log_message` override (see `06_cli_and_web_modes.md`) keeps the console clean.

**Note:** only `BrokenPipeError` is caught here. Other exceptions inside `do_GET` (JSON serialization failures, handler bugs, etc.) will still produce the default 500 behavior with traceback logging. That's intentional — real bugs should be loud.

## Error messaging style

All user-facing error strings share a style:

- Prefix with `ERROR:` in all caps (startup errors) or `⚠` emoji (per-stop fetch errors).
- One-line headline, then a blank line, then instructions.
- Instructions use numbered lists (`1.`, `2.`, `3.`) when multiple remediation paths exist, with command-line snippets the user can copy verbatim.
- URLs are bare (`https://register.developer.obanyc.com/`), not embedded in prose.

The 2026-04-10 chat describes this as "copy-paste-ready diagnostics" — the user should not need to read the README to fix a startup error; the error message itself should be sufficient.

## Spec-auditor focus

- **Startup errors must be reached before any network call.** If `fetch_all_stops` runs with no API key and produces a 401 from SIRI, the user's error message comes from MTA, not from bus-tracker. Ordering of checks in `main` matters: config → API key → fetch.
- **`sys.exit(1)` must actually be reached** on each startup error. A `return` instead of `sys.exit` leaves `main` unfinished but exits 0, which masks the failure in CI / scripting contexts.
- **`{"error": ..., "arrivals": []}` shape must be preserved** across refactors. Callers dereference both keys.
- **`BrokenPipeError` catch must be scoped to the response-write path**, not wrapped around the API fetch. A too-broad catch would swallow a real SIRI connection failure.
- **`json.JSONDecodeError` in `load_config` should NOT be caught.** The intentional-unhandled property is part of the design (loud corrupt-config behavior). Adding a handler would be a regression.
- **`datetime.fromisoformat` try/except must be per-field, not per-response.** Widening the catch to wrap the entire visit loop would turn one bad timestamp into an empty stop.
- **`--web` mode's `KeyboardInterrupt` path must call `server.server_close()`**, not just print. Leaving the socket bound causes `OSError: [Errno 48] Address already in use` on immediate restart.

## What's NOT handled

- No retry / backoff on transient errors. A timeout or 5xx produces a single visible error and the user waits for the next refresh.
- No rate-limit-aware backoff. If MTA returns 429, the user sees the error string; the next 30-second tick tries again.
- No health-check endpoint. There's no way to ask the web server "is the upstream API reachable right now" short of waiting for `/api/arrivals` to return.
- No structured logging. Errors are printed to stderr (startup) or returned as dict fields (runtime); there's no log file, no log level, no JSON-lines output.
- No per-stop error isolation beyond the fetch layer. If `fetch_all_stops` itself crashes (e.g. a bug in the loop, not in a specific stop's API call), the whole dashboard request 500s / the whole CLI run aborts.

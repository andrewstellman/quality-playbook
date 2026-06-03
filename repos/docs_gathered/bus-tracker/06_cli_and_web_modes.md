# 06 — CLI Mode vs Web Mode

**Source:** `bus_tracker.py::main` + `print_dashboard` + `run_web` + `make_handler` + HTML template. README quickstart and 2026-04-10 build chat confirm intent.

## Two invocation modes, one code path for data

Bus-tracker has a single entry point (`main`) that selects between two display modes based on the `--web` flag:

| Flag | Mode | Behavior |
|---|---|---|
| *(absent, default)* | CLI one-shot | Prints a formatted text dashboard to stdout and exits. |
| `--web` | Web dashboard | Starts a local HTTP server that renders the same data as an auto-refreshing HTML page. |

**Both modes share the same `fetch_all_stops` data path and the same gating logic** (see `05_walk_time_gating.md`). The formatting layer differs; the logic doesn't.

## CLI mode

Invoked as:

```
python bus_tracker.py            # default mode
python bus_tracker.py --key K    # override API key for this run
python bus_tracker.py --config path/to/custom.json
```

`print_dashboard(api_key, config)` does the work:

1. Prints a header with `title`, current timestamp (`%I:%M %p, %A %B %d`), optional `subtitle`, and an optional `(includes +N min cushion)` note.
2. Calls `fetch_all_stops` to hit the SIRI API for every configured stop.
3. For each stop, prints the label, direction line, walk minutes, and up to 4 arrivals formatted by `format_arrival`.
4. Error stops print `⚠ Error: <message>`; stops with no tracked buses print `No buses currently tracked on this route.`
5. Exits when done — no loop, no re-fetch.

This is the "quick terminal check" mode. Re-running it is how you refresh.

## Web mode

Invoked as:

```
python bus_tracker.py --web              # port 5555 (default)
python bus_tracker.py --web --port 8080  # custom port
```

`run_web(api_key, config, port)` does the work:

1. Calls `make_handler` to build a `BaseHTTPRequestHandler` subclass with `api_key`, `stops`, `cushion`, `title`, and `subtitle` baked in via closure.
2. Pre-renders the HTML shell (title and subtitle substituted into `HTML_TEMPLATE`). The HTML is `.encode()`d once at startup, not per request.
3. Starts an `HTTPServer(("0.0.0.0", port), handler)` — binds to all interfaces, **not** just localhost. The README frames this as "access from other devices on your LAN."
4. `serve_forever()` blocks. `KeyboardInterrupt` (Ctrl+C) triggers a clean `server.server_close()` and prints `Shutting down.`

**Port default is 5555**, defined in `argparse` (`--port`, `default=5555`). Not a config file value — it's a CLI arg.

### The two HTTP routes

The handler's `do_GET` serves only two paths:

| Path | Content | Use |
|---|---|---|
| `/api/arrivals` | JSON array of stop results | Polled by the browser every 30 s. |
| *(anything else, including `/`)* | The pre-rendered HTML shell | Initial page load. |

**There is no routing table** — the implementation is a two-branch `if/else` on `self.path == "/api/arrivals"`. Any path other than `/api/arrivals` serves the full dashboard HTML, including requests for `/favicon.ico`, `/robots.txt`, etc.

### JSON payload shape

`/api/arrivals` returns a list of stop dicts identical to `fetch_all_stops` output, with one transformation: `arr["expected_arrival"]` is converted from a `datetime` to an ISO-8601 string. All other fields pass through unchanged.

CORS: `Access-Control-Allow-Origin: *` is set on the API route. This is deliberate — the build chat shows Andrew considering whether the dashboard might be embedded in other pages; open CORS is the "least surprising" choice for a local home-use tool.

### Auto-refresh cadence

`REFRESH_MS = 30000` in the embedded JavaScript. The page calls `refresh()` once at load, then `setInterval(refresh, REFRESH_MS)` thereafter. There's also a `Refresh Now` button that calls `refresh()` directly.

**The 30-second cadence is a code constant**, not a config value. Rationale from the build chat: MTA's real-time update cadence is on the order of 15–30 seconds, so polling faster than that wastes API quota without producing fresher data.

### Shared data, different renderer

The web dashboard's JavaScript `render()` function is the client-side counterpart to `format_arrival`. It implements the same four-state gating machine (`action-late` / `action-now` / `action-soon` / `action-go`) and the same `[:4]` arrival cap (`slice(0, 4)`). Both renderers receive the same raw `minutes_away` / `walk_minutes` / `cushion_minutes` fields and compute `need` and `buffer` identically — a parity concern called out in `05_walk_time_gating.md`.

## Stdlib-only constraint

**Bus-tracker has no third-party dependencies.** The only imports are from the Python standard library: `argparse`, `json`, `os`, `sys`, `datetime`, `http.server`, `pathlib`, `urllib.request`, `urllib.parse`, `urllib.error`.

The build chat documents this as an explicit design decision: the project should install with nothing but `python3`. No `pip install`, no `requirements.txt`, no virtualenv prerequisites. That's why:

- HTTP serving uses `http.server.BaseHTTPRequestHandler`, not Flask or FastAPI.
- HTTP fetching uses `urllib.request.urlopen`, not `requests` or `httpx`.
- JSON parsing uses the stdlib `json` module, not `orjson` or `ujson`.
- The HTML template is a string literal inside `bus_tracker.py`, not a Jinja2 template or a separate `.html` file. This is why the template uses `{{` / `}}` escaping throughout — it's a Python `str.format()` call with embedded JS/CSS braces.

**Divergence signal:** any `requirements.txt`, `pyproject.toml` with runtime deps, or `import` of a third-party package is a scope violation. The only acceptable additions are dev-only tooling (pytest, ruff, etc.) kept out of the runtime import graph.

## `log_message` override

`Handler.log_message` is overridden to a no-op (`pass`). Without this, every GET would print a line to stderr (`127.0.0.1 - - [...] "GET / HTTP/1.1" 200 -`). The dashboard polls every 30 s indefinitely; leaving the default behavior would produce a log spam that obscures the only two messages we care about — the startup banner and `Shutting down.`

## Spec-auditor focus

- **`--web` without `--port` must default to 5555.** The `argparse` default is authoritative; don't let a refactor accidentally read a port from config.
- **Port must bind to `0.0.0.0`**, not `127.0.0.1`. The documented intent is "LAN access from your phone," which localhost-only would break.
- **CLI mode must not start a server.** A code path that calls `run_web` when `--web` is absent would be a behavioral divergence.
- **`/api/arrivals` route must be exact-match** (`self.path == "/api/arrivals"`). A `startswith` or regex match could accidentally serve JSON to `/api/arrivals-old` or similar.
- **Datetime → ISO string conversion** happens before `json.dumps`. A missed conversion crashes the request with `Object of type datetime is not JSON serializable`.
- **`setInterval` must fire with `REFRESH_MS` unchanged from 30000.** Changing this to a smaller value (5000, 10000) pushes the user closer to API rate limits. The build chat specifically called out 30 s as the correct value for MTA cadence.
- **No third-party runtime imports.** A stray `import requests` breaks the zero-dependency promise.

## What's NOT in the modes

- No daemon / background-service mode. The user is expected to run the script manually and kill it with Ctrl+C.
- No HTTPS — the web server is plain HTTP. Rationale: intended for LAN-only use; the MTA API key never touches the browser (it's used server-side to hit SIRI, then the server returns pre-resolved arrivals to the client).
- No authentication on the web server. Anyone on the LAN who can reach the port gets the dashboard. For a personal bus tracker on a home network, this is considered acceptable by the build chat.
- No multiple-page UI — `/api/arrivals` is the only JSON endpoint, and everything else serves the single dashboard HTML.

# bus-tracker Documentation Index — Behavioral Specification

**Generated:** 2026-04-10
**Restructured:** 2026-04-21 (chat dump → six topical docs)
**Purpose:** Curated specification material for the `bus-tracker` benchmark target — a tiny MTA-SIRI arrival tracker used in QPB for fast parallel `--full-run` exercises.
**Target use:** Specification auditing: comparing actual code behavior in `clean/bus-tracker/` against documented intent captured here.

---

## Document Overview

The collection is intentionally compact. The repo itself is one 491-line standard-library Python file (`bus_tracker.py`), one README, and one example config. The documented intent lives in the README plus the 2026-04-10 Cowork build chat; this INDEX points at the **topical extracts** of both.

Documents should be read in numeric order. `01` sets context (what the tool does); `02`–`07` are the concrete behavioral spec (how it does it, and what must stay true across refactors).

---

## Document List

### 1. `01_project_readme.md`

**Content:** Verbatim copy of `clean/bus-tracker/README.md`.

**Key topics:**
- Project purpose and feature summary (CLI + dark-themed web dashboard)
- Setup: MTA API key acquisition, environment variable vs `.api_key` file
- Config file schema pointer
- Stop-ID discovery options (bustime.mta.info URLs, stops-for-location API, physical signs)
- Usage: `python3 bus_tracker.py`, `--web`, `--port`, `--config`
- "No dependencies" constraint (standard library only)

**Spec-auditor focus:** high-level conformance to user-facing documentation. Use as the authoritative source for "what the README says the tool will do."

---

### 2. `02_siri_api_endpoint.md`

**Content:** The MTA SIRI StopMonitoring HTTP integration.

**Key topics:**
- Why SIRI StopMonitoring was chosen over VehicleMonitoring, OneBusAway REST, and GTFS-Realtime
- Base URL constant `SIRI_BASE = "https://bustime.mta.info/api/siri/stop-monitoring.json"`
- Required params (`key`, `MonitoringRef`, `version=2`, `StopMonitoringDetailLevel=normal`) and optional `LineRef` with its critical `MTA NYCT_<ROUTE>` space
- Response-walking path: `Siri.ServiceDelivery.StopMonitoringDelivery[0].MonitoredStopVisit[]`
- Field extraction order (Expected > Aimed arrival time; `PublishedLineName` / `DestinationName` as list → first)
- `{"error": ..., "arrivals": []}` structured error shape
- Sort order (`minutes_away` asc, None pushed to end via 9999 sentinel)

**Spec-auditor focus:** URL construction, param encoding, response-walking exactness, and the semantic-vs-empty ambiguity when a 200 returns an unexpected body.

---

### 3. `03_api_key_resolution.md`

**Content:** Three-path key resolution with explicit precedence.

**Key topics:**
- Order: `--key` CLI arg → `MTA_API_KEY` env → `.api_key` file → None
- `.api_key` is script-relative (`Path(__file__).parent`), tolerates trailing newlines
- Missing-key path prints a three-option instructional message and `sys.exit(1)`
- Git hygiene: `.api_key` and `config.json` both gitignored

**Spec-auditor focus:** precedence order, script-relative vs cwd-relative path, instructional error vs silent 401.

---

### 4. `04_config_schema.md`

**Content:** `config.json` schema, defaults, merge behavior.

**Key topics:**
- Top-level: `title` (str), `subtitle` (str), `cushion_minutes` (int), `stops` (dict)
- Per-stop: `stop_id` (`MTA_NNNNNN`), `route_filter` (`MTA NYCT_<ROUTE>` — literal space), `direction` (cosmetic), `walk_minutes` (int, default 5)
- Stop map **key** is the display label
- Missing file / empty stops → `sys.exit(1)` with pointer to `config.example.json`
- User config shallow-merged over `DEFAULT_CONFIG`

**Spec-auditor focus:** format rules that currently silently no-match (malformed stop_id, dash-instead-of-space in route_filter), empty-stops fatal behavior, no port/refresh/theme in config.

---

### 5. `05_walk_time_gating.md`

**Content:** The 4-state buffer machine that powers both CLI and web action labels.

**Key topics:**
- `need = walk_minutes + cushion_minutes`; `buffer = minutes_away - need`
- Four buckets evaluated top-down: `buffer < 0` → too late; `< 2` → leave NOW; `< 5` → leave soon; else → plenty
- Thresholds `0`, `2`, `5` are hardcoded (no config override)
- `minutes_away is None` → "time unknown" (no gating)
- `minutes_away < 1` → "arriving now" but still gated (usually bucket 1)
- `cushion_minutes` applied uniformly across stops
- Up to 4 arrivals per stop (`[:4]` / `slice(0, 4)`)

**Spec-auditor focus:** bucket order top-down, CLI/web parity, `cushion_minutes` uniform application, threshold constants matching between CLI and web.

---

### 6. `06_cli_and_web_modes.md`

**Content:** CLI one-shot vs `--web` dashboard. Shared data path, two renderers.

**Key topics:**
- Entry point selects mode based on `--web` flag
- CLI: `print_dashboard` → one-shot, no loop, re-run to refresh
- Web: `run_web` → `HTTPServer("0.0.0.0", port)`, pre-rendered HTML shell, two routes (`/api/arrivals` vs everything else)
- Port default `5555` (argparse), bind `0.0.0.0` (LAN access intentional)
- `REFRESH_MS = 30000` in embedded JS — 30-second poll cadence matches MTA upstream
- Stdlib-only: `http.server`, `urllib`, `json`, `datetime`; no Flask, no requests
- `log_message` overridden to no-op to silence access log spam

**Spec-auditor focus:** port default, `0.0.0.0` bind, exact `/api/arrivals` route match, 30 s cadence constant, no third-party runtime imports.

---

### 7. `07_error_handling.md`

**Content:** Three error classes — startup (fatal), upstream (structured), client disconnect (silent).

**Key topics:**
- Startup fatals (exit 1): missing `config.json`, empty stops, no API key — each with instructional messaging
- Intentionally unhandled: `json.JSONDecodeError` in `load_config` (loud corrupt-config)
- Upstream: `(URLError, json.JSONDecodeError)` → `{"error": str(exc), "arrivals": []}`
- Per-field `datetime.fromisoformat` try/except keeps one bad timestamp from killing a whole stop
- `BrokenPipeError` in `do_GET` silently swallowed (tab closed during response)
- Known gap: 200 with malformed body looks like "no buses currently tracked"

**Spec-auditor focus:** fatal-before-network ordering, `sys.exit(1)` actually reached, structured-dict shape stability, scope of `BrokenPipeError` catch, semantic-vs-empty gap as documented limitation vs regression.

---

## Critical behaviors to verify (cross-document)

When auditing `bus-tracker` code against these docs, the highest-value checks are:

1. **API key resolution order** (03): CLI → env → file. Any reorder is a silent behavior change.
2. **Stop / route ID formats** (04): `MTA_NNNNNN` and `MTA NYCT_<ROUTE>` with literal space. Malformed values currently silent-no-match.
3. **4-state walk-time gating** (05): bucket order top-down; thresholds 0/2/5 hardcoded and matching across CLI and web.
4. **Default port 5555** (06), bind `0.0.0.0`, 30-second refresh cadence.
5. **Zero-dependency constraint** (06): no imports outside the standard library at runtime.
6. **Fatal startup errors** (07): missing config, empty stops, missing key all exit 1 with instructional messages — before any network request.
7. **Structured upstream errors** (02, 07): `{"error": ..., "arrivals": []}` shape preserved; semantic-vs-empty gap noted.

---

## Known limitations of this collection

- **No RFCs or external protocol specs.** SIRI is documented by the MTA Bus Time wiki (linked in the README), not via formal RFC. The README and chat extracts are sufficient primary sources; no deep protocol audit is expected here.
- **No GitHub discussion threads.** The project is single-author with no public issue tracker activity worth citing.
- **Single build session.** Unlike `chi` or `httpx`, there is no multi-year changelog. The authoritative history is one 2026-04-10 chat (preserved at `_raw/project_chat_history.md`) and the current main branch.

These are features, not defects: `bus-tracker` exists to exercise QPB end-to-end quickly on a target with a compact, fully-captured documented intent.

---

## Last updated

2026-04-21 — split the single-file chat dump into six topical docs to reduce Phase 1/2 token cost.

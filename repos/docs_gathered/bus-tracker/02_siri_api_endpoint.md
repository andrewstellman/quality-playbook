# 02 — MTA SIRI StopMonitoring API

**Source:** MTA Bus Time developer docs + 2026-04-10 build chat (see `_raw/project_chat_history.md`).

## Endpoint selection

Bus-tracker uses the MTA Bus Time **SIRI StopMonitoring** endpoint, not the alternatives that were evaluated during the build:

- **SIRI StopMonitoring** *(chosen)* — "real-time information about vehicles serving a particular stop."
- SIRI VehicleMonitoring *(rejected)* — vehicle-centric; requires you to know which vehicles serve your stop.
- OneBusAway REST API *(rejected after test)* — the chat documents an attempt with `TEST_KEY` that failed; the SIRI endpoint was used instead.
- GTFS-Realtime *(rejected)* — heavier, protobuf-based, more appropriate for route-wide analysis than per-stop polling.

**Design-intent claim:** bus-tracker is a per-stop real-time client. SIRI StopMonitoring is the intended endpoint. If the code calls VehicleMonitoring, OneBusAway REST, or GTFS-RT, that is a divergence from documented intent.

## URL construction

Base URL (constant `SIRI_BASE` in `bus_tracker.py`):

```
https://bustime.mta.info/api/siri/stop-monitoring.json
```

Required query parameters:

| Parameter | Value | Notes |
|---|---|---|
| `key` | API key | Resolved per `03_api_key_resolution.md` |
| `MonitoringRef` | stop ID | Format `MTA_NNNNNN` |
| `version` | `2` | SIRI schema version; must be literal `"2"` |
| `StopMonitoringDetailLevel` | `normal` | Controls response verbosity; `calls` is a richer alternative, but `normal` is what the code specifies |

Optional query parameters:

| Parameter | Value | Notes |
|---|---|---|
| `LineRef` | route filter | Format `MTA NYCT_<ROUTE>` (e.g. `MTA NYCT_B63`). Note the **literal space** between `MTA` and `NYCT_…`. Omitted → all routes at the stop. |

Parameters are URL-encoded via `urllib.parse.urlencode`, so the literal space in `LineRef` serializes as `+` (`MTA+NYCT_B63`), which is what the chat's "Constructed URL" trace confirmed works.

**Concrete example from the build chat:**
```
https://bustime.mta.info/api/siri/stop-monitoring.json?key=TEST_KEY&MonitoringRef=MTA_308210&version=2&StopMonitoringDetailLevel=normal&LineRef=MTA+NYCT_B63
```

## Request headers

The code sends `Accept: application/json` and a 15-second timeout. No auth header — the API key is in the query string. No user-agent customization.

## Response shape

The SIRI response is deeply nested. Bus-tracker walks this path:

```
Siri.ServiceDelivery.StopMonitoringDelivery[0].MonitoredStopVisit[]
```

For each `MonitoredStopVisit`, the code reads `MonitoredVehicleJourney` (`mvj`) and its `MonitoredCall` (`mc`), extracting:

- **Expected arrival time** — first non-null of `mc.ExpectedArrivalTime`, `mc.ExpectedDepartureTime`, `mc.AimedArrivalTime`. Parsed with `datetime.fromisoformat`. The **fallback order is deliberate** — Expected arrival is preferred over Expected departure, and both are preferred over the scheduled (Aimed) time.
- **Distance signals** — `mc.Extensions.Distances.StopsFromCall` (int) and `mc.Extensions.Distances.DistanceFromCall` (meters).
- **Route name** — `mvj.PublishedLineName` (can be a list → take first element).
- **Destination** — `mvj.DestinationName` (can be a list → take first element).
- **Stroller accessibility** — `mc.Extensions.VehicleFeatures.StrollerVehicle` (bool).
- **Progress status** — `mvj.ProgressStatus`.
- **Vehicle id** — `mvj.VehicleRef`.
- **Recorded at** — `visit.RecordedAtTime`.

**Spec-auditor focus:** If the response-walking code takes a different path (e.g. `StopMonitoringDelivery` as an object, not an array; missing `[0]` index; reading `AimedArrivalTime` before `ExpectedArrivalTime`), that's a divergence. The SIRI spec allows arrays; bus-tracker specifically reads the first delivery.

## Error handling

The fetch is wrapped in a `try/except (URLError, json.JSONDecodeError)`. On error, `fetch_stop_arrivals` returns `{"error": <str>, "arrivals": []}` — a structured error with an empty arrival list, not a raised exception. Callers check `stop["error"]` before rendering arrivals.

**Important divergence check:** If a malformed upstream response (valid HTTP 200 but missing `Siri` envelope) produces empty arrivals and a `None` error, downstream code will render it as "no buses currently tracked" — indistinguishable from the bus simply not running. The build chat flagged this as a concern ("semantic failures should not look like empty service"); look for explicit detection of semantic-vs-empty in the parse path.

## Sort order

Arrivals are sorted by `minutes_away` ascending, with `None` pushed to end via `9999` sentinel. Callers generally show only the top 4.

## What's out of scope

- No SIRI authentication beyond the `key=` query parameter.
- No retry/backoff on 5xx or timeout; the current error path is "report and show no buses."
- No pagination — a single request returns all upcoming arrivals for the stop.
- No local caching — every call hits the API.

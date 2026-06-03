# 04 — config.json Schema

**Source:** `bus_tracker.py::load_config` + `DEFAULT_CONFIG` + `config.example.json` + README + 2026-04-10 build chat.

## File location and discovery

By default, bus-tracker reads `config.json` **next to the script** (`Path(__file__).parent / "config.json"`). The `--config <path>` CLI flag overrides this with an explicit path.

If the default-location file doesn't exist, bus-tracker prints a pointer to `config.example.json` and exits with status 1. **Missing config is an explicit fatal error, not a "fall back to defaults" situation** — the stop list is personal and there is no meaningful default.

The file is parsed as JSON with `json.load`; invalid JSON raises and propagates (intentional: corrupt config should be loud).

## Top-level fields

The schema is a flat dict with these keys:

| Key | Type | Default | Purpose |
|---|---|---|---|
| `title` | string | `"MTA Bus Tracker"` | Dashboard title (CLI header and web `<title>`/`<h1>`). |
| `subtitle` | string | `""` | Small text below the title on the dashboard. |
| `cushion_minutes` | int | `0` | Extra safety margin added to every stop's `walk_minutes` when computing the "hurry" label. |
| `stops` | dict | `{}` | Map of stop label → stop config. **Must be non-empty or the process exits.** |

Defaults come from `DEFAULT_CONFIG` in `bus_tracker.py`. User config is merged over defaults with `{**DEFAULT_CONFIG, **cfg}` — a shallow merge, so top-level keys the user supplies fully replace defaults.

## Per-stop schema

Each entry under `stops` is a dict:

| Key | Type | Required | Format | Purpose |
|---|---|---|---|---|
| `stop_id` | string | yes | `MTA_NNNNNN` | The MTA stop id; passed as `MonitoringRef` to the SIRI API. |
| `route_filter` | string | no | `MTA NYCT_<ROUTE>` (literal space) | Restricts arrivals to one route; passed as `LineRef`. Omit for all routes. |
| `direction` | string | no | free text | Friendly label shown above arrivals; cosmetic only. |
| `walk_minutes` | int | effectively required | int ≥ 0 | Used by the gating math in `05_walk_time_gating.md`. If absent, `fetch_all_stops` defaults to `5`. |

**Format rules to verify:**
- `stop_id` must be the literal string `MTA_` followed by digits. The code does not validate this, but the SIRI endpoint will return empty / error for malformed ids.
- `route_filter` MUST contain a space between `MTA` and `NYCT_<ROUTE>`. URL-encoding serializes this correctly. A dash or underscore instead of the space is a silent-no-match bug.
- `direction` is not parsed — it's passed through as-is to the dashboard.

## Stop label semantics

The **key** in the `stops` map (e.g. `"B63 — 5th Ave & Saint John's Pl"`) is the display label. It can contain any JSON-safe string. The code uses it as a stable identifier for the stop card in the UI.

Because the label is the map key, **labels are unique per config**. Two B63 stops would need distinct labels.

## Example

```json
{
  "title": "My Bus Tracker",
  "subtitle": "Morning commute",
  "cushion_minutes": 2,
  "stops": {
    "B63 — 5th Ave & Saint John's Pl": {
      "stop_id": "MTA_308210",
      "route_filter": "MTA NYCT_B63",
      "direction": "Southbound toward Bay Ridge",
      "walk_minutes": 4
    },
    "B67 — 7th Ave & Berkeley Pl": {
      "stop_id": "MTA_305672",
      "route_filter": "MTA NYCT_B67",
      "direction": "Southbound",
      "walk_minutes": 6
    }
  }
}
```

## Finding stop IDs

The README documents three methods (`bustime.mta.info` URL inspection, the `stops-for-location` API, physical stop signs). The build chat used the first two to discover the example stop IDs above.

## Spec-auditor focus

- **Empty stops map** must exit with status 1 and a clear message. A "no stops configured, running with zero stops" empty dashboard would be a divergence.
- **Missing config.json** must exit with a pointer to `config.example.json`, not crash with a `FileNotFoundError`.
- **Invalid JSON** should propagate a clear error, not silently fall back to defaults.
- **Malformed `stop_id`** (e.g. `"308210"` without the `MTA_` prefix) currently silently produces empty arrivals from the SIRI endpoint. Whether this is considered a bug depends on your standard — the README documents the format, but the code doesn't enforce it.
- **`route_filter` with dash instead of space** (e.g. `"MTA_NYCT_B63"`) is a common misformat and currently silent-no-match — also a likely "should fail fast" candidate.

## What's NOT in the config

- No API key (that's in env or `.api_key`, not config — see `03_api_key_resolution.md`).
- No port, no dashboard refresh interval, no HTML theme — those are code constants.
- No upstream URL override — `SIRI_BASE` is a module constant.

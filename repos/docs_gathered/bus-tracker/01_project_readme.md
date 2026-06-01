# MTA Bus Tracker

Real-time NYC bus arrival predictions using the [MTA Bus Time](https://bustime.mta.info/) SIRI API. Configure the stops you care about, and the tracker tells you exactly when to leave the house.

Features a CLI mode for quick terminal checks and a dark-themed web dashboard that auto-refreshes every 30 seconds (works great on your phone).

## Setup

### 1. Get a free MTA API key

Register at <https://register.developer.obanyc.com/> (takes a few minutes).

Save your key using one of these methods:

```bash
# Option A: environment variable
export MTA_API_KEY=your_key_here

# Option B: key file (in this folder)
echo "your_key_here" > .api_key
```

### 2. Configure your stops

Copy the example config and edit it with your stops:

```bash
cp config.example.json config.json
```

Edit `config.json` with the MTA stop IDs for the bus stops you want to monitor. Each stop needs:

| Field | Description |
|-------|-------------|
| `stop_id` | MTA stop ID (format: `MTA_123456`) |
| `route_filter` | Route to filter for (format: `MTA NYCT_B63`) — optional |
| `direction` | Friendly label for the direction |
| `walk_minutes` | How long it takes you to walk to this stop |

#### Finding stop IDs

You can find stop IDs by:
- Visiting <https://bustime.mta.info/> and searching for your route — stop IDs appear in the URLs
- Using the MTA's [stops-for-location API](https://bustime.mta.info/wiki/Developers/OneBusAwayRESTfulAPI):
  ```
  https://bustime.mta.info/api/where/stops-for-location.json?lat=YOUR_LAT&lon=YOUR_LON&latSpan=0.005&lonSpan=0.005&key=YOUR_KEY
  ```
- Checking the stop code posted at the physical bus stop sign

## Usage

```bash
# Quick check from the terminal:
python3 bus_tracker.py

# Web dashboard (auto-refreshes every 30s):
python3 bus_tracker.py --web

# Custom port:
python3 bus_tracker.py --web --port 8080

# Custom config location:
python3 bus_tracker.py --config /path/to/config.json
```

The web dashboard runs at `http://localhost:5555` by default.

## How it works

The tracker calls the MTA's SIRI StopMonitoring API to get real-time vehicle positions and arrival predictions for your configured stops. For each approaching bus, it compares the estimated arrival time against your walk time and tells you whether you have time, need to leave soon, or have already missed it.

## No dependencies

Uses only the Python standard library — no `pip install` needed.

## License

MIT

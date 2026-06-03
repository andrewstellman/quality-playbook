# 03 — API Key Resolution

**Source:** `bus_tracker.py::load_api_key`, README, 2026-04-10 build chat.

## Three resolution paths, with explicit precedence

Bus-tracker resolves the MTA API key by checking three sources in this fixed order. The first non-empty value wins:

1. **`--key` CLI argument** — highest precedence. Used for one-off invocations and for overriding environment or file state during testing.
2. **`MTA_API_KEY` environment variable** — the normal path for shell users (matches the README's "Option A" recommendation).
3. **`.api_key` file in the script's directory** — the persistent no-shell-config path (README's "Option B").

If **all three are empty**, the process exits with a clear instructional error (see below), not a silent failure.

## The exact logic

Pseudocode of `load_api_key`:

```
if cli_key: return cli_key
if os.environ.get("MTA_API_KEY"): return that
if .api_key file exists: return its contents (stripped)
return None
```

The `.api_key` file content is read with `.read_text().strip()`, so trailing newlines are tolerated. No interpolation, no comments — the file is the key, nothing else.

**Path resolution note:** the `.api_key` file is looked up **next to `bus_tracker.py`**, not in the current working directory. `Path(__file__).parent / ".api_key"` is the concrete path. Running `python3 bus_tracker.py` from a different directory still finds the key if it's beside the script.

## Missing-key handling

If `load_api_key` returns `None` after all three paths, `main()` prints:

```
ERROR: No API key found.

Get a free key at: https://register.developer.obanyc.com/

Then do one of:
  1. export MTA_API_KEY=your_key_here
  2. echo 'your_key_here' > .api_key
  3. python bus_tracker.py --key your_key_here
```

…and exits with status 1. This is **deliberate** — the build chat documents the "TEST" / "TEST_KEY" attempt failing, which motivated clear missing-key messaging.

**Design-intent claim:** missing-key should **never** produce a silent 401 that looks like "the bus isn't running." It should produce an instructional error before a single network request is made.

## Git hygiene

The `.api_key` file is gitignored. So is `config.json`. The build chat walks through this in detail: Andrew's real stop IDs and walk times were moved out of the source file into `config.json` precisely because the personal-location information shouldn't land in a public repo. `config.example.json` is the committed template.

## Spec-auditor focus

- Does the code actually resolve in CLI → env → file order? A swapped order (file → env) would be a silent divergence.
- Does a missing key produce an instructional error, or a 401 from the SIRI server, or a silent "no buses" rendering?
- Does `.api_key` resolution use `Path(__file__).parent` (script-relative) rather than `cwd`-relative? CWD-relative would break when the script is invoked from a different directory.
- Does the error message actually list all three recovery paths, not just one?
- Is the `.api_key` file gitignored alongside `config.json`?

## What's explicitly NOT supported

- No keyring / credential-store integration (scope was deliberately kept to the standard library).
- No URL-embedded credentials, no Basic auth, no OAuth — SIRI auth is purely the `key=` query parameter.
- No rotation or expiry handling — the same key is used for every request; if the user's key is revoked, the user re-gets it from the MTA and updates env/file.

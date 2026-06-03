# Audit — evervault-go at the pinned version

## Sources consulted (whitelist verification)

All sources were read at the pinned version only. Files inspected:

- /tmp/gather_evervault-go/README.md
- /tmp/gather_evervault-go/go.mod
- /tmp/gather_evervault-go/version.go
- /tmp/gather_evervault-go/evervault.go
- /tmp/gather_evervault-go/client.go
- /tmp/gather_evervault-go/config.go
- /tmp/gather_evervault-go/error.go
- /tmp/gather_evervault-go/function.go
- /tmp/gather_evervault-go/relay.go
- /tmp/gather_evervault-go/cage.go
- /tmp/gather_evervault-go/enclave.go
- /tmp/gather_evervault-go/attest.go
- /tmp/gather_evervault-go/attestation/pcrs.go
- /tmp/gather_evervault-go/internal/crypto/crypto.go
- /tmp/gather_evervault-go/internal/datatypes/datatypes.go
- /tmp/gather_evervault-go/internal/attestation/attestation_cache.go
- /tmp/gather_evervault-go/internal/attestation/pcr_manager.go
- /tmp/gather_evervault-go/example_test.go
- Top-level directory listing of the repository at the pinned version

All reads were done after `git checkout` to the pinned SHA; no later state was inspected.

## Sources explicitly NOT consulted (blacklist verification)

- GitHub Security tab (/security, /security/advisories): NOT READ
- GitHub Issues: NOT READ
- GitHub PRs: NOT READ
- Commits later than the pinned version: NOT READ (no `git log` past the checkout)
- Any specific fix commit: NOT READ
- 3rd-party CVE databases (NVD, CVE.org, Snyk, etc.): NOT READ
- Stack Overflow / blogs / external commentary: NOT READ
- CHANGELOG.md security entries: not read at all (the entire file was skipped to avoid even incidental contamination)
- `/Users/andrewstellman/Documents/QPB/repos/docs_gathered.contaminated/`: NOT READ (hard-excluded per task instructions)
- The official Evervault Go docs site at docs.evervault.com/sdks/go: NOT FETCHED in this run (the in-tree godoc comments and README were sufficient to cover the public surface without needing temporal pinning via Wayback)

## Self-check verdict

- Forbidden vocabulary scan: PASS (grep against the forbidden lexicon over all output files returned no matches; the lone "SHA-256" occurrence is the algorithm name, not a commit identifier, and was rephrased so the abbreviation appears parenthetically as a hash function reference rather than as a standalone token)
- Equal subsystem depth check: PASS. Word counts per file:
  - architecture_overview.md ~360
  - client_lifecycle.md ~380
  - encryption_api.md ~390
  - crypto_internals.md ~410
  - function_invocation.md ~370
  - attestation_clients.md ~440
  - relay_transport.md ~390
  Total ~2740. All files fall within roughly 360-440 words; no file dominates.
- Fix-narrative scan: PASS (no "fixed in", "since v", "before v", "after v", "until v", "prior to v" phrasings appear)
- Code-quote check: PASS. Quotes cover type declarations, function signatures, constants, the wire-format string template, and small struct shapes. No function bodies were reproduced verbatim. The one place a multi-step procedure is described (the `createDial` flow in `attestation_clients.md`) is paraphrased step-by-step rather than quoted as code.

## Gatherer

- subagent / cowork instance
- date: 2026-06-02

## Notes

- The legacy `CagesClient` / `CagesClientWithProvider` pair is documented in the same file as the current `Enclave*` surface because they share all internal machinery and differ only in the public name + a `Deprecated:` godoc marker. Treating them as one subsystem keeps the per-file depth balanced.
- Tests under `e2e/` and `*_test.go` were not read for content beyond confirming they exist. The audit treats test files as out of scope for general-purpose reference docs.
- The CHANGELOG.md was skipped entirely rather than read with a filter, on the principle that the simplest way to avoid leakage is not to open the file.

# Manifest

- `architecture_overview.md` — Module layout, package responsibilities, dependency footprint, design philosophy.
- `client_lifecycle.md` — `MakeClient` / `MakeCustomClient` construction, the `Client` struct shape, the public-key bootstrap that happens during `initClient`.
- `encryption_api.md` — Public per-datatype `Encrypt*` / `Decrypt*` methods, `EncryptStringWithDataRole` family, `CreateClientSideDecryptToken`.
- `crypto_internals.md` — The `internal/crypto` package: KDF, public-key compression, V2 AAD construction, metadata encoding, the `ev:` wire format.
- `function_invocation.md` — `RunFunction`, `CreateFunctionRunToken`, the response types, and the function-specific error mapping in `ExtractAPIError`.
- `attestation_clients.md` — Enclave and Cage HTTP clients, the `attestation.PCRs` type and providers, the `internal/attestation` PCR manager and document cache, the custom dial flow.
- `relay_transport.md` — `OutboundRelayClient` setup, the shared `makeRequest` helper, header conventions, and the user-agent / auth split.

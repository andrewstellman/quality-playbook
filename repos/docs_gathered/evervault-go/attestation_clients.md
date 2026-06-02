# Enclave and cage attestation clients

The SDK offers two pairs of client constructors that produce a `*http.Client` whose TLS dialer attests the peer's identity against a set of PCR measurements before any application bytes flow. "Enclave" is the current name; "Cage" is the legacy spelling, kept for backwards compatibility and marked deprecated in godoc.

## Public surface

```go
// attestation/pcrs.go
type PCRs struct { PCR0, PCR1, PCR2, PCR8 string }
func (p *PCRs) Equal(other PCRs) bool
func (p *PCRs) IsEmpty() bool
func BuildStaticPcrProvider(pcrs []PCRs) func() ([]PCRs, error)
```

```go
// enclave.go
func (c *Client) EnclaveClient(hostname string, pcrs []attestation.PCRs) (*http.Client, error)
func (c *Client) EnclaveClientWithProvider(hostname string,
    pcrsProvider func() ([]attestation.PCRs, error)) (*http.Client, error)
func (c *Client) EnclaveTCPConnectionWithProvider(hostname string,
    pcrsProvider func() ([]attestation.PCRs, error)) (
    func(ctx context.Context, network, addr string) (net.Conn, error), error)

// cage.go (deprecated mirror)
func (c *Client) CagesClient(hostname string, pcrs []attestation.PCRs) (*http.Client, error)
func (c *Client) CagesClientWithProvider(hostname string,
    pcrsProvider func() ([]attestation.PCRs, error)) (*http.Client, error)
```

A caller can either supply a static slice of `PCRs` or hand in a `pcrsProvider` callback that the SDK polls periodically. The static variant is sugar around `BuildStaticPcrProvider`. Each `PCRs` value covers four registers (PCR0, PCR1, PCR2, PCR8) — the subset Evervault attests on.

## Internals

Two internal types coordinate state:

- `internal/attestation.PCRManager` — an interface with a single method `Get() *[]attestation.PCRs`. Two implementations: `StaticProvider` (returns a fixed slice) and `PollingProvider` (background ticker calls the supplied callback every `AttestationPollingInterval`, guards the slice with a `sync.RWMutex`, and exposes `StopPolling`).
- `internal/attestation.Cache` — caches the latest attestation document fetched from `https://{hostname}/.well-known/attestation`. Polls on the same interval, retries up to 3 times with exponential backoff, and is mutex-guarded.

## Connection flow

`Client.createDial` (in `attest.go`) builds the custom dial function:

1. Reject any network other than `tcp` (`ErrUnsupportedNetworkType`).
2. Open a TCP connection with a 5 s `net.DialTimeout`.
3. Wrap it in `tls.Client` using a `tls.Config` with `MinVersion: tls.VersionTLS12`, `ServerName: hostname`, and `InsecureSkipVerify: false`. Perform the handshake.
4. Pull the peer's leaf certificate; pull the latest cached attestation document.
5. Call `attestCert(cert, expectedPCRs, doc)`. That function calls `nitrite.Verify` on the attestation document, checks `SignatureOK`, runs `verifyPCRs` (which returns true if *any* expected PCR set equals the document's PCRs via `PCRs.Equal`), and finally checks that the certificate's marshaled public key bytes equal the attestation document's `UserData`.
6. If attestation fails, reload the document (with a 30 s timeout) and retry once. Persistent failure surfaces as `ErrAttestionFailure`.

The resulting `*http.Client` is wired with `Transport: &http.Transport{DisableKeepAlives: true, DialTLSContext: dial}` so each request re-attests on a fresh connection.

`filterEmptyPCRs` removes zeroed entries before the dial closure runs, and if the filtered slice is empty the constructor returns `ErrNoPCRs` rather than building a client that would attest against nothing.

Word count: ~440

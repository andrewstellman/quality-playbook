# Outbound Relay and HTTP transport

The Outbound Relay client lets a caller send arbitrary outbound HTTP traffic through Evervault's relay infrastructure, where encrypted fields embedded in request bodies are decrypted in flight before the request reaches its destination.

## Public surface

```go
// relay.go
func (c *Client) OutboundRelayClient() (*http.Client, error)
```

Returns a `*http.Client` that has been pre-configured to proxy through `Config.RelayURL` and to trust the Evervault CA. Typical usage:

```go
outbound, err := evClient.OutboundRelayClient()
resp, err := outbound.Post("https://example.com/", "application/json", bodyReader)
```

## Construction flow

1. Fetch the Evervault CA certificate from `Config.EvervaultCaURL` over plain HTTP (no body, GET). A non-200 response yields `APIError{Message: "Error making HTTP request"}`.
2. Build a `tls.Config`:
   - `InsecureSkipVerify: false`
   - `RootCAs:` system pool, with the fetched CA appended via `AppendCertsFromPEM`
   - `MinVersion: tls.VersionTLS12`
3. Parse `Config.RelayURL` into a `*url.URL`.
4. Build a `*http.Transport`:
   - `DisableKeepAlives: true`
   - `TLSClientConfig:` the config above
   - `Proxy: http.ProxyURL(relayURL)`
   - `ProxyConnectHeader: http.Header{"Proxy-Authorization": []string{c.apiKey}}`
5. Return `&http.Client{Transport: transport}`.

The `Proxy-Authorization` header carries the API key so the relay can authenticate the tenant. Because keep-alives are disabled, the proxy connection is re-established per request.

## Internal request helper

Most of the SDK's HTTP traffic flows through a small internal helper on the client (`client.go`):

```go
func (c *Client) makeRequest(url, method string, body []byte, useBasicAuth bool) (clientResponse, error)
```

Used by every API call to the Evervault control plane (`/cages/key`, `/decrypt`, `/client-side-tokens`, `/functions/...`, the CA fetch). Two private structs frame it:

```go
type clientRequest struct {
    url, method string
    body        []byte
    appUUID, apiKey string
    useBasicAuth bool
}
type clientResponse struct {
    body        []byte
    contentType string
    statusCode  int
}
```

Headers are set centrally by `setRequestHeaders`. When `useBasicAuth` is true, the SDK sends `Authorization: Basic base64(appUUID:apiKey)`; otherwise it sends `API-KEY: <apiKey>`. Every request also carries `Content-Type: application/json` and `user-agent: evervault-go/<ClientVersion>` (the version constant lives in `version.go`).

GET requests omit the body reader; non-GET requests wrap `clientRequest.body` in `bytes.NewReader`. The HTTP client is constructed fresh per call (`client := &http.Client{}`); there is no global pooled client. Response bodies are read in full with `io.ReadAll` and the response struct is returned by value.

This helper is the single transport choke point for non-attested traffic, so changes to auth or user-agent only need to happen here.

Word count: ~390

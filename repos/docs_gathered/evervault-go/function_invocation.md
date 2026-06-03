# Function invocation

Evervault Functions are server-side handlers a customer registers under their app. The SDK exposes two ways to talk to them: server-side invocation and client-side run-token minting.

## Run-token minting

```go
type RunTokenResponse struct {
    Token string `json:"token"`
}

func (c *Client) CreateFunctionRunToken(functionName string, payload any) (RunTokenResponse, error)
```

Used when a server wants to hand a short-lived token to a browser so the browser can invoke the function directly. The payload is marshaled to JSON and `POST`ed to `Config.EvAPIURL + "/v2/functions/{functionName}/run-token"`. A non-200 response yields a generic `APIError{Message: "Error making HTTP request"}`; a JSON-parse failure wraps the underlying decoder error. On success the `Token` field carries the server-issued JWT-style token.

## Server-side invocation

```go
type FunctionRunResponse struct {
    Status string         `json:"status"`
    ID     string         `json:"id"`
    Result map[string]any `json:"result"`
}

func (c *Client) RunFunction(functionName string, payload map[string]any) (FunctionRunResponse, error)
```

The payload is wrapped in `{"payload": ...}` before being marshaled and `POST`ed to `Config.EvAPIURL + "/functions/{functionName}/runs"` using basic-auth headers. The response body is decoded twice: first into `FunctionRunResponse`, then — if the status field reports `"failure"` — into the dedicated runtime-error type. Three outcomes are possible:

- `Status == "success"` — `FunctionRunResponse` is returned as-is. `Result` holds whatever the function emitted.
- `Status == "failure"` — the body re-parses into `FunctionRuntimeError`, and that error is returned as the second value. The zero `FunctionRunResponse` is the first.
- The body does not parse into either shape — `ExtractAPIError(response.body)` runs and returns whichever specific error type matches the server's `code` field.

`ExtractAPIError` (declared in `error.go`) recognizes two function-specific error codes and lifts them into dedicated Go types:

```go
type FunctionTimeoutError  struct { Message string }
type FunctionNotReadyError struct { Message string }
type FunctionRuntimeError  struct {
    Status    string
    ErrorBody struct{ Message, Stack string }
    ID        string
}
```

`FunctionNotReadyError` corresponds to `functions/function-not-ready` (the function has been idle and is warming up — retry shortly). `FunctionTimeoutError` corresponds to `functions/request-timeout`. Any other code falls through to a plain `APIError{Code, Message}`.

All three error types implement `error` via a stringly `Error()` method, so callers can either inspect the type with `errors.As` or just log `err.Error()`. The runtime-error `Error()` formats as `"Error in Function run <ID>: <inner message>"` to make logs traceable back to the specific run.

Word count: ~370

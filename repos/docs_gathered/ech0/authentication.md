# Ech0 Authentication and Access Control

## Overview

Ech0 supports three authentication mechanisms that are available simultaneously: password-based login producing session tokens, OAuth2 / OIDC third-party login, and WebAuthn passkey login. API automation is covered by a separate access token system with scoped permissions. All token types are encoded as JWTs signed with HMAC-SHA256.

## Token Types

Two token types are distinguished by the `typ` claim in the JWT payload:

- **`session`** — Issued on interactive login. Contains `userid`, `username`, and a configured expiry. Session tokens carry no scope list; they implicitly have full user-level access to all endpoints.
- **`access`** — Issued through the access token management UI. Contains a scoped permission list (`scopes`), an audience claim, and an optional TTL (zero means no expiry). Access tokens are intended for API automation and third-party integrations.

Both types are validated by `jwtUtil.ParseToken`, which verifies the HMAC-SHA256 signature, checks `iss`/`aud` claims, and rejects any token whose `typ` is not one of the two known values.

## Session Tokens

The `CreateClaims(user)` function in `internal/util/jwt` constructs a standard session JWT:

```go
type MyClaims struct {
    Userid   string   `json:"userid"`
    Username string   `json:"username"`
    Type     string   `json:"typ"`
    Scopes   []string `json:"scopes,omitempty"`
    jwt.RegisteredClaims
}
```

Session tokens include a 60-second leeway to accommodate clock skew. The default lifetime is 30 days (configurable via `ECH0_JWT_EXPIRES`).

## Access Tokens and Scopes

Access tokens are created through `CreateAccessClaimsWithExpiry`, which adds an explicit scope list and audience. The full scope set is:

| Scope | Grants |
|---|---|
| `echo:read` | Read posts |
| `echo:write` | Create, update, and delete posts |
| `comment:read` | Read comments |
| `comment:write` | Post comments |
| `comment:moderate` | Approve and delete comments |
| `file:read` | Download files |
| `file:write` | Upload files |
| `profile:read` | Read user profile |
| `admin:settings` | Manage system settings |
| `admin:user` | Manage user accounts |
| `admin:token` | Manage access tokens |

Valid audience values are `public-client`, `cli`, and `integration`.

The `RequireScopes` middleware in `internal/middleware/scope.go` enforces scope checks on protected routes. Session tokens bypass scope checking. Access tokens must carry every scope listed in the middleware invocation and must have a recognized audience.

## JWT Middleware Flow

Every request passes through `JWTAuthMiddleware`. The middleware:

1. Reads the `Authorization: Bearer <token>` header. Falls back to a `?token=` query parameter for browser media requests (audio/video direct links).
2. Parses and validates the JWT.
3. If valid, attaches a `viewer.Context` to the request context using `viewer.AttachToRequest`.
4. For routes that allow anonymous access (public echo queries, page listings, today view, echo detail), an invalid or missing token results in a `viewer.NoopViewer` being attached rather than an HTTP 401.

High-privilege tokens (those bearing any `admin:*` scope) cannot be transmitted via the query parameter mechanism. Only `Authorization: Bearer` headers are accepted for admin-scoped tokens.

## viewer.Context

The `pkg/viewer` package provides a portable identity abstraction that downstream code uses without importing HTTP or JWT packages:

```go
type Context interface {
    UserID()    string
    TokenType() string
    Scopes()    []string
    Audience()  []string
    TokenID()   string
}
```

Functions `viewer.FromContext`, `viewer.MustFromContext`, and `viewer.AttachToRequest` handle storage and retrieval from `context.Context`. `MustFromContext` always returns a non-nil value (falling back to `NoopViewer`) so callers do not need nil checks.

## OAuth2 / OIDC

OAuth2 and OIDC login is handled by `internal/service/user`. The flow produces a short-lived state JWT (10-minute expiry, HMAC-SHA256) that encodes action, user ID, redirect URL, provider name, and a random nonce. The nonce is used for OIDC id_token verification.

`ParseAndVerifyIDToken` uses the `go-oidc/v3` library to fetch the provider JWKS and verify the id_token signature, expiry, audience, and nonce. Both RSA and EC public keys (P-256, P-384, P-521) are supported.

After a successful callback, the identity is stored in the `auth_identity` table and a standard session token is issued to the browser.

OAuth2 provider settings (client ID, client secret, scopes, OIDC issuer, JWKS URL) are stored in the key-value settings table and are manageable from the admin panel without a process restart.

## WebAuthn / Passkey

Passkey registration and login use the `go-webauthn/webauthn` library. The relying party ID (`RPID`) and allowed origins are configured through the admin panel or via `ECH0_AUTH_WEBAUTHN_RP_ID` and `ECH0_AUTH_WEBAUTHN_ORIGINS`.

The challenge/nonce used during registration and authentication is stored in the in-process Ristretto cache with a short TTL via `CacheSetPasskeySession`. On completion, the credential is persisted to the `passkeys` table. Each passkey record stores the credential ID, public key, sign counter, device name, and last-used timestamp. The sign counter is updated on every successful authentication.

After successful passkey login, a standard session token is issued using the same `CreateClaims` path as password login.

## User Roles

Ech0 uses a lightweight role model stored on the `user` record:

- **Owner** — The first registered account. Has full administrative access.
- **Admin** — Accounts promoted by the owner. Can manage settings and users.
- **Regular user** — Can publish posts if granted permission; cannot access admin settings.

Role checks are performed in the service layer rather than in middleware. The `admin:settings` and `admin:user` scopes in access tokens map to the same permission gates as the Admin role for the purposes of API automation.

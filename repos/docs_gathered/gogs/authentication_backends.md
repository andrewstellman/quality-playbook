# Authentication Backends

Gogs identifies users via a local username/password in the `user` table, an external login source through a pluggable `Provider`, or bearer credentials (personal access tokens / HTTP Basic). External backends share one Go interface.

## Provider interface

`internal/auth/auth.go` defines:

```
type Provider interface {
    Authenticate(login, password string) (*ExternalAccount, error)
    Config() any
    HasTLS() bool
    UseTLS() bool
    SkipTLSVerify() bool
}
```

`Authenticate` returns either a populated `ExternalAccount` or `auth.ErrBadCredentials`. `ExternalAccount` carries `Login`, `Name`, `FullName`, `Email`, `Location`, `Website`, and an `Admin` boolean. `Config()` returns the provider's typed configuration; the TLS predicates let the admin UI render the right knobs.

## Auth types

`auth.Type` is an `int` constant so values round-trip through the database without depending on package import order:

```
None=0  Plain=1  LDAP=2  SMTP=3  PAM=4  DLDAP=5  GitHub=6
```

`auth.Name(typ)` returns the human-readable label.

## Provider implementations

Each backend lives in its own sub-package with `provider.go` and `config.go`:

- `internal/auth/ldap/` — LDAP via BindDN search-then-bind (`LDAP`) or direct bind (`DLDAP`); attribute mapping covers username, name, surname, email, and SSH public key.
- `internal/auth/smtp/` — verifies credentials against a remote SMTP server, optionally restricted to a comma-separated `AllowedDomains` list.
- `internal/auth/pam/` — POSIX PAM, with a build-tag stub for platforms without `libpam`.
- `internal/auth/github/` — GitHub.com and GitHub Enterprise OAuth/personal-token flow.

Local username/password lookups happen directly in `db.Users.Authenticate` without going through the provider interface.

## LoginSource store

`internal/db/login_sources.go` defines `LoginSourcesStore` (`Create`, `Count`, `DeleteByID`, `GetByID`, `List`, `ResetNonDefault`, `Save`) and the `LoginSource` model with `Type`, `Name`, `IsActived`, `IsDefault`, `Config` (JSON-encoded provider configuration), and timestamps. The `Provider` field is populated at load time by deserializing `Config`. `DeleteByID` returns `ErrLoginSourceInUse` when at least one user references the source so administrators cannot orphan accounts.

Sources may also live as `.conf` files under `custom/conf/auth.d/`. `login_source_files.go` (`loginSourceFileStore`) loads each file at startup, registers it through the same interface, and round-trips changes back to disk.

## Authentication flow

`db.Users.Authenticate(ctx, username, password, loginSourceID)` is the single entry point used by the web sign-in handler, the API context, and the LFS authenticator:

1. `loginSourceID < 0` — only the local `user` table is consulted.
2. `loginSourceID == 0` — every active login source is tried in turn; the user is auto-provisioned locally if missing.
3. `loginSourceID > 0` — only the named source is tried.

Auto-provisioning calls `db.Users.Create` with `ExternalAccount` fields and stores `LoginType` and `LoginSource` so subsequent logins skip the search.

## Personal access tokens

API requests authenticate via a token in `Authorization: token <value>`, or as the HTTP Basic password against any username. Tokens live in the `access_token` table as SHA-256 hashes; the displayed value is shown only at creation time. `db.AccessTokens` exposes `Create`, `DeleteByID`, `GetBySHA1`, `List`, `Touch`.

## Reverse-proxy authentication

When `[auth] EnableReverseProxyAuthentication = true`, the header named by `ReverseProxyAuthenticationHeader` (default `X-WEBAUTH-USER`) is treated as the authenticated username. With `EnableReverseProxyAutoRegistration` also set, missing users are auto-created.

## Two-factor and cookies

Users may enroll a TOTP authenticator. The enrollment lives in `two_factor`; recovery codes live in `two_factor_recovery_code`. `db.TwoFactors` exposes `Create`, `GetByUserID`, `IsEnabled`, plus recovery-code methods.

After sign-in the web flow writes a session cookie (`go-macaron/session`) and optionally a "remember me" cookie controlled by `[security] CookieRememberName` and `LoginRememberDays`. `[security] CookieSecure` adds the `Secure` attribute.

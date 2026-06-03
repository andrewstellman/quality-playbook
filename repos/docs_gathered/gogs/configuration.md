# Configuration

Configuration is INI-format and loaded with `gopkg.in/ini.v1`. Defaults are embedded; an operator overrides them by editing `custom/conf/app.ini`. The source of truth for sections, keys, types, and defaults is `internal/conf/static.go`, where every section is a typed struct that the loader populates.

## Loading order

`conf.Init(customConf)` runs once during process startup:

1. Read the embedded `app.ini` as the baseline.
2. Locate the custom configuration (an absolute path argument, otherwise `<WORK DIR>/custom/conf/app.ini`). The work dir is whichever of `GOGS_WORK_DIR`, the binary's directory, or the current directory resolves first.
3. Append every `*.conf` file under `custom/conf/auth.d/` so authentication source definitions can live in their own files.
4. Call `MapTo` on the typed structs in `static.go` to bind sections to fields.
5. Perform derived computations: parse `Server.ExternalURL` into `Server.URL`, compute `Server.Subpath`, parse email From addresses, validate SSH minimum key sizes.

## Major sections

- `[server]` — `ExternalURL`, `Domain`, `Protocol` (`http`, `https`, `fcgi`, `unix`), `HTTP_ADDR`, `HTTP_PORT`, `CertFile`, `KeyFile`, `TLS_MIN_VERSION`, `UnixSocketPermission`, `OfflineMode`, `EnableGzip`, `AppDataPath`, `LoadAssetsFromDisk`, `LANDING_URL`.
- `[database]` — `Type` (`postgres`, `mysql`, `sqlite3`, `mssql`, `tidb`), `Host`, `Name`, `Schema`, `User`, `Password`, `SSL_MODE`, `Path`, `MaxOpenConns`, `MaxIdleConns`.
- `[repository]` — `Root`, `ForcePrivate`, `MaxCreationLimit`, `PreferredLicenses`, `DISABLE_HTTP_GIT`, `EnableLocalPathMigration`, `EnableRawFileRenderMode`, `DefaultBranch`, plus nested `[repository.editor]` and `[repository.upload]`.
- `[ssh]` — `DISABLE_SSH`, `SSH_DOMAIN`, `SSH_PORT`, `SSH_ROOT_PATH`, `SSH_KEYGEN_PATH`, `MinimumKeySizeCheck`, `RewriteAuthorizedKeysAtStart`, `START_SSH_SERVER`, `SSH_LISTEN_HOST`, `SSH_LISTEN_PORT`, `SSH_SERVER_CIPHERS`, `SSH_SERVER_MACS`, `SSH_SERVER_ALGORITHMS`. Per-algorithm minimum key sizes come from `[ssh.minimum_key_sizes]`.
- `[security]` — `InstallLock`, `SecretKey`, `LoginRememberDays`, `CookieRememberName`, `CookieUsername`, `CookieSecure`, `EnableLoginStatusCookie`, `LoginStatusCookieName`, `LocalNetworkAllowlist`.
- `[auth]` — `ActivateCodeLives`, `ResetPasswordCodeLives`, `RequireEmailConfirmation`, `RequireSigninView`, `DisableRegistration`, `EnableRegistrationCaptcha`, reverse-proxy header configuration.
- `[session]`, `[cache]`, `[email]`, `[attachment]`, `[release.attachment]`, `[webhook]`, `[markdown]`, `[smartypants]` — subsystem-specific knobs.
- `[cron.*]` — per-job `Enabled`, `Schedule`, `RunAtStart`, plus job-specific options.
- `[git]` and `[git.timeout]` — diff size limits, GC arguments, per-operation timeouts.
- `[api]`, `[prometheus]`, `[other]`, `[log]`, `[log.*]` — paging cap, metrics auth, branding, logger configuration.

## Authentication source files

External login sources can live in the database (managed through the admin UI) or as files under `custom/conf/auth.d/*.conf`. Each file is one source.

## Custom directory layout

```
custom/
├── conf/  (app.ini, auth.d/, gitignore/, label/, license/, locale/, readme/)
├── public/      # shadows embedded assets
└── templates/   # overrides applied on top of embedded templates
```

`AppendDirectories` is wired to `<custom>/templates`, and `macaron.Static` is wired to `<custom>/public` first, so any file dropped into `custom/` shadows the embedded version.

## Run modes and compatibility

`conf.App.RunMode` accepts `dev` or `prod`. Build metadata (`BuildTime`, `BuildCommit`) is injected via `-ldflags`. Windows service support is build-tag gated in `static_minwinsvc.go`. Older key names (`[service]`, `[mailer]`, `APP_NAME`, `ROOT_URL`) are accepted for backward compatibility and translated in `internal/conf/conf.go`.

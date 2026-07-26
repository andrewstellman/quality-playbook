# Remote Cache

Trestle supports referencing OSCAL artifacts by URI in addition to local workspace paths. The remote cache subsystem fetches, caches, and serves these remote references.

## Package Layout

```
trestle/core/remote/
  cache.py             # FetcherBase, concrete fetchers, FetcherFactory
  security.py          # Path and URL security validators
```

## FetcherBase

`FetcherBase` in `trestle/core/remote/cache.py` is the abstract base class for all fetchers:

```python
class FetcherBase(ABC):
    def __init__(self, trestle_root: pathlib.Path, uri: str) -> None: ...
    def _do_fetch(self) -> None: ...   # abstract; fetches from remote source
    def get_oscal(self, model_type: Type[OscalBaseModel]) -> OscalBaseModel: ...
    def get_raw(self) -> bytes: ...
```

On construction, `FetcherBase` ensures the `.trestle/cache/` directory exists (creating it if needed). The default cache expiration is `const.DAY_SECONDS` (86400 seconds). Cache staleness is determined by comparing the modification time of the cached file to the expiration window.

The `_update_cache` method fetches the resource only when the cached copy is absent or stale, or when `force_update=True` is passed. This makes repeated references to the same remote URI cheap at runtime.

## Concrete Fetchers

Four concrete fetchers handle different URI schemes:

| Class | URI Scheme | Transport |
|---|---|---|
| `LocalFetcher` | `file://` or bare path | Local filesystem copy |
| `HTTPFetcher` | `http://`, `https://` | `requests` library with optional HTTP Basic Auth |
| `SFTPFetcher` | `sftp://` | `paramiko` SSH/SFTP |
| `HTTPSFetcher` | (subclass of HTTPFetcher) | HTTPS with TLS |

`HTTPFetcher` accepts username and password either from environment variables or from a `.env` file loaded by `python-dotenv`. Credentials are passed as `HTTPBasicAuth` to `requests`.

`SFTPFetcher` constructs a `paramiko.SSHClient` with `AutoAddPolicy` and connects using credentials resolved from environment variables or the `.env` file. The SFTP get operation writes the remote file into the local cache directory.

## FetcherFactory

`FetcherFactory` in `trestle/core/remote/cache.py` selects the appropriate fetcher based on the URI scheme:

```python
class FetcherFactory:
    @staticmethod
    def get_fetcher(
        trestle_root: pathlib.Path,
        uri: str
    ) -> FetcherBase: ...
```

URI parsing uses the `furl` library for URL decomposition and the standard library `urllib.parse` for scheme detection. Bare paths and `file://` URIs map to `LocalFetcher`; `http://` maps to `HTTPFetcher`; `https://` maps to `HTTPSFetcher`; `sftp://` maps to `SFTPFetcher`.

## Security Validators

`trestle/core/remote/security.py` provides two validator classes used by the fetcher layer:

`PathSecurityValidator` checks that a local file path does not traverse outside the permitted root directory, preventing directory traversal when resolving `file://` URIs or local path references.

`URLSecurityValidator` checks that HTTP/HTTPS URLs do not target private IP address ranges (e.g., 10.x.x.x, 172.16.x.x–172.31.x.x, 192.168.x.x, 127.x.x.x, `::1`). Whether this check is active is controlled by the `get_block_private_ips_config()` function, which reads a configuration flag from the trestle workspace config.

Both validators are used directly by the Jinja authoring command (`author jinja`) as well as by the fetcher classes.

## Cache Directory Structure

Cached files are stored under `.trestle/cache/` within the workspace root. The path within the cache directory is derived from the URI to create a stable mapping. The `const.TRESTLE_CACHE_DIR` constant defines the directory name.

## Integration with ProfileResolver

`ProfileResolver` uses `FetcherFactory` to resolve `href` values in profile `import` statements. A profile may reference an upstream catalog or profile by a local workspace path, an `https://` URL, or an `sftp://` path. The resolver calls `FetcherFactory.get_fetcher(trestle_root, href)` and then calls `get_oscal(model_type)` on the returned fetcher to obtain the in-memory model. The cache layer ensures that repeated resolution of the same upstream reference does not make redundant network calls.

## SSP Inheritance and Remote SSPs

`SSPInheritanceAPI` (in `trestle/core/crm/ssp_inheritance_api.py`) uses `FetcherFactory` to fetch leveraged SSPs referenced by URI. A leveraged SSP may be stored locally in the workspace or at a remote URI, and the fetch-and-cache pattern applies equally in both cases.

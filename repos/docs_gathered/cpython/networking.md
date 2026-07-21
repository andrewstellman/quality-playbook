# CPython Networking and Protocols

## Overview

CPython's standard library provides networking capabilities at multiple levels of abstraction, from raw BSD socket access through application-layer protocol implementations. All networking modules are built on top of the OS socket interface exposed by the `socket` module, with higher-level modules adding protocol framing, authentication, and convenience APIs.

## `socket` — Low-Level Network Interface

`Lib/socket.py` wraps the `_socket` C extension, which translates to the OS Berkeley socket API. The module is available on all modern Unix systems, Windows, and macOS.

**Creating sockets:**
```python
socket.socket(family=AF_INET, type=SOCK_STREAM, proto=0, fileno=None)
```
Address families include `AF_INET` (IPv4), `AF_INET6` (IPv6), `AF_UNIX` (Unix domain), `AF_NETLINK` (Linux), and `AF_TIPC`. Socket types include `SOCK_STREAM` (TCP), `SOCK_DGRAM` (UDP), and `SOCK_RAW`.

**Address representation:**
- `AF_INET`: `(host, port)` tuple, where `host` is a dotted-decimal string or hostname.
- `AF_INET6`: `(host, port, flowinfo, scope_id)` tuple.
- `AF_UNIX`: a string path or `bytes` object.

**Socket methods:** `bind`, `listen`, `accept`, `connect`, `connect_ex`, `send`, `sendall`, `sendto`, `recv`, `recvfrom`, `recvmsg`, `close`, `shutdown`, `setsockopt`, `getsockopt`, `setblocking`, `settimeout`, `getpeername`, `getsockname`, `fileno`, `makefile`.

`socket.create_connection(address, timeout, source_address)` is a convenience function that handles IPv4/IPv6 duality, attempting to connect to each address family available for the given hostname.

`socket.getaddrinfo(host, port, family, type, proto, flags)` performs DNS resolution and returns a list of 5-tuples `(family, type, proto, canonname, sockaddr)`, enabling address-family-agnostic connection code.

## `ssl` — TLS Wrapper

`ssl` wraps OpenSSL (minimum 1.1.1, recommended 3.0.16) to add TLS/DTLS on top of `socket`. The primary interface is `ssl.SSLContext`, which holds certificate material and TLS configuration:

```python
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.load_verify_locations('/etc/ssl/certs/ca-bundle.crt')
ctx.verify_mode = ssl.CERT_REQUIRED
ctx.check_hostname = True
wrapped = ctx.wrap_socket(sock, server_hostname='example.com')
```

`ssl.create_default_context(purpose)` constructs a recommended-configuration context. `ssl.SSLSocket` extends `socket` with `do_handshake()`, `getpeercert()`, `cipher()`, `version()`.

## `http.client` — HTTP Client

`http.client.HTTPConnection` and `HTTPSConnection` implement the HTTP/1.1 client protocol. Usage follows a stateful request/response model:

```python
conn = http.client.HTTPSConnection('api.example.com')
conn.request('GET', '/v1/data', headers={'Accept': 'application/json'})
resp = conn.getresponse()
body = resp.read()
```

The response exposes `status`, `reason`, `headers` (an `http.client.HTTPMessage` / `email.message.Message`), and a file-like `read()` interface. `urllib.request` uses `http.client` internally.

## `urllib` — URL Handling

`urllib` is a package with four submodules:

- `urllib.request` — opens URLs (HTTP, HTTPS, FTP, file://, data:). The `urlopen(url, data, timeout, context)` function is the simple entry point. `Request` objects allow custom headers and method selection. Handler classes (`HTTPBasicAuthHandler`, `HTTPCookieProcessor`, `ProxyHandler`, etc.) customize behavior via `build_opener(*handlers)`.
- `urllib.parse` — URL parsing and construction. `urlparse(urlstring)` → `ParseResult`; `urlunparse(components)` → string; `urlencode(query)` → query string; `quote(string)`, `unquote(string)` for percent-encoding.
- `urllib.error` — `URLError` (base), `HTTPError` (subclass with `code`, `reason`, `headers`).
- `urllib.robotparser` — reads and queries `robots.txt` files.

## `http.server` — HTTP Server Primitives

`http.server.HTTPServer` (a `socketserver.TCPServer` subclass) and `BaseHTTPRequestHandler` implement a minimal HTTP server suitable for development, testing, and simple file serving. `SimpleHTTPRequestHandler` serves files from the current directory.

## `socketserver` — Generic Server Framework

`socketserver` provides `TCPServer`, `UDPServer`, `UnixStreamServer`, `UnixDatagramServer`, and mixin classes `ForkingMixIn` and `ThreadingMixIn`. It handles the accept/handle loop; user code overrides `handle()` in a `BaseRequestHandler` subclass.

## Email and MIME

The `email` package parses and generates RFC 5322 (email) and MIME messages. `email.parser.BytesParser` / `Parser` produce `email.message.EmailMessage` objects. `email.mime.*` modules construct messages with attachments. `smtplib.SMTP` / `SMTP_SSL` provide the client side of SMTP.

## `asyncio` — Asynchronous Networking

`asyncio` is the core framework for cooperative concurrency using `async def` / `await` syntax. The event loop drives I/O readiness notifications from the OS and schedules coroutines accordingly. Key networking components:

- **`asyncio.open_connection(host, port)`** — coroutine returning `(reader, writer)` pair using `StreamReader`/`StreamWriter`.
- **`asyncio.start_server(client_connected_cb, host, port)`** — server that calls a callback for each accepted connection.
- **`asyncio.get_event_loop()` / `asyncio.run(coro)`** — loop management.
- **Transports and Protocols** — the lower-level API. `Protocol.data_received(data)`, `Protocol.connection_made(transport)`, `Protocol.connection_lost(exc)` are the callbacks; `Transport.write(data)`, `Transport.close()` are the send-side interface.
- **`asyncio.DatagramProtocol`** — UDP variant.
- **`asyncio.Semaphore`, `asyncio.Lock`, `asyncio.Event`, `asyncio.Condition`, `asyncio.Queue`** — synchronization primitives for coroutines.

`asyncio.selector_events.BaseSelectorEventLoop` uses `selectors.DefaultSelector` (wrapping `epoll`, `kqueue`, or `select` depending on platform). `asyncio.proactor_events.BaseProactorEventLoop` uses Windows I/O Completion Ports on Windows.

## `selectors` — Multiplexed I/O

`selectors.DefaultSelector` wraps the most efficient OS mechanism available: `EpollSelector` (Linux), `KqueueSelector` (BSD/macOS), `PollSelector`, or `SelectSelector`. The abstract interface is `register(fileobj, events, data)` / `select(timeout)` → list of `(key, events)` pairs.

## `xmlrpc` and `json`

`xmlrpc.client` / `xmlrpc.server` implement XML-RPC. `json` (C extension `_json` for scanning) provides `json.dumps`, `json.loads`, and encoder/decoder customization via `JSONEncoder`/`JSONDecoder` subclasses.

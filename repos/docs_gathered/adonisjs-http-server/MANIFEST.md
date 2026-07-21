# MANIFEST

Documentation files for `@adonisjs/http-server` v8.1.3

| File | Subsystem |
|---|---|
| architecture.md | High-level architecture, design philosophy, package structure, data flow, build and packaging |
| server.md | Server class: boot sequence, request lifecycle, middleware registration, error handler registration, Node.js server configuration, testing pipeline |
| routing.md | Router, Route, RouteGroup, RouteResource, BriskRoute, RoutesStore, parameter matchers, domain routing, route lookup, type generation |
| request.md | HttpRequest: body access, URL and method, headers, content negotiation, cookies, request IDs, configuration, macroable extension |
| response.md | HttpResponse: body methods, status codes, headers, cookies, redirects, abort helpers, ETag, JSONP, response lifecycle, configuration |
| middleware.md | Global middleware, named middleware, inline middleware, execution order, error propagation, route executor pipeline, testing pipeline, type metadata |
| cookies.md | CookieClient, CookieParser, CookieSerializer, plain/signed/encrypted drivers, lazy decoding, application-level API, test helpers |
| http_context.md | HttpContext, per-request container, route information, AsyncLocalStorage, container resolver, macroable extension, TypeScript declaration merging |
| url_builder.md | createUrlBuilder, createURL, signed URL builder, domain-prefixed identifiers, URLOptions, legacy builder, client-side export |
| exception_handling.md | ExceptionHandler, built-in error types (E_ROUTE_NOT_FOUND, E_CANNOT_LOOKUP_ROUTE, E_HTTP_EXCEPTION, E_HTTP_REQUEST_ABORTED), report/handle phases, content-negotiated rendering, pipeline integration |
| configuration.md | defineConfig, ServerConfig, RequestConfig, ResponseConfig, QSParserConfig, cookie defaults, trust proxy normalisation |
| tracing_testing.md | diagnostics_channel tracing channels, channel payloads, test factories (RequestFactory, ResponseFactory, HttpContextFactory, RouterFactory, ServerFactory), Japa test conventions |

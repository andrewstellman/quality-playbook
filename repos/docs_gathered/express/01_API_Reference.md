# Express.js 5.x Complete API Reference

## Core Application (`express()`)

### Creating an Application
```javascript
const express = require('express')
const app = express()
```

### Built-in Middleware Methods

#### `express.json([options])`
Parses incoming JSON requests. Sets `req.body`.

**Options:**
- `inflate` (Boolean, default: `true`) - Handle deflated bodies
- `limit` (Mixed, default: `"100kb"`) - Max request body size
- `reviver` (Function) - Passed to `JSON.parse()`
- `strict` (Boolean, default: `true`) - Only accept arrays/objects
- `type` (Mixed, default: `"application/json"`) - Content-Type to parse
- `verify` (Function) - Called as `verify(req, res, buf, encoding)`

#### `express.urlencoded([options])`
Parses URL-encoded request bodies.

**Key Options:**
- `extended` (Boolean, default: `false`) - Use `qs` library if true
- `limit` (Mixed, default: `"100kb"`)
- `parameterLimit` (Number, default: `1000`)
- `depth` (Number, default: `32`)

#### `express.text([options])`
Parses incoming text requests.

**Options:**
- `defaultCharset` (String, default: `"utf-8"`)
- `limit` (Mixed, default: `"100kb"`)

#### `express.raw([options])`
Parses incoming requests into a `Buffer`.

#### `express.static(root, [options])`
Serves static files from the specified directory.

**Options:**
```javascript
{
  dotfiles: 'ignore',        // 'allow', 'deny', 'ignore'
  etag: true,                // Boolean
  extensions: ['html', 'htm'],
  fallthrough: true,         // Boolean
  index: 'index.html',       // String or false
  lastModified: true,        // Boolean
  maxAge: 0,                 // Number or string (ms format)
  redirect: true,            // Boolean
  setHeaders: fn,            // Function(res, path, stat)
  immutable: false,          // Boolean
  acceptRanges: true,        // Boolean
  cacheControl: true         // Boolean
}
```

#### `express.Router([options])`
Creates a new router instance.

**Options:**
- `caseSensitive` (Boolean) - Enable case-sensitive routing
- `mergeParams` (Boolean, default: `false`) - Preserve parent `req.params`
- `strict` (Boolean) - Enable strict routing

## Application Object (`app`)

### Properties

#### `app.locals`
Object containing application-level local variables. Persists throughout the application lifecycle.

#### `app.mountpath`
Path pattern(s) on which a sub-app was mounted.

#### `app.router`
The application's built-in router instance (created lazily on first access).

### Methods

#### `app.get(name)` / `app.set(name, value)`
Get or set application settings.

#### `app.enable(name)` / `app.disable(name)`
Set boolean settings to `true` or `false`.

#### `app.enabled(name)` / `app.disabled(name)`
Check if a setting is enabled/disabled.

#### `app.engine(ext, callback)`
Register a template engine.

#### `app.listen([port[, host[, backlog]]][, callback])`
Bind and listen on a port. Returns an `http.Server` object.

#### `app.use([path,] callback [, callback...])`
Mount middleware at specified path. Matches all HTTP methods.

Error-handling middleware requires 4 arguments: `(err, req, res, next)`

#### `app.METHOD(path, callback [, callback...])`
Route HTTP methods: `get`, `post`, `put`, `delete`, `patch`, `options`, `head`, etc.

#### `app.all(path, callback [, callback...])`
Match all HTTP methods on a path.

#### `app.param(name, callback)`
Add callback triggers for route parameters.

#### `app.route(path)`
Returns a route instance for chaining HTTP methods.

#### `app.render(view, [locals], callback)`
Render a view and return HTML via callback.

#### `app.path()`
Get the canonical path of the app.

### Application Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `case sensitive routing` | Boolean | undefined | Enable case-sensitive routing |
| `env` | String | `process.env.NODE_ENV` or "development" | Environment mode |
| `etag` | Varied | `weak` | Set ETag response header |
| `jsonp callback name` | String | "callback" | JSONP callback name |
| `json escape` | Boolean | undefined | Escape `<`, `>`, `&` in JSON |
| `json replacer` | Varied | undefined | JSON.stringify replacer |
| `json spaces` | Varied | undefined | JSON.stringify spaces |
| `query parser` | Varied | "simple" | Query string parser |
| `strict routing` | Boolean | undefined | Treat "/foo" and "/foo/" as different |
| `subdomain offset` | Number | 2 | Subdomain offset from domain |
| `trust proxy` | Varied | `false` | Trust X-Forwarded-* headers |
| `views` | String/Array | `process.cwd() + '/views'` | Views directory |
| `view cache` | Boolean | `true` in production | Cache compiled views |
| `view engine` | String | undefined | Default template engine |
| `x-powered-by` | Boolean | `true` | Send X-Powered-By header |

## Request Object (`req`)

### Key Properties

- `req.app` - Reference to Express application instance
- `req.baseUrl` - The URL path on which the router was mounted
- `req.body` - Contains parsed request body
- `req.cookies` - Cookies sent with request
- `req.hostname` - Hostname from Host header (without port)
- `req.host` - Host with port from Host header
- `req.ip` - Remote IP address
- `req.ips` - Array of IPs from X-Forwarded-For header
- `req.method` - HTTP method of request
- `req.originalUrl` - Original request URL
- `req.params` - Named route parameters
- `req.path` - Path portion of request URL
- `req.protocol` - Request protocol (http or https)
- `req.query` - Query string parameters as object
- `req.route` - Currently matched route
- `req.secure` - Boolean indicating TLS connection
- `req.signedCookies` - Signed cookies
- `req.fresh` / `req.stale` - Cache freshness
- `req.subdomains` - Array of subdomains
- `req.xhr` - Is XMLHttpRequest

### Key Methods

- `req.accepts(types)` - Check acceptable content types
- `req.acceptsCharsets(charset)` - First accepted charset
- `req.acceptsEncodings(encoding)` - First accepted encoding
- `req.acceptsLanguages(lang)` - First accepted language
- `req.get(field)` - Get HTTP header field
- `req.is(type)` - Check request content type
- `req.range(size[, options])` - Parse Range header

## Response Object (`res`)

### Key Properties

- `res.app` - Reference to Express application instance
- `res.headersSent` - Headers have been sent?
- `res.locals` - Object for passing variables to templates
- `res.req` - Reference to request object

### Key Methods

- `res.status(code)` - Set HTTP status code
- `res.send([body])` - Send response
- `res.json([body])` - Send JSON response
- `res.jsonp([body])` - Send JSONP response
- `res.end([data[, encoding]][, callback])` - End response
- `res.redirect([status,] path)` - Redirect to URL
- `res.render(view, [locals], [callback])` - Render view template
- `res.sendFile(path[, options][, fn])` - Transfer file
- `res.download(path[, filename][, options][, fn])` - Prompt download
- `res.set(field [, value])` - Set response header
- `res.get(field)` - Get response header
- `res.append(field[, value])` - Append to response header
- `res.type(type)` - Set Content-Type header
- `res.format(object)` - Content negotiation based on Accept header
- `res.cookie(name, value[, options])` - Set cookie
- `res.clearCookie(name[, options])` - Clear cookie
- `res.location(path)` - Set Location header
- `res.attachment([filename])` - Set Content-Disposition header
- `res.sendStatus(statusCode)` - Send status code and message
- `res.links(links)` - Populate Link header
- `res.vary(field)` - Add Vary header

## Router Object

### Methods

- `router.METHOD(path, [callback, ...] callback)` - Route HTTP methods
- `router.all(path, [callback, ...] callback)` - Match all HTTP methods
- `router.use([path,] [callback, ...] callback)` - Mount middleware
- `router.param(name, callback)` - Route parameter handling
- `router.route(path)` - Create chainable route

## Common Patterns

### Error Handling
```javascript
// Try-catch in async route
app.get('/', async (req, res, next) => {
  try {
    const data = await fetchData()
    res.json(data)
  } catch (err) {
    next(err)
  }
})

// Error handler middleware (must be last)
app.use((err, req, res, next) => {
  console.error(err.stack)
  res.status(err.status || 500).json({
    error: err.message
  })
})
```

### Middleware Composition
```javascript
const authenticate = (req, res, next) => {
  if (req.user) next()
  else res.status(401).send('Unauthorized')
}

const authorize = (role) => (req, res, next) => {
  if (req.user.role === role) next()
  else res.status(403).send('Forbidden')
}

app.delete('/user/:id', authenticate, authorize('admin'), (req, res) => {
  // delete user
})
```

### Sub-applications
```javascript
const admin = express()
admin.get('/', (req, res) => res.send('Admin'))

app.use('/admin', admin)
```

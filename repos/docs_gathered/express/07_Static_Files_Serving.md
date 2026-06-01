# Serving Static Files in Express

## Overview
To serve static files (images, CSS, JavaScript), use the `express.static` built-in middleware function in Express.

## Basic Syntax
```javascript
express.static(root, [options])
```

The `root` argument specifies the root directory from which to serve static assets.

## Basic Usage

### Simple Static Directory
```javascript
app.use(express.static('public'))
```

This allows access to files in the `public` directory:
```
http://localhost:3000/images/kitten.jpg
http://localhost:3000/css/style.css
http://localhost:3000/js/app.js
http://localhost:3000/images/bg.png
http://localhost:3000/hello.html
```

**Note:** The static directory name is not part of the URL.

### Multiple Static Directories
```javascript
app.use(express.static('public'))
app.use(express.static('files'))
```

Express looks up files in the order directories are declared. If a file exists in both, the first one wins.

## Virtual Path Prefix

Create a virtual path prefix for serving static files:

```javascript
app.use('/static', express.static('public'))
```

Files are now accessed with the `/static` prefix:
```
http://localhost:3000/static/images/kitten.jpg
http://localhost:3000/static/css/style.css
http://localhost:3000/static/js/app.js
```

## Absolute Path (Recommended)

For safer deployment, use absolute paths:

```javascript
const path = require('path')
app.use('/static', express.static(path.join(__dirname, 'public')))
```

This avoids issues when running from different directories.

## express.static Options

The `express.static` middleware accepts several options:

### Common Options

```javascript
app.use(express.static('public', {
  dotfiles: 'ignore',        // 'allow', 'deny', 'ignore' (default: ignore in v5)
  etag: true,                // Enable/disable ETag generation
  extensions: ['html', 'htm'], // Set file extension fallbacks
  fallthrough: true,         // Pass to next handler if not found
  index: 'index.html',       // Default file to serve
  lastModified: true,        // Set Last-Modified header
  maxAge: '1d',              // Cache-Control max-age
  redirect: true,            // Redirect to trailing slash
  setHeaders: function (res, path, stat) {
    // Custom headers logic
  },
  immutable: false,          // Cache-Control immutable
  acceptRanges: true,        // Accept-Ranges header
  cacheControl: true         // Cache-Control header
}))
```

### Dotfiles Handling (Express 5 Change)

**Express 4 behavior:** Served by default
**Express 5 behavior:** Ignored by default (returns 404)

To serve dotfiles in v5:

```javascript
// Allow specific dot-directory
app.use('/.well-known', express.static('public/.well-known', { dotfiles: 'allow' }))

// Or allow all dotfiles (not recommended)
app.use(express.static('public', { dotfiles: 'allow' }))
```

### Custom Headers Example

```javascript
app.use(express.static('public', {
  setHeaders: function (res, path, stat) {
    if (path.endsWith('.js')) {
      res.set('X-Content-Type-Options', 'nosniff')
    }
    if (path.endsWith('.css')) {
      res.set('X-Content-Type-Options', 'nosniff')
    }
  }
}))
```

### Cache Control Example

```javascript
app.use(express.static('public', {
  maxAge: '1h',              // 1 hour cache
  etag: true,                // Use ETag validation
  lastModified: true         // Use Last-Modified header
}))

// For assets with content hash, use immutable
app.use(express.static('dist', {
  maxAge: '365d',            // 1 year cache
  immutable: true            // Never expires
}))
```

## Project Structure with Static Files

```
myapp/
├── app.js
├── public/                 # Static files directory
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── app.js
│   ├── images/
│   │   └── logo.png
│   └── index.html
└── package.json
```

## Multiple Static Directories Pattern

```javascript
// Serve public files (without prefix)
app.use(express.static('public'))

// Serve uploaded files (with prefix)
app.use('/uploads', express.static('uploads'))

// Serve node_modules for client libraries (with prefix)
app.use('/vendor', express.static('node_modules'))
```

## Performance Best Practice
For optimal performance, use a [reverse proxy cache](https://expressjs.com/en/advanced/best-practice-performance.html#use-a-reverse-proxy) to improve static asset serving.

Examples:
- [Varnish](https://www.varnish-cache.org/)
- [Nginx caching](https://blog.nginx.org/blog/nginx-caching-guide)

## Fallback Behavior

```javascript
app.use(express.static('public', {
  fallthrough: true          // Default: pass to next middleware if not found
}))

// If fallthrough is false:
// app.use(express.static('public', {
//   fallthrough: false      // Send 404 if file not found
// }))
```

## Index File Configuration

```javascript
app.use(express.static('public', {
  index: 'index.html'        // Default index file
}))

// Or custom index files:
app.use(express.static('public', {
  index: ['index.html', 'index.htm']
}))

// Disable index file serving:
app.use(express.static('public', {
  index: false
}))
```

## Security Considerations

1. **Dotfiles**: By default (v5), dotfiles are not served (security best practice)
2. **Directory Traversal**: Express prevents access outside the root directory
3. **MIME Types**: Ensure correct MIME types are set for files
4. **Caching**: Use appropriate cache headers to prevent stale content

## Common Use Cases

### Serve SPA (Single Page Application)
```javascript
app.use(express.static('dist'))

// Fallback to index.html for client-side routing
app.use((req, res) => {
  res.sendFile(path.join(__dirname, 'dist/index.html'))
})
```

### Serve API Docs
```javascript
app.use('/api-docs', express.static('api-docs'))
```

### Serve User Uploads
```javascript
app.use('/uploads', express.static('uploads', {
  maxAge: '7d'
}))
```

## Documentation Reference
For detailed options, see [express.static API documentation](/en/5x/api.html#express.static)

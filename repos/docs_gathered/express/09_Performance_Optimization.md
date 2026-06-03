# Performance Best Practices for Express in Production

## Overview
This guide covers performance and reliability best practices divided into two categories: code-level optimizations (dev) and environment/setup configurations (ops).

## Code-Level Best Practices

### 1. Use Gzip Compression
Compress response bodies to significantly reduce size and increase app speed.

**Using compression middleware:**
```javascript
const compression = require('compression')
const express = require('express')
const app = express()

app.use(compression())
```

**For high-traffic sites:** Implement compression at the reverse proxy level (Nginx) instead, eliminating the need for middleware.

### 2. Avoid Synchronous Functions
Synchronous functions block the process until completion, degrading performance under load.

**Best practices:**
- Always use asynchronous versions in production
- Synchronous functions only justified at initial startup
- Use `--trace-sync-io` flag during development to identify synchronous APIs

### 3. Logging Best Practices

**For Debugging:**
- Use the [debug](https://www.npmjs.com/package/debug) module instead of `console.log()`
- Control debug messages via the `DEBUG` environment variable

**For App Activity:**
- Use [Pino](https://www.npmjs.com/package/pino) logging library (fastest and most efficient)
- Avoid `console.log()` and `console.error()` (synchronous in production)

### 4. Handle Exceptions Properly

**Use Try-Catch (synchronous code):**
```javascript
app.get('/search', (req, res) => {
  setImmediate(() => {
    const jsonStr = req.query.params
    try {
      const jsonObj = JSON.parse(jsonStr)
      res.send('Success')
    } catch (e) {
      res.status(400).send('Invalid JSON string')
    }
  })
})
```

**Use Promises (async code):**
```javascript
app.get('/', async (req, res, next) => {
  const data = await userData() // Errors auto-call next(err)
  res.send(data)
})

app.use((err, req, res, next) => {
  res.status(err.status ?? 500).send({ error: err.message })
})
```

**What NOT to do:**
- Don't listen for `uncaughtException` events
- Don't use deprecated `domains` module
- Let app crash and restart via process manager (more reliable)

## Environment/Setup Best Practices

### 1. Set NODE_ENV to "production"
**Performance improvement: 3x faster!**

**Benefits:**
- Caches view templates
- Caches CSS from extensions
- Generates less verbose errors

**Using systemd:**
```ini
# /etc/systemd/system/myservice.service
[Service]
Environment=NODE_ENV=production
```

### 2. Ensure Automatic Restarts

**Process Manager Approach:**
Use [PM2](https://github.com/Unitech/pm2) to restart the app when it crashes.

**Init System Approach (Recommended):**
Use systemd as the primary layer of reliability.

**Example systemd unit file:**
```ini
[Unit]
Description=<Awesome Express App>

[Service]
Type=simple
ExecStart=/usr/local/bin/node </projects/myapp/index.js>
WorkingDirectory=</projects/myapp>

User=nobody
Group=nogroup

Environment=NODE_ENV=production
LimitNOFILE=infinity
LimitCORE=infinity

Restart=always

[Install]
WantedBy=multi-user.target
```

### 3. Run Your App in a Cluster
Distribute load across multiple processes (ideally one per CPU core).

**Using Node's cluster module:**
Spawn multiple worker processes from a master process to distribute incoming connections.

**Using PM2 (easiest):**
```bash
# Start 4 worker processes
pm2 start npm --name my-app -i 4 -- start

# Auto-detect CPU count
pm2 start npm --name my-app -i max -- start

# Scale dynamically
pm2 scale my-app +3
pm2 scale my-app 2
```

**Important:** Apps must be stateless. Use Redis for session/state data, not in-memory storage.

### 4. Cache Request Results
Avoid repeating operations for identical requests.

**Options:**
- [Varnish](https://www.varnish-cache.org/)
- [Nginx caching](https://blog.nginx.org/blog/nginx-caching-guide)

### 5. Use a Load Balancer
Distribute traffic across multiple app instances for better performance and scalability.

**Options:**
- [Nginx load balancing](https://nginx.org/en/docs/http/load_balancing.html)
- [HAProxy](https://www.digitalocean.com/community/tutorials/an-introduction-to-haproxy-and-load-balancing-concepts)

**Note:** Consider session affinity (sticky sessions) or use Redis for distributed session storage.

### 6. Use a Reverse Proxy
Offload non-application tasks to a reverse proxy (compression, caching, error pages, load balancing).

**Recommended options:**
- [Nginx](https://www.nginx.org/)
- [HAProxy](https://www.haproxy.org/)

This frees Express to focus on application logic while the reverse proxy handles infrastructure concerns.

## Caching Strategies

### Application-Level Caching
```javascript
const cache = new Map()

function getCachedData(key, fetch) {
  if (cache.has(key)) {
    return cache.get(key)
  }

  const data = fetch()
  cache.set(key, data)
  return data
}

app.get('/data/:id', (req, res) => {
  const data = getCachedData(`data-${req.params.id}`, () => {
    return fetchFromDatabase(req.params.id)
  })
  res.json(data)
})
```

### HTTP Caching Headers
```javascript
app.get('/api/data', (req, res) => {
  res.set({
    'Cache-Control': 'public, max-age=3600',
    'ETag': generateETag(data)
  })
  res.json(data)
})
```

## Summary
The most impactful optimizations are:
1. Setting `NODE_ENV=production` (3x performance boost)
2. Using async functions exclusively
3. Implementing clustering and load balancing
4. Running behind a reverse proxy
5. Automatic restart mechanisms
6. Compression middleware or reverse proxy compression
7. Efficient logging with Pino or debug module

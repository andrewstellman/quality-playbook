# Express 4 to Express 5 Migration Guide

## Overview

Express 5 maintains the same basic API as Express 4 but includes **breaking changes** that require code updates. Applications built with Express 4 will not work without modifications when upgraded to Express 5.

**Requirements:** Node.js version 18 or higher

**Installation:**
```bash
npm install "express@5"
```

## Automated Migration Tools

Express provides codemods to automatically update your code:

```bash
# Run all available codemods
npx codemod@latest @expressjs/v5-migration-recipe

# Run specific codemod
npx codemod@latest @expressjs/name-of-the-codemod
```

## Removed Methods and Properties

### 1. `app.del()` → `app.delete()`
```javascript
// v4
app.del('/user/:id', (req, res) => {
  res.send(`DELETE /user/${req.params.id}`)
})

// v5
app.delete('/user/:id', (req, res) => {
  res.send(`DELETE /user/${req.params.id}`)
})
```

### 2. `app.param(fn)` - Removed
The signature for modifying `app.param(name, fn)` behavior is no longer supported.

### 3. Pluralized Method Names - Updated
```javascript
// v4
req.acceptsCharset()      // ❌
req.acceptsEncoding()     // ❌
req.acceptsLanguage()     // ❌

// v5
req.acceptsCharsets()     // ✓
req.acceptsEncodings()    // ✓
req.acceptsLanguages()    // ✓
```

### 4. `req.param(name)` - Removed
```javascript
// v4
app.post('/user', (req, res) => {
  const id = req.param('id')
})

// v5
app.post('/user', (req, res) => {
  const id = req.params.id        // Use req.params
  const body = req.body           // Use req.body
  const query = req.query         // Use req.query
})
```

### 5. `res.json(obj, status)` - Signature Changed
```javascript
// v4
res.json({ name: 'Ruben' }, 201)

// v5
res.status(201).json({ name: 'Ruben' })
```

### 6. `res.jsonp(obj, status)` - Signature Changed
```javascript
// v4
res.jsonp({ name: 'Ruben' }, 201)

// v5
res.status(201).jsonp({ name: 'Ruben' })
```

### 7. `res.redirect()` - Argument Order Changed
```javascript
// v4
res.redirect('/users', 301)

// v5
res.redirect(301, '/users')
```

### 8. `res.redirect('back')` - Magic String Removed
```javascript
// v4
res.redirect('back')

// v5
res.redirect(req.get('Referrer') || '/')
```

### 9. `res.send(body, status)` - Signature Changed
```javascript
// v4
res.send({ name: 'Ruben' }, 200)

// v5
res.status(200).send({ name: 'Ruben' })
```

### 10. `res.send(status)` - Removed
```javascript
// v4
res.send(200)

// v5
res.sendStatus(200)
// Or for sending a number as data:
res.send('200')
```

### 11. `res.sendfile()` → `res.sendFile()`
```javascript
// v4
res.sendfile('/path/to/file')

// v5
res.sendFile('/path/to/file')
```

**MIME type detection changes:**
- `.js`: "text/javascript" (was "application/javascript")
- `.json`: "application/json" (was "text/json")
- `.css`: "text/css" (was "text/plain")
- `.xml`: "application/xml" (was "text/xml")
- `.woff`: "font/woff" (was "application/font-woff")

### 12. `router.param(fn)` - Removed
The signature for modifying `router.param(name, fn)` behavior is no longer supported.

### 13. `express.static.mime` - Removed
```javascript
// v4
express.static.mime.lookup('json')

// v5
const mime = require('mime-types')
mime.lookup('json')
```

### 14. Debug Logs Namespace Changed
```bash
# v4
DEBUG=express:* node index.js

# v5
DEBUG=express:*,router,router:* node index.js
```

## Changed Behavior

### Path Route Matching Syntax

#### **Wildcards Must Be Named**
```javascript
// v4
app.get('/*', (req, res) => res.send('ok'))

// v5
app.get('/*splat', (req, res) => res.send('ok'))

// To match root path too:
app.get('/{*splat}', (req, res) => res.send('ok'))
```

#### **Optional Parameters Use Braces**
```javascript
// v4
app.get('/:file.:ext?', (req, res) => res.send('ok'))

// v5
app.get('/:file{.:ext}', (req, res) => res.send('ok'))
```

#### **Regexp Characters Not Supported**
```javascript
// v4
app.get('/[discussion|page]/:slug', (req, res) => res.send('ok'))

// v5
app.get(['/discussion/:slug', '/page/:slug'], (req, res) => res.send('ok'))
```

### Rejected Promise Handling
Rejected promises in middleware/handlers are now passed to error handlers:

```javascript
app.get('/', async (req, res) => {
  throw new Error('Something went wrong')
})

// Error handling middleware
app.use((err, req, res, next) => {
  res.status(500).send(err.message)
})
```

### express.urlencoded
The `extended` option now defaults to `false`.

### express.static Dotfiles
**Default changed to ignore dotfiles** (was: serve by default)

```javascript
// v4 - Request to /.well-known/assetlinks.json works
app.use(express.static('public'))

// v5 - Returns 404 for dotfiles by default
// Fix: Explicitly allow specific dot-directories
app.use('/.well-known', express.static('public/.well-known', { dotfiles: 'allow' }))
app.use(express.static('public'))
```

### app.listen Callback
```javascript
// v5 - Errors passed to callback
const server = app.listen(8080, '0.0.0.0', (error) => {
  if (error) {
    throw error // e.g., EADDRINUSE
  }
  console.log(`Listening on ${JSON.stringify(server.address())}`)
})
```

### app.router
The `app.router` object is now available as a reference to the base Express router.

### req.body
Now returns `undefined` when unparsed (was: `{}`).

### req.host
Now includes port number (v4 stripped it).

### req.params Behavioral Changes

**Null Prototype for String Paths:**
```javascript
app.get('/*splat', (req, res) => {
  // GET /foo/bar
  console.dir(req.params)
  // => [Object: null prototype] { splat: ['foo', 'bar'] }
})
```

**Wildcard Parameters Are Arrays:**
Splat parameters are now arrays, not strings.

**Unmatched Parameters Omitted:**
```javascript
// v4
app.get('/:file.:ext?', (req, res) => {
  // GET /image
  console.dir(req.params)
  // => { file: 'image', ext: undefined }
})

// v5
app.get('/:file{.:ext}', (req, res) => {
  // GET /image
  console.dir(req.params)
  // => [Object: null prototype] { file: 'image' }
  // ext key is omitted entirely
})
```

### req.query
- No longer writable (is a getter)
- Default query parser changed from "extended" to "simple"

### res.clearCookie
Now ignores `maxAge` and `expires` options.

### res.status
- Only accepts integers 100-999
- Throws error for non-integer values

### res.vary
Throws error when `field` argument is missing (v4 gave a warning).

## Improvements

### res.render()
Now enforces asynchronous behavior for all view engines.

### Brotli Encoding Support
Express 5 supports Brotli compression for compatible clients.

## Migration Checklist

- [ ] Install Express 5: `npm install "express@5"`
- [ ] Run automated codemods: `npx codemod@latest @expressjs/v5-migration-recipe`
- [ ] Run automated tests to identify remaining issues
- [ ] Review removed methods and update code
- [ ] Test application thoroughly
- [ ] Update path routing syntax if needed
- [ ] Verify static file serving (dotfiles)
- [ ] Check req.params behavior in routes
- [ ] Update debug logging commands if applicable
- [ ] Test error handling with rejected promises

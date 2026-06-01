# Express Error Handling Guide

## Overview

Error Handling refers to how Express catches and processes errors that occur both synchronously and asynchronously. Express includes a default error handler, so you don't need to write your own to get started.

## Catching Errors

### Synchronous Errors
Express automatically catches synchronous errors in route handlers and middleware:

```javascript
app.get('/', (req, res) => {
  throw new Error('BROKEN') // Express will catch this on its own.
})
```

### Asynchronous Errors (Callbacks)
For asynchronous functions, pass errors to the `next()` function:

```javascript
app.get('/', (req, res, next) => {
  fs.readFile('/file-does-not-exist', (err, data) => {
    if (err) {
      next(err) // Pass errors to Express.
    } else {
      res.send(data)
    }
  })
})
```

### Express 5: Promise-based Handlers
Route handlers and middleware that return Promises automatically call `next(value)` on rejection:

```javascript
app.get('/user/:id', async (req, res, next) => {
  const user = await getUserById(req.params.id)
  res.send(user)
})
```

### Asynchronous Code with Try-Catch
For asynchronous code in setTimeout or similar, use try-catch:

```javascript
app.get('/', (req, res, next) => {
  setTimeout(() => {
    try {
      throw new Error('BROKEN')
    } catch (err) {
      next(err)
    }
  }, 100)
})
```

### Using Promises
Simplify error handling with promises:

```javascript
app.get('/', (req, res, next) => {
  Promise.resolve().then(() => {
    throw new Error('BROKEN')
  }).catch(next) // Errors will be passed to Express.
})
```

## The Default Error Handler

Express includes a built-in error handler that:

- Sets `res.statusCode` from `err.status` (or `err.statusCode`), defaulting to 500
- Sets `res.statusMessage` according to the status code
- Returns HTML of the status message in production, or `err.stack` in development
- Includes any headers specified in `err.headers`

**Enable production mode:**
```bash
NODE_ENV=production
```

## Writing Custom Error Handlers

### Basic Error Handler
Error-handling middleware has **four arguments** instead of three:

```javascript
app.use((err, req, res, next) => {
  console.error(err.stack)
  res.status(500).send('Something broke!')
})
```

**Important**: Define error handlers **last**, after other `app.use()` and route calls:

```javascript
const bodyParser = require('body-parser')
const methodOverride = require('method-override')

app.use(bodyParser.urlencoded({ extended: true }))
app.use(bodyParser.json())
app.use(methodOverride())
app.use((err, req, res, next) => {
  // Error handling logic
})
```

### Multiple Error Handlers

Organize error handling with multiple handlers:

```javascript
app.use(bodyParser.urlencoded({ extended: true }))
app.use(bodyParser.json())
app.use(methodOverride())
app.use(logErrors)
app.use(clientErrorHandler)
app.use(errorHandler)
```

#### Log Errors
```javascript
function logErrors (err, req, res, next) {
  console.error(err.stack)
  next(err)
}
```

#### Handle XHR vs Regular Requests
```javascript
function clientErrorHandler (err, req, res, next) {
  if (req.xhr) {
    res.status(500).send({ error: 'Something failed!' })
  } else {
    next(err)
  }
}
```

#### Catch-All Handler
```javascript
function errorHandler (err, req, res, next) {
  res.status(500)
  res.render('error', { error: err })
}
```

## Best Practices

### 1. Always catch errors
If you don't call `next()` in an error handler, you must write and end the response, or requests will hang.

### 2. Delegate to default handler
When headers are already sent, delegate to the default error handler:

```javascript
function errorHandler (err, req, res, next) {
  if (res.headersSent) {
    return next(err)
  }
  res.status(500)
  res.render('error', { error: err })
}
```

### 3. Use `next('route')`
Skip remaining route handlers in a chain:

```javascript
app.get('/:id', (req, res, next) => {
  if (!isValidId(req.params.id)) {
    return next('route')  // Skip to next matching route
  }
  res.send('Valid ID')
})

app.get('/:id', (req, res) => {
  res.send('ID fallback handler')
})
```

### 4. Ensure Express receives errors
Without proper error passing, your app may crash unexpectedly.

## Error Handler Middleware Chain

- `next(err)` skips all remaining handlers except error-handling middleware
- `next('route')` skips to the next route handler
- Error-handling middleware must have exactly 4 parameters: `(err, req, res, next)`

## Production Error Handling

### Security Consideration
Never send the client the error stack as it poses a security risk to the server. Stack traces expose implementation details that help attackers.

### Example: Production Error Handler
```javascript
app.use((err, req, res, next) => {
  // Log with details for debugging
  console.error(err)

  // Send generic error to client
  const status = err.status || 500
  const message = process.env.NODE_ENV === 'production'
    ? 'Internal Server Error'
    : err.message

  res.status(status).json({
    error: {
      status: status,
      message: message
    }
  })
})
```

## Handling Rejected Promises (Express 5)

In Express 5, unhandled promise rejections in request handlers are automatically passed to error handlers:

```javascript
app.get('/', async (req, res, next) => {
  // This error is automatically caught by error middleware
  throw new Error('Something went wrong')
})

app.use((err, req, res, next) => {
  res.status(500).send('Error: ' + err.message)
})
```

## Common Error Patterns

### Validation Error Handler
```javascript
app.post('/user', (req, res, next) => {
  if (!req.body.email) {
    return next(new ValidationError('Email required'))
  }
  // Continue processing
})

class ValidationError extends Error {
  constructor(message) {
    super(message)
    this.status = 400
  }
}

app.use((err, req, res, next) => {
  if (err instanceof ValidationError) {
    return res.status(err.status).json({ error: err.message })
  }
  next(err)
})
```

### Async Route Wrapper
```javascript
const asyncHandler = (fn) => (req, res, next) => {
  Promise.resolve(fn(req, res, next)).catch(next)
}

app.get('/', asyncHandler(async (req, res) => {
  const data = await fetchData()
  res.json(data)
}))
```

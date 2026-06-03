# Express Middleware Architecture & Writing Guide

## Overview

Middleware functions are the backbone of every Node.js web application built with Express. They control how requests flow from arrival to response. Middleware functions have access to:
- Request object (`req`)
- Response object (`res`)
- `next` function to pass control to the next middleware

## Core Middleware Responsibilities

Middleware functions can:
- Execute any code
- Modify request and response objects
- End the request-response cycle
- Call the next middleware in the stack

**Critical Rule**: If middleware doesn't end the request-response cycle, it **must call `next()`** to avoid hanging requests.

## Execution Flow

Middleware functions are executed in the order they are defined, creating a pipeline. Each middleware can perform operations and decide whether to pass control to the next middleware or end the cycle.

## Basic Middleware Pattern

```javascript
const myMiddleware = function (req, res, next) {
  // Execute code
  next() // Pass control to next middleware
}

app.use(myMiddleware)
```

## Modifying Request Objects

```javascript
const requestTime = function (req, res, next) {
  req.requestTime = Date.now()
  next()
}

app.use(requestTime)

app.get('/', (req, res) => {
  res.send(`Requested at: ${req.requestTime}`)
})
```

## Error Handling & Async Middleware

### Async Middleware with Error Handling (Express 5+)

```javascript
async function validateCookies (req, res, next) {
  await cookieValidator(req.cookies)
  next()
}

app.use(validateCookies)

// Error handler middleware
app.use((err, req, res, next) => {
  res.status(400).send(err.message)
})
```

**Key Behavior**: Starting with Express 5, middleware returning Promises will automatically call `next(value)` on rejection/error.

### Passing Errors Forward

```javascript
// Trigger error handler by passing anything to next()
// (except 'route' or 'router')
next(new Error('Invalid input'))
```

## Middleware Loading Order

```javascript
app.use(myLogger)  // Loaded first, executed first

app.get('/', handler)  // Route handler

// myLogger runs BEFORE the route handler
```

## Configurable Middleware Pattern

### File: my-middleware.js
```javascript
module.exports = function (options) {
  return function (req, res, next) {
    // Implement based on options
    next()
  }
}
```

### Usage
```javascript
const mw = require('./my-middleware.js')
app.use(mw({ option1: '1', option2: '2' }))
```

Examples: [cookie-session](https://github.com/expressjs/cookie-session), [compression](https://github.com/expressjs/compression)

## Request Lifecycle Control

### Don't leave requests hanging
```javascript
// DON'T - Missing next() causes request to hang
const badMiddleware = (req, res, next) => {
  console.log('LOGGED')
  // Missing next() - request hangs!
}

// DO - Call next() to continue
const goodMiddleware = (req, res, next) => {
  console.log('LOGGED')
  next()  // ✓ Correct
}
```

## Common Middleware Patterns

| Use Case | Pattern |
|----------|---------|
| Logging | Simple function with `next()` |
| Request enrichment | Add properties to `req`, call `next()` |
| Validation | Validate input, `next()` on success or error handler on failure |
| Cookie handling | Use `cookie-parser`, validate asynchronously |
| Authentication | Check token/session, add user to `req`, call `next()` |
| CORS | Set headers, call `next()` |
| Rate limiting | Check limits, respond with 429 or call `next()` |

## Built-in Middleware

Express includes several built-in middleware functions:

```javascript
// Parse JSON bodies
app.use(express.json())

// Parse URL-encoded bodies
app.use(express.urlencoded({ extended: true }))

// Parse text bodies
app.use(express.text())

// Parse binary bodies
app.use(express.raw())

// Serve static files
app.use(express.static('public'))
```

## Error-Handling Middleware

Error-handling middleware has **four arguments** and must be defined **last**:

```javascript
app.use((err, req, res, next) => {
  console.error(err.stack)
  res.status(500).send('Something broke!')
})
```

## Middleware Composition

```javascript
const authenticate = (req, res, next) => {
  if (req.user) next()
  else res.status(401).send('Unauthorized')
}

const authorize = (role) => (req, res, next) => {
  if (req.user.role === role) next()
  else res.status(403).send('Forbidden')
}

// Use middleware in routes
app.delete('/user/:id', authenticate, authorize('admin'), (req, res) => {
  // delete user
})
```

## Middleware Factory

```javascript
function createLogger(options) {
  return function logger(req, res, next) {
    const start = Date.now()

    res.on('finish', () => {
      const duration = Date.now() - start
      console.log(`${req.method} ${req.url} - ${duration}ms`)
    })

    next()
  }
}

app.use(createLogger({ format: 'dev' }))
```

## Best Practices

1. **Keep middleware focused** - One middleware = one responsibility
2. **Use next() consistently** - Always call it unless ending response
3. **Order matters** - Place middleware in correct execution order
4. **Error handlers last** - Error middleware should be defined last
5. **Scope narrowly** - Use path prefixes to limit middleware scope
6. **Handle async properly** - Use try-catch or promise chains
7. **Add context carefully** - When modifying `req`, use clear property names

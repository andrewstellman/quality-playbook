# Express Routing Guide

## Overview

Routing refers to how an application's endpoints (URIs) respond to client requests. Express uses methods on the `app` object that correspond to HTTP methods to define routes.

## Route Methods

Define routes using HTTP method functions:

```javascript
const express = require('express')
const app = express()

// GET request
app.get('/', (req, res) => {
  res.send('GET request to the homepage')
})

// POST request
app.post('/', (req, res) => {
  res.send('POST request to the homepage')
})
```

Use `app.all()` to handle all HTTP methods:

```javascript
app.all('/secret', (req, res, next) => {
  console.log('Accessing the secret section ...')
  next() // pass control to the next handler
})
```

## Route Paths

Route paths can be **strings**, **string patterns**, or **regular expressions**.

### String-based paths
```javascript
app.get('/', (req, res) => res.send('root'))
app.get('/about', (req, res) => res.send('about'))
app.get('/random.text', (req, res) => res.send('random.text'))
```

### Regular expression paths
```javascript
// Match anything with "a"
app.get(/a/, (req, res) => res.send('/a/'))

// Match butterfly/dragonfly but not butterflyman/dragonflyman
app.get(/.*fly$/, (req, res) => res.send('/.*fly$/'))
```

## Route Parameters

Capture URL segments using named parameters (accessible via `req.params`):

```javascript
// Route path: /users/:userId/books/:bookId
// Request URL: http://localhost:3000/users/34/books/8989
// req.params: { "userId": "34", "bookId": "8989" }

app.get('/users/:userId/books/:bookId', (req, res) => {
  res.send(req.params)
})
```

### Using hyphens and dots
```javascript
// Route path: /flights/:from-:to
// Request URL: http://localhost:3000/flights/LAX-SFO
// req.params: { "from": "LAX", "to": "SFO" }

app.get('/flights/:from-:to', (req, res) => {
  res.send(req.params)
})
```

### With regex constraints
```javascript
// Route path: /user/:userId(\d+)
// Request URL: http://localhost:3000/user/42
// req.params: {"userId": "42"}

app.get('/user/:userId(\\d+)', (req, res) => {
  res.send(req.params)
})
```

## Route Handlers

### Single callback
```javascript
app.get('/example/a', (req, res) => {
  res.send('Hello from A!')
})
```

### Multiple callbacks
```javascript
app.get('/example/b', (req, res, next) => {
  console.log('the response will be sent by the next function ...')
  next()
}, (req, res) => {
  res.send('Hello from B!')
})
```

### Array of callbacks
```javascript
const cb0 = (req, res, next) => {
  console.log('CB0')
  next()
}

const cb1 = (req, res, next) => {
  console.log('CB1')
  next()
}

const cb2 = (req, res) => {
  res.send('Hello from C!')
}

app.get('/example/c', [cb0, cb1, cb2])
```

### Bypass route handlers with `next('route')`
```javascript
app.get('/user/:id', (req, res, next) => {
  if (req.params.id === '0') {
    return next('route') // skip to next matching route
  }
  res.send(`User ${req.params.id}`)
})

app.get('/user/:id', (req, res) => {
  res.send('Special handler for user ID 0')
})
```

## Response Methods

| Method | Description |
|--------|-------------|
| `res.download()` | Prompt a file to be downloaded |
| `res.end()` | End the response process |
| `res.json()` | Send a JSON response |
| `res.jsonp()` | Send a JSON response with JSONP support |
| `res.redirect()` | Redirect a request |
| `res.render()` | Render a view template |
| `res.send()` | Send a response of various types |
| `res.sendFile()` | Send a file as an octet stream |
| `res.sendStatus()` | Set response status code and send string representation |

## app.route()

Create chainable route handlers for a single path:

```javascript
app.route('/book')
  .get((req, res) => {
    res.send('Get a random book')
  })
  .post((req, res) => {
    res.send('Add a book')
  })
  .put((req, res) => {
    res.send('Update the book')
  })
```

## express.Router

Create modular, mountable route handlers. A Router instance is a complete middleware and routing system, often referred to as a "mini-app".

### Router module file (birds.js)
```javascript
const express = require('express')
const router = express.Router()

// Middleware specific to this router
const timeLog = (req, res, next) => {
  console.log('Time: ', Date.now())
  next()
}
router.use(timeLog)

// Routes
router.get('/', (req, res) => {
  res.send('Birds home page')
})

router.get('/about', (req, res) => {
  res.send('About birds')
})

module.exports = router
```

### Using the router in main app
```javascript
const birds = require('./birds')
app.use('/birds', birds)

// Now handles: /birds and /birds/about
```

### Router with merged parameters
```javascript
const router = express.Router({ mergeParams: true })
```

This allows sub-routes to access parent route parameters.

## Query Parameters

Query parameters are sent in the URL after the `?` symbol:

```javascript
// Request: GET /search?q=express&limit=10
app.get('/search', (req, res) => {
  console.log(req.query)  // { q: 'express', limit: '10' }
  res.send(`Searching for: ${req.query.q}`)
})
```

## Best Practices for Routing

1. **Use Router for modular organization** - Break routes into separate files
2. **Keep routes simple** - Move complex logic to controllers
3. **Use named parameters** - `/:id` is clearer than wildcards
4. **Validate parameters** - Check parameter values before processing
5. **Use middleware** - Apply validation/auth before reaching route handlers
6. **Consistent naming** - Use descriptive, RESTful path names
7. **Version your API** - Consider `/v1/`, `/v2/` prefixes for versioning

# Express.js RESTful API Design Patterns & Best Practices

## REST Principles

A RESTful API should follow these core principles:

1. **Use HTTP Methods for Actions**
   - GET - Retrieve resources
   - POST - Create new resources
   - PUT - Replace entire resources
   - PATCH - Partial updates
   - DELETE - Remove resources

2. **Use URIs to Identify Resources**
   - `/users` - Collection of users
   - `/users/:id` - Specific user
   - `/posts/:id/comments` - Comments on a post

3. **Use HTTP Response Codes for Status**
   - 2xx - Success
   - 4xx - Client error
   - 5xx - Server error

## RESTful Resource Design

### Naming Conventions

Use plural nouns for resources:
```javascript
// ✓ Good
app.get('/users', ...)           // Get all users
app.post('/users', ...)          // Create a user
app.get('/users/:id', ...)       // Get specific user
app.put('/users/:id', ...)       // Replace user
app.delete('/users/:id', ...)    // Delete user

// ✗ Avoid
app.get('/getUser', ...)         // Verb in endpoint
app.get('/user_list', ...)       // Snake case
app.get('/Users', ...)           // Mixed case
```

### Nested Resources

For related resources, use nesting:
```javascript
// Comments on a post
app.get('/posts/:postId/comments', controller.getComments)
app.post('/posts/:postId/comments', controller.createComment)
app.get('/posts/:postId/comments/:commentId', controller.getComment)

// User's posts
app.get('/users/:userId/posts', controller.getUserPosts)
```

### HTTP Methods

```javascript
// GET - Safe and idempotent, returns data
app.get('/users/:id', (req, res) => {
  const user = findUser(req.params.id)
  res.json(user)
})

// POST - Creates new resource
app.post('/users', (req, res) => {
  const user = createUser(req.body)
  res.status(201).json(user)  // 201 Created
})

// PUT - Replace entire resource
app.put('/users/:id', (req, res) => {
  const user = updateUser(req.params.id, req.body)
  res.json(user)
})

// PATCH - Partial update
app.patch('/users/:id', (req, res) => {
  const user = partialUpdate(req.params.id, req.body)
  res.json(user)
})

// DELETE - Remove resource
app.delete('/users/:id', (req, res) => {
  deleteUser(req.params.id)
  res.sendStatus(204)  // 204 No Content
})
```

## HTTP Status Codes

### 2xx Success
```javascript
res.status(200).json(data)          // 200 OK - Successful GET
res.status(201).json(data)          // 201 Created - Successful POST
res.status(204).send()              // 204 No Content - DELETE
```

### 4xx Client Error
```javascript
res.status(400).json({              // 400 Bad Request
  error: 'Invalid input'
})

res.status(401).json({              // 401 Unauthorized
  error: 'Missing authentication'
})

res.status(403).json({              // 403 Forbidden
  error: 'Insufficient permissions'
})

res.status(404).json({              // 404 Not Found
  error: 'Resource not found'
})

res.status(409).json({              // 409 Conflict
  error: 'Resource already exists'
})

res.status(422).json({              // 422 Unprocessable Entity
  error: 'Invalid data'
})
```

### 5xx Server Error
```javascript
res.status(500).json({              // 500 Internal Server Error
  error: 'Server error'
})

res.status(503).json({              // 503 Service Unavailable
  error: 'Service temporarily unavailable'
})
```

## API Versioning

Version your API to manage breaking changes:

```javascript
// v1 API
app.use('/api/v1/users', require('./v1/users'))
app.use('/api/v1/posts', require('./v1/posts'))

// v2 API with breaking changes
app.use('/api/v2/users', require('./v2/users'))
app.use('/api/v2/posts', require('./v2/posts'))

// Current version (optional)
app.use('/api/users', require('./v2/users'))
```

## Request/Response Format

### Consistent JSON Response Structure

```javascript
// Success response
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully"
}

// Error response
{
  "success": false,
  "error": {
    "code": "INVALID_INPUT",
    "message": "Email is required",
    "field": "email"
  }
}

// Paginated response
{
  "success": true,
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "pages": 5
  }
}
```

### Response Middleware

```javascript
app.use((req, res, next) => {
  res.sendSuccess = (data, message = 'Success', status = 200) => {
    res.status(status).json({
      success: true,
      data,
      message
    })
  }

  res.sendError = (error, status = 400) => {
    res.status(status).json({
      success: false,
      error: {
        code: error.code || 'ERROR',
        message: error.message,
        ...(error.field && { field: error.field })
      }
    })
  }

  next()
})

// Usage
app.get('/users/:id', (req, res) => {
  const user = findUser(req.params.id)
  res.sendSuccess(user, 'User retrieved')
})
```

## Pagination

```javascript
app.get('/users', (req, res) => {
  const page = req.query.page || 1
  const limit = req.query.limit || 20
  const offset = (page - 1) * limit

  const users = User.find().skip(offset).limit(limit)
  const total = User.countDocuments()

  res.json({
    data: users,
    pagination: {
      page: parseInt(page),
      limit: parseInt(limit),
      total,
      pages: Math.ceil(total / limit)
    }
  })
})
```

## Filtering & Sorting

```javascript
app.get('/users', (req, res) => {
  let query = User.find()

  // Filtering
  if (req.query.status) {
    query = query.where('status', req.query.status)
  }
  if (req.query.role) {
    query = query.where('role', req.query.role)
  }

  // Sorting
  if (req.query.sort) {
    const sortBy = req.query.sort.startsWith('-') ? '-' : ''
    query = query.sort(req.query.sort)
  } else {
    query = query.sort('-createdAt')  // Default: newest first
  }

  // Pagination
  const page = req.query.page || 1
  const limit = req.query.limit || 20
  query = query.skip((page - 1) * limit).limit(limit)

  const users = query.exec()
  res.json(users)
})

// Usage: /api/users?status=active&sort=-createdAt&page=1&limit=50
```

## Input Validation

```javascript
const { body, validationResult } = require('express-validator')

app.post('/users', [
  body('email').isEmail().normalizeEmail(),
  body('name').trim().notEmpty().escape(),
  body('age').isInt({ min: 0, max: 150 }),
  body('password').isLength({ min: 8 })
], (req, res, next) => {
  const errors = validationResult(req)
  if (!errors.isEmpty()) {
    return res.status(400).json({
      success: false,
      errors: errors.array()
    })
  }

  // Process valid data
  const user = createUser(req.body)
  res.status(201).json({
    success: true,
    data: user
  })
})
```

## Error Handling

```javascript
// Custom error class
class APIError extends Error {
  constructor(code, message, status = 400) {
    super(message)
    this.code = code
    this.status = status
  }
}

// Error handling middleware
app.use((err, req, res, next) => {
  if (err instanceof APIError) {
    return res.status(err.status).json({
      success: false,
      error: {
        code: err.code,
        message: err.message
      }
    })
  }

  // Generic error
  res.status(500).json({
    success: false,
    error: {
      code: 'INTERNAL_ERROR',
      message: 'An unexpected error occurred'
    }
  })
})

// Usage in routes
app.get('/users/:id', (req, res, next) => {
  const user = findUser(req.params.id)
  if (!user) {
    return next(new APIError('USER_NOT_FOUND', 'User not found', 404))
  }
  res.json({ success: true, data: user })
})
```

## Documentation

Use tools like Swagger/OpenAPI to document your API:

```javascript
const swaggerUi = require('swagger-ui-express')
const swaggerDoc = require('./swagger.json')

app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerDoc))
```

## Best Practices Summary

1. **Use consistent naming** - plural nouns, lowercase
2. **Use proper HTTP methods** - GET, POST, PUT, DELETE
3. **Use meaningful status codes** - 200, 201, 400, 404, 500
4. **Version your API** - /api/v1, /api/v2
5. **Validate input** - Always validate request data
6. **Handle errors gracefully** - Provide clear error messages
7. **Implement pagination** - For large datasets
8. **Support filtering/sorting** - For flexible queries
9. **Document thoroughly** - Use Swagger/OpenAPI
10. **Use consistent response format** - Same structure across endpoints

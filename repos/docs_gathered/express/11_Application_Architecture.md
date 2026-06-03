# Express Application Structure & Architecture Best Practices

## Common Project Structure

A well-organized Express.js project typically includes:

```
myapp/
├── config/               # Configuration files
│   ├── database.js
│   ├── env.js
│   └── logger.js
├── controllers/          # Business logic for routes
│   ├── userController.js
│   ├── postController.js
│   └── authController.js
├── models/              # Database models & schemas
│   ├── User.js
│   ├── Post.js
│   └── Comment.js
├── routes/              # API route definitions
│   ├── users.js
│   ├── posts.js
│   ├── auth.js
│   └── index.js
├── middleware/          # Custom middleware
│   ├── authMiddleware.js
│   ├── validationMiddleware.js
│   └── errorHandler.js
├── services/            # Business logic & external integrations
│   ├── userService.js
│   ├── emailService.js
│   └── paymentService.js
├── utils/               # Helper functions
│   ├── validators.js
│   ├── helpers.js
│   └── constants.js
├── public/              # Static files
│   ├── css/
│   ├── js/
│   └── images/
├── views/               # Template files
│   ├── layout.html
│   ├── users.html
│   └── errors.html
├── tests/               # Test files
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── .env                 # Environment variables
├── .gitignore
├── app.js               # Express app setup
├── server.js            # Server startup
├── package.json
└── README.md
```

## Architectural Approaches

### 1. Layered Architecture

Organizes code into functional layers:

**Structure:**
```
Routes Layer → Controllers Layer → Services Layer → Models Layer → Database
```

**Pros:**
- Clear separation of concerns
- Easy to understand flow
- Good for small to medium apps
- Simple to test each layer

**Cons:**
- Can become complex for large apps
- Logic might span multiple files

**Best for:** CRUD applications, simple APIs

**Example:**

```javascript
// routes/users.js
const router = require('express').Router()
const userController = require('../controllers/userController')

router.get('/', userController.getAll)
router.post('/', userController.create)

module.exports = router
```

```javascript
// controllers/userController.js
const userService = require('../services/userService')

exports.getAll = async (req, res, next) => {
  try {
    const users = await userService.getAllUsers()
    res.json(users)
  } catch (err) {
    next(err)
  }
}
```

```javascript
// services/userService.js
const User = require('../models/User')

exports.getAllUsers = async () => {
  return await User.find()
}
```

### 2. Modular Architecture

Organizes code by feature/module rather than function:

**Structure:**
```
features/
├── users/
│   ├── routes.js
│   ├── controller.js
│   ├── service.js
│   ├── model.js
│   └── tests.js
├── posts/
│   ├── routes.js
│   ├── controller.js
│   ├── service.js
│   ├── model.js
│   └── tests.js
└── auth/
    ├── routes.js
    ├── controller.js
    ├── service.js
    ├── middleware.js
    └── tests.js
```

**Pros:**
- Highly scalable
- Each module is self-contained
- Easy to add/remove features
- Better for large applications
- Team collaboration easier

**Cons:**
- More complex initial setup
- Slightly harder to understand full flow

**Best for:** Large applications, scalable systems

**Example:**

```javascript
// users/routes.js
const router = require('express').Router()
const controller = require('./controller')

router.get('/', controller.getAll)
router.post('/', controller.create)

module.exports = router
```

```javascript
// index.js - Main app file
const express = require('express')
const userRoutes = require('./users/routes')
const postRoutes = require('./posts/routes')
const authRoutes = require('./auth/routes')

const app = express()

app.use('/api/users', userRoutes)
app.use('/api/posts', postRoutes)
app.use('/api/auth', authRoutes)

module.exports = app
```

## Key Organizational Principles

### 1. Separation of Concerns
- **Routes**: Define API endpoints only
- **Controllers**: Handle HTTP requests/responses
- **Services**: Contain business logic
- **Models**: Define data structure
- **Middleware**: Handle cross-cutting concerns

### 2. Single Responsibility
Each file should have one reason to change:

```javascript
// ✓ Good - focused responsibility
// userValidator.js
function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

// ✗ Bad - multiple responsibilities
// user.js
function validateEmail(email) { /* ... */ }
function hashPassword(password) { /* ... */ }
function fetchFromDB(id) { /* ... */ }
```

### 3. Reusable Components
Abstract common functionality:

```javascript
// middleware/validationMiddleware.js
function validateRequest(schema) {
  return (req, res, next) => {
    const { error, value } = schema.validate(req.body)
    if (error) return res.status(400).json({ error: error.details })
    req.validated = value
    next()
  }
}

// routes/users.js
const { userSchema } = require('../validators')
router.post('/', validateRequest(userSchema), controller.create)
```

## Recommended Project Flow

```
Client Request
    ↓
Routes (URL matching)
    ↓
Middleware (Auth, Validation)
    ↓
Controller (Handle request)
    ↓
Service (Business logic)
    ↓
Model (Database operations)
    ↓
Database
    ↓
Response
```

## Configuration Management

```javascript
// config/env.js
module.exports = {
  development: {
    database: 'mongodb://localhost:27017/myapp',
    port: 3000,
    debug: true
  },
  production: {
    database: process.env.DATABASE_URL,
    port: process.env.PORT || 3000,
    debug: false
  }
}
```

## Error Handling Architecture

```javascript
// middleware/errorHandler.js
module.exports = (err, req, res, next) => {
  const status = err.status || 500
  const message = err.message || 'Internal Server Error'

  res.status(status).json({
    error: {
      status,
      message,
      ...(process.env.NODE_ENV === 'development' && { stack: err.stack })
    }
  })
}
```

## Testing Architecture

```javascript
// tests/unit/userService.test.js
const userService = require('../../services/userService')

describe('User Service', () => {
  it('should get all users', async () => {
    const users = await userService.getAllUsers()
    expect(Array.isArray(users)).toBe(true)
  })
})

// tests/integration/users.test.js
const request = require('supertest')
const app = require('../../app')

describe('Users API', () => {
  it('should get all users', async () => {
    const res = await request(app).get('/api/users')
    expect(res.status).toBe(200)
  })
})
```

## Scaling Considerations

### 1. Microservices
As the app grows, consider splitting into microservices:
- User service
- Post service
- Auth service
- Payment service

### 2. API Versioning
```javascript
app.use('/api/v1/users', userRoutesV1)
app.use('/api/v2/users', userRoutesV2)
```

### 3. Feature Flags
```javascript
if (process.env.FEATURE_NEW_DASHBOARD) {
  app.use('/api/dashboard', dashboardRoutes)
}
```

## Why Structure Matters

By structuring your Express.js project properly, you:
- Create scalable, maintainable, organized codebases
- Make code easy to debug and extend
- Facilitate team collaboration
- Improve code reusability
- Simplify testing
- Enable easier deployment

# Express.js Testing Guide

## Testing Overview

Express applications require multiple levels of testing:

1. **Unit Tests** - Test individual components in isolation
2. **Integration Tests** - Test components working together
3. **End-to-End Tests** - Test complete user workflows

## Popular Testing Frameworks

### Jest
A comprehensive JavaScript testing framework with excellent Express support.

**Installation:**
```bash
npm install --save-dev jest
```

**Configuration (package.json):**
```json
{
  "scripts": {
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  }
}
```

### Mocha
Traditional testing framework popular with Node.js developers.

**Installation:**
```bash
npm install --save-dev mocha chai
```

### SuperTest
HTTP assertion library specifically designed for testing Express apps.

**Installation:**
```bash
npm install --save-dev supertest
```

## Unit Testing

### Testing Controllers

```javascript
// controllers/userController.js
exports.getUser = async (req, res, next) => {
  try {
    const user = await User.findById(req.params.id)
    if (!user) {
      return res.status(404).json({ error: 'Not found' })
    }
    res.json(user)
  } catch (err) {
    next(err)
  }
}

// tests/unit/userController.test.js
const controller = require('../../controllers/userController')
const User = require('../../models/User')

jest.mock('../../models/User')

describe('User Controller', () => {
  afterEach(() => {
    jest.clearAllMocks()
  })

  it('should get a user by ID', async () => {
    const mockUser = { _id: '1', name: 'John' }
    User.findById.mockResolvedValue(mockUser)

    const req = { params: { id: '1' } }
    const res = {
      json: jest.fn(),
      status: jest.fn().mockReturnThis()
    }
    const next = jest.fn()

    await controller.getUser(req, res, next)

    expect(User.findById).toHaveBeenCalledWith('1')
    expect(res.json).toHaveBeenCalledWith(mockUser)
  })

  it('should return 404 when user not found', async () => {
    User.findById.mockResolvedValue(null)

    const req = { params: { id: '1' } }
    const res = {
      json: jest.fn(),
      status: jest.fn().mockReturnThis()
    }
    const next = jest.fn()

    await controller.getUser(req, res, next)

    expect(res.status).toHaveBeenCalledWith(404)
  })
})
```

### Testing Services

```javascript
// services/userService.js
exports.getUserById = async (id) => {
  return await User.findById(id)
}

// tests/unit/userService.test.js
const service = require('../../services/userService')
const User = require('../../models/User')

jest.mock('../../models/User')

describe('User Service', () => {
  it('should fetch user by ID', async () => {
    const mockUser = { _id: '1', name: 'John' }
    User.findById.mockResolvedValue(mockUser)

    const user = await service.getUserById('1')

    expect(user).toEqual(mockUser)
    expect(User.findById).toHaveBeenCalledWith('1')
  })
})
```

### Testing Middleware

```javascript
// middleware/auth.js
exports.authenticate = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1]
  if (!token) {
    return res.status(401).json({ error: 'No token' })
  }
  req.user = { id: 'user123' }
  next()
}

// tests/unit/authMiddleware.test.js
const auth = require('../../middleware/auth')

describe('Auth Middleware', () => {
  it('should authenticate valid token', () => {
    const req = {
      headers: {
        authorization: 'Bearer valid-token'
      }
    }
    const res = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn()
    }
    const next = jest.fn()

    auth.authenticate(req, res, next)

    expect(req.user).toEqual({ id: 'user123' })
    expect(next).toHaveBeenCalled()
  })

  it('should reject missing token', () => {
    const req = { headers: {} }
    const res = {
      status: jest.fn().mockReturnThis(),
      json: jest.fn()
    }
    const next = jest.fn()

    auth.authenticate(req, res, next)

    expect(res.status).toHaveBeenCalledWith(401)
  })
})
```

## Integration Testing

### Testing Routes with SuperTest

```javascript
// tests/integration/users.test.js
const request = require('supertest')
const app = require('../../app')
const User = require('../../models/User')

describe('Users API', () => {
  beforeAll(async () => {
    // Connect to test database
    await setupTestDatabase()
  })

  afterAll(async () => {
    await closeDatabase()
  })

  afterEach(async () => {
    await User.deleteMany({})
  })

  describe('GET /api/users', () => {
    it('should retrieve all users', async () => {
      // Create test data
      const user = await User.create({
        name: 'John',
        email: 'john@example.com'
      })

      const res = await request(app).get('/api/users')

      expect(res.status).toBe(200)
      expect(res.body).toBeInstanceOf(Array)
      expect(res.body.length).toBe(1)
      expect(res.body[0].email).toBe('john@example.com')
    })
  })

  describe('GET /api/users/:id', () => {
    it('should retrieve a specific user', async () => {
      const user = await User.create({
        name: 'John',
        email: 'john@example.com'
      })

      const res = await request(app).get(`/api/users/${user._id}`)

      expect(res.status).toBe(200)
      expect(res.body.email).toBe('john@example.com')
    })

    it('should return 404 for nonexistent user', async () => {
      const res = await request(app).get('/api/users/invalid-id')

      expect(res.status).toBe(404)
    })
  })

  describe('POST /api/users', () => {
    it('should create a new user', async () => {
      const res = await request(app)
        .post('/api/users')
        .send({
          name: 'John',
          email: 'john@example.com',
          password: 'password123'
        })

      expect(res.status).toBe(201)
      expect(res.body.email).toBe('john@example.com')

      const savedUser = await User.findOne({ email: 'john@example.com' })
      expect(savedUser).toBeDefined()
    })

    it('should validate required fields', async () => {
      const res = await request(app)
        .post('/api/users')
        .send({
          name: 'John'
          // Missing email and password
        })

      expect(res.status).toBe(400)
      expect(res.body.errors).toBeDefined()
    })
  })

  describe('PUT /api/users/:id', () => {
    it('should update a user', async () => {
      const user = await User.create({
        name: 'John',
        email: 'john@example.com'
      })

      const res = await request(app)
        .put(`/api/users/${user._id}`)
        .send({
          name: 'Jane'
        })

      expect(res.status).toBe(200)
      expect(res.body.name).toBe('Jane')

      const updated = await User.findById(user._id)
      expect(updated.name).toBe('Jane')
    })
  })

  describe('DELETE /api/users/:id', () => {
    it('should delete a user', async () => {
      const user = await User.create({
        name: 'John',
        email: 'john@example.com'
      })

      const res = await request(app).delete(`/api/users/${user._id}`)

      expect(res.status).toBe(204)

      const deleted = await User.findById(user._id)
      expect(deleted).toBeNull()
    })
  })
})
```

### Testing Middleware Chain

```javascript
// tests/integration/middleware.test.js
const request = require('supertest')
const app = require('../../app')

describe('Middleware Chain', () => {
  it('should process request through middleware', async () => {
    const res = await request(app)
      .post('/api/users')
      .set('Authorization', 'Bearer token')
      .send({ name: 'John' })

    // Should have passed through:
    // 1. Logger middleware
    // 2. Auth middleware
    // 3. Validation middleware
    // 4. Route handler
    expect(res.status).toBeLessThan(500)
  })
})
```

## Database Testing

### Using Test Fixtures

```javascript
// tests/fixtures/users.js
module.exports = [
  {
    name: 'John Doe',
    email: 'john@example.com'
  },
  {
    name: 'Jane Smith',
    email: 'jane@example.com'
  }
]

// tests/integration/users.test.js
const fixtures = require('../fixtures/users')

beforeEach(async () => {
  await User.insertMany(fixtures)
})
```

### Test Database Setup

```javascript
// tests/setup.js
const mongoose = require('mongoose')

beforeAll(async () => {
  await mongoose.connect(process.env.TEST_DATABASE_URL)
})

afterAll(async () => {
  await mongoose.disconnect()
})

// In package.json:
// "test": "jest --setupFilesAfterEnv ./tests/setup.js"
```

## Common Testing Patterns

### Testing Async Routes

```javascript
it('should handle async errors', async () => {
  // Mock service to throw error
  userService.getUser = jest.fn().mockRejectedValue(
    new Error('Database error')
  )

  const res = await request(app).get('/api/users/1')

  expect(res.status).toBe(500)
})
```

### Testing with Queries

```javascript
it('should filter users by status', async () => {
  await User.create({ name: 'John', status: 'active' })
  await User.create({ name: 'Jane', status: 'inactive' })

  const res = await request(app)
    .get('/api/users?status=active')

  expect(res.body.length).toBe(1)
  expect(res.body[0].name).toBe('John')
})
```

## Coverage

Check test coverage:

```bash
npm run test:coverage
```

Look for:
- **Line coverage**: Percentage of code lines executed
- **Branch coverage**: Percentage of conditional branches tested
- **Function coverage**: Percentage of functions called

Target: 80%+ coverage for critical paths

## Best Practices

1. **Test behavior, not implementation** - Focus on what the code does, not how
2. **Use descriptive test names** - Clearly state what is being tested
3. **One assertion per test** - Easier to understand failures
4. **Keep tests isolated** - Tests should not depend on each other
5. **Mock external dependencies** - Don't rely on database/APIs
6. **Use fixtures** - Reusable test data
7. **Clean up after tests** - Reset state between tests
8. **Test happy path and error cases** - Cover both success and failure

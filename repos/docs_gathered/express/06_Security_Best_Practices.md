# Express.js Security Best Practices

## Core Security Best Practices

### 1. Use Updated Express Versions
- Avoid Express 2.x and 3.x (no longer maintained)
- Use Express 4.x or later
- Check the Security updates page for vulnerable versions
- Migrate using the official migration guide

### 2. Use TLS (Transport Layer Security)
- Encrypt data in transit between client and server
- Use TLS instead of deprecated SSL
- Use Nginx to handle TLS configuration
- Obtain free TLS certificates from [Let's Encrypt](https://letsencrypt.org/)

### 3. Never Trust User Input
Validate and sanitize all user input to prevent:
- Cross-site scripting (XSS) attacks
- SQL injection attacks
- Command injection attacks
- Open redirects

**Example - Prevent Open Redirects:**
```javascript
app.use((req, res) => {
  try {
    if (new URL(req.query.url).host !== 'example.com') {
      return res.status(400).end(`Unsupported redirect to host: ${req.query.url}`)
    }
  } catch (e) {
    return res.status(400).end(`Invalid url: ${req.query.url}`)
  }
  res.redirect(req.query.url)
})
```

### 4. Use Helmet Middleware
Helmet sets critical security HTTP headers automatically:

```javascript
const helmet = require('helmet')
app.use(helmet())
```

**Headers set by Helmet:**
- `Content-Security-Policy` - Allow-list for page resources
- `Strict-Transport-Security` - Enforce HTTPS
- `X-Content-Type-Options` - Prevent MIME sniffing
- `X-Frame-Options` - Mitigate clickjacking attacks
- `X-XSS-Protection` - Legacy XSS protection (disabled by default)
- And 8+ additional security headers

### 5. Reduce Server Fingerprinting
Disable the `X-Powered-By` header:

```javascript
app.disable('x-powered-by')
```

Implement custom error handlers:

```javascript
// Custom 404 handler
app.use((req, res, next) => {
  res.status(404).send("Sorry can't find that!")
})

// Custom error handler
app.use((err, req, res, next) => {
  console.error(err.stack)
  res.status(500).send('Something broke!')
})
```

### 6. Secure Cookie Configuration

**Don't use default session cookie names:**
```javascript
const session = require('express-session')
app.set('trust proxy', 1)
app.use(session({
  secret: 's3Cur3',
  name: 'sessionId'  // Generic name instead of default
}))
```

**Set cookie security options:**
```javascript
const session = require('cookie-session')
const expiryDate = new Date(Date.now() + 60 * 60 * 1000) // 1 hour

app.use(session({
  name: 'session',
  keys: ['key1', 'key2'],
  cookie: {
    secure: true,        // HTTPS only
    httpOnly: true,      // No client-side JavaScript access
    domain: 'example.com',
    path: 'foo/bar',
    expires: expiryDate
  }
}))
```

**Cookie Security Options:**
- `secure` - Browser only sends cookie over HTTPS
- `httpOnly` - Cookie inaccessible to client JavaScript; protects against XSS
- `domain` - Restrict cookie to specific domain
- `path` - Restrict cookie to specific path
- `expires` - Set expiration date
- `sameSite` - Prevent CSRF attacks ("Strict", "Lax", or "None")

### 7. Prevent Brute-Force Authorization Attacks
Implement rate-limiting using two metrics:
1. Consecutive failed attempts by same username + IP address
2. Total failed attempts from an IP address over time (e.g., 100 attempts/day)

**Recommended tool:** [rate-limiter-flexible](https://github.com/animir/node-rate-limiter-flexible)

### 8. Ensure Dependency Security
Use npm's built-in security tools:

```bash
# Automatic with npm 6+
npm audit

# Or use Snyk for enhanced protection
npm install -g snyk
snyk test
```

Check databases for vulnerabilities:
- [Node Security Project Advisories](https://npmjs.com/advisories)
- [Snyk Vulnerability Database](https://snyk.io/vuln/)

## Additional Security Recommendations

| Threat | Tool/Practice |
|--------|---------------|
| SQL Injection | Use parameterized queries/prepared statements |
| XSS Attacks | Filter and sanitize all user input |
| SSL/TLS Issues | Test with `nmap` and `sslyze` |
| SQL Injection Vulnerabilities | Scan with `sqlmap` tool |
| ReDoS Attacks | Use `safe-regex` package for regex validation |

## Input Validation Strategies

### Validate All User Input
```javascript
const { body, validationResult } = require('express-validator')

app.post('/user', [
  body('email').isEmail(),
  body('name').trim().notEmpty(),
  body('age').isInt({ min: 0, max: 120 })
], (req, res) => {
  const errors = validationResult(req)
  if (!errors.isEmpty()) {
    return res.status(400).json({ errors: errors.array() })
  }
  // Process valid input
})
```

### Sanitize Output
```javascript
app.get('/user/:id', (req, res) => {
  const user = getUserById(req.params.id)
  // Never concatenate user data directly into HTML
  res.send(`<h1>${user.name}</h1>`)  // ❌ XSS vulnerable

  // Use template escaping or JSON
  res.json(user)  // ✓ Safe - JSON is auto-escaped
})
```

## Authentication & Authorization

### OAuth 2.1 and OpenID Connect
Recommended for user authentication with third-party providers.

### JWT (JSON Web Tokens)
Use short-lived JWTs for API authentication:

```javascript
const jwt = require('jsonwebtoken')

// Generate token
const token = jwt.sign({ id: user.id }, process.env.JWT_SECRET, {
  expiresIn: '1h'
})

// Verify token
const verify = (req, res, next) => {
  const token = req.headers.authorization?.split(' ')[1]
  if (!token) return res.status(401).send('No token')

  try {
    const decoded = jwt.verify(token, process.env.JWT_SECRET)
    req.user = decoded
    next()
  } catch (err) {
    res.status(401).send('Invalid token')
  }
}
```

### mTLS for Service-to-Service
Use mutual TLS for communication between services.

## Resources
- [OWASP Top Ten Web Vulnerabilities](https://www.owasp.org/www-project-top-ten/)
- [Node.js Security Checklist](https://blog.risingstack.com/node-js-security-checklist/)
- [Helmet.js Documentation](https://helmetjs.github.io/)

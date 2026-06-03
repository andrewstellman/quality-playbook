# Express Database Integration Guide

This guide covers integrating popular databases with Express apps by loading appropriate Node.js drivers.

## Database Options & Setup

### MongoDB

**Module**: `mongodb` or `mongoose` (recommended for object modeling)

**Installation**:
```bash
npm install mongodb
# Or for Mongoose ODM:
npm install mongoose
```

**Native MongoDB Driver Example:**
```javascript
const MongoClient = require('mongodb').MongoClient

MongoClient.connect('mongodb://localhost:27017/animals', (err, client) => {
  if (err) throw err
  const db = client.db('animals')
  db.collection('mammals').find().toArray((err, result) => {
    if (err) throw err
    console.log(result)
  })
})
```

**Mongoose Example:**
```javascript
const mongoose = require('mongoose')
mongoose.connect('mongodb://localhost:27017/myapp')

const userSchema = new mongoose.Schema({
  name: String,
  email: String
})

const User = mongoose.model('User', userSchema)

User.find({}, (err, users) => {
  if (err) throw err
  console.log(users)
})
```

### PostgreSQL

**Module**: `pg-promise`

**Installation**: `npm install pg-promise`

**Example:**
```javascript
const pgp = require('pg-promise')()
const db = pgp('postgres://username:password@host:port/database')

db.one('SELECT $1 AS value', 123)
  .then((data) => console.log('DATA:', data.value))
  .catch((error) => console.log('ERROR:', error))
```

### MySQL

**Module**: `mysql`

**Installation**: `npm install mysql`

**Example:**
```javascript
const mysql = require('mysql')
const connection = mysql.createConnection({
  host: 'localhost',
  user: 'dbuser',
  password: 's3kreee7',
  database: 'my_db'
})

connection.connect()
connection.query('SELECT 1 + 1 AS solution', (err, rows) => {
  if (err) throw err
  console.log('The solution is: ', rows[0].solution)
})
connection.end()
```

### SQLite

**Module**: `sqlite3`

**Installation**: `npm install sqlite3`

**Example:**
```javascript
const sqlite3 = require('sqlite3').verbose()
const db = new sqlite3.Database(':memory:')

db.serialize(() => {
  db.run('CREATE TABLE lorem (info TEXT)')
  const stmt = db.prepare('INSERT INTO lorem VALUES (?)')

  for (let i = 0; i < 10; i++) {
    stmt.run(`Ipsum ${i}`)
  }
  stmt.finalize()
})
```

### Redis

**Module**: `redis`

**Installation**: `npm install redis`

**Features**: String and hash operations

**Example:**
```javascript
const redis = require('redis')
const client = redis.createClient()

client.set('mykey', 'myvalue', (err, reply) => {
  if (err) throw err
  console.log(reply)
})

client.get('mykey', (err, reply) => {
  if (err) throw err
  console.log(reply)
})
```

### CouchDB

**Module**: `nano`

**Installation**: `npm install nano`

**Features**: Document creation, insertion, and listing

### Cassandra

**Module**: `cassandra-driver`

**Installation**: `npm install cassandra-driver`

**Example:**
```javascript
const cassandra = require('cassandra-driver')
const client = new cassandra.Client({ contactPoints: ['localhost'] })

client.execute('select key from system.local', (err, result) => {
  if (err) throw err
  console.log(result.rows[0])
})
```

### Oracle

**Module**: `oracledb`

**Installation**: `npm install oracledb`

**Features**: Async/await support with connection pooling

### Neo4j

**Module**: `neo4j-driver`

**Installation**: `npm install neo4j-driver`

### SQL Server

**Module**: `tedious`

**Installation**: `npm install tedious`

### Couchbase

**Module**: `couchnode`

**Installation**: `npm install couchbase`

**Features**: Document insertion and N1QL queries

### LevelDB

**Module**: `levelup`

**Installation**: `npm install level levelup leveldown`

**Features**: Key-value store operations

### Elasticsearch

**Module**: `elasticsearch`

**Installation**: `npm install elasticsearch`

**Features**: Full-text search capabilities

## Best Practices for Database Integration

### 1. Use Connection Pooling
Most database drivers support connection pooling to improve performance:

```javascript
const pool = mysql.createPool({
  connectionLimit: 10,
  host: 'localhost',
  user: 'user',
  password: 'password',
  database: 'db'
})

pool.query('SELECT * FROM users', (err, rows) => {
  // Connection is released back to pool
})
```

### 2. Handle Errors Properly
```javascript
app.post('/user', async (req, res, next) => {
  try {
    const user = await User.create(req.body)
    res.json(user)
  } catch (err) {
    next(err)  // Pass to error handler
  }
})
```

### 3. Use ORM/ODM for Complex Applications
For medium to large applications, consider using an ORM/ODM:
- **Mongoose** (MongoDB)
- **Sequelize** (SQL databases)
- **TypeORM** (SQL databases)
- **Prisma** (Multi-database)

### 4. Implement Caching
```javascript
app.get('/user/:id', async (req, res, next) => {
  const cacheKey = `user:${req.params.id}`

  // Check cache first
  const cached = await cache.get(cacheKey)
  if (cached) {
    return res.json(JSON.parse(cached))
  }

  // Fetch from database
  const user = await User.findById(req.params.id)

  // Store in cache
  await cache.set(cacheKey, JSON.stringify(user), 'EX', 3600)

  res.json(user)
})
```

### 5. Use Parameterized Queries
Prevent SQL injection by using parameterized queries:

```javascript
// Safe - uses parameterized query
db.query('SELECT * FROM users WHERE id = $1', [userId])

// Unsafe - string concatenation (vulnerable to SQL injection)
db.query(`SELECT * FROM users WHERE id = ${userId}`)
```

## CRUD Operations with Express

### Example: MongoDB with Mongoose
```javascript
// CREATE
app.post('/users', async (req, res, next) => {
  try {
    const user = await User.create(req.body)
    res.status(201).json(user)
  } catch (err) {
    next(err)
  }
})

// READ
app.get('/users/:id', async (req, res, next) => {
  try {
    const user = await User.findById(req.params.id)
    res.json(user)
  } catch (err) {
    next(err)
  }
})

// UPDATE
app.put('/users/:id', async (req, res, next) => {
  try {
    const user = await User.findByIdAndUpdate(req.params.id, req.body, { new: true })
    res.json(user)
  } catch (err) {
    next(err)
  }
})

// DELETE
app.delete('/users/:id', async (req, res, next) => {
  try {
    await User.findByIdAndDelete(req.params.id)
    res.sendStatus(204)
  } catch (err) {
    next(err)
  }
})
```

## Additional Resources
- For more database options, search the [npm registry](https://www.npmjs.com/)
- MongoDB is extremely popular in the Node community due to JSON-like document storage
- Mongoose provides comfortable API and object modeling for MongoDB

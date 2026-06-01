# Express.js Getting Started Guide

## Complete Hello World Example

```javascript
const express = require('express')
const app = express()
const port = 3000

app.get('/', (req, res) => {
  res.send('Hello World!')
})

app.listen(port, () => {
  console.log(`Example app listening on port ${port}`)
})
```

## What This App Does

- Starts a server listening on **port 3000**
- Responds with **"Hello World!"** for requests to the root URL (`/`)
- Returns a **404 Not Found** for any other path

## Installation and Setup Steps

### 1. Create a directory
```bash
mkdir myapp
cd myapp
```

### 2. Initialize npm
```bash
npm init
```

### 3. Install Express
```bash
npm install express
```

### 4. Create `app.js`
Copy the Hello World example code above into a file named `app.js`

### 5. Run the app
```bash
node app.js
```

### 6. View in browser
Load `http://localhost:3000/` to see the output

## Key Notes

- The `req` (request) and `res` (response) are standard Node.js objects
- You can use Node methods like `req.pipe()` and `req.on('data', callback)`
- This is a minimal single-file app
- For a full scaffolded project structure, use the Express generator

## What is Express?

Express is a minimal and flexible Node.js web framework that provides:
- A thin layer of fundamental web app features
- Flexible tools for building single and multi-page web apps and APIs
- A set of utilities for HTTP servers

## Key Concepts for New Users

### Routing
Routing is the process of mapping incoming HTTP requests to handler functions. Express makes this simple with methods like:
- `app.get()` - Handle GET requests
- `app.post()` - Handle POST requests
- `app.put()` - Handle PUT requests
- `app.delete()` - Handle DELETE requests

### Middleware
Middleware functions have access to the request object (`req`), response object (`res`), and the `next` function in the request-response cycle. They can:
- Execute code
- Modify request and response objects
- End the request-response cycle
- Call the next middleware in the stack

### Views and Templates
Express supports various template engines like Pug, EJS, and Handlebars for rendering dynamic HTML.

## Project Structure for Growing Apps

As your app grows beyond a simple example, consider organizing it like this:

```
myapp/
├── app.js              # Main application file
├── routes/             # Route handlers
│   ├── users.js
│   └── posts.js
├── controllers/        # Business logic
│   ├── userController.js
│   └── postController.js
├── models/            # Database models
│   ├── user.js
│   └── post.js
├── views/             # Template files
│   └── index.html
├── public/            # Static files
│   ├── css/
│   ├── js/
│   └── images/
└── package.json       # Project dependencies
```

## Next Steps

1. Learn about routing in detail
2. Understand middleware
3. Explore template engines
4. Set up error handling
5. Connect a database
6. Deploy to production

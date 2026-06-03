# Express.js Template Engines & Views

## Overview

Template engines allow you to use static template files with placeholders that are replaced with actual data at runtime. This enables dynamic HTML generation.

## How Template Engines Work

A template engine works by:

1. Creating a template file with placeholders for variables
2. Passing variables/data into the template at runtime
3. Compiling the template with actual values
4. Sending the rendered HTML to the client

## Setting Up Express Views

To render views in Express, you need to:

### 1. Configure the Template Engine
```javascript
app.set('view engine', 'ejs')  // Use EJS as template engine
```

### 2. Set the Views Directory
```javascript
app.set('views', './views')  // Define where template files are located
```

### 3. Render Templates
```javascript
app.get('/', (req, res) => {
  res.render('index', { title: 'Home' })
})
```

The `render` method looks in the views folder and passes the data object to the template.

## Popular Template Engines

### EJS (Embedded JavaScript)

Simple, flexible, and JavaScript-like syntax.

**Installation:**
```bash
npm install ejs
```

**Configuration:**
```javascript
app.set('view engine', 'ejs')
```

**Template Example (views/index.ejs):**
```html
<!DOCTYPE html>
<html>
<head>
  <title><%= title %></title>
</head>
<body>
  <h1><%= title %></h1>
  <ul>
    <% users.forEach(user => { %>
      <li><%= user.name %></li>
    <% }) %>
  </ul>
</body>
</html>
```

**Route Handler:**
```javascript
app.get('/', (req, res) => {
  const users = [
    { name: 'John' },
    { name: 'Jane' }
  ]
  res.render('index', { title: 'Users', users })
})
```

### Pug (formerly Jade)

Minimal syntax with implicit closing tags.

**Installation:**
```bash
npm install pug
```

**Configuration:**
```javascript
app.set('view engine', 'pug')
```

**Template Example (views/index.pug):**
```pug
doctype html
html
  head
    title= title
  body
    h1= title
    ul
      each user in users
        li= user.name
```

### Handlebars

Logic-less templates with clean syntax.

**Installation:**
```bash
npm install express-handlebars
```

**Configuration:**
```javascript
const exphbs = require('express-handlebars')
app.engine('handlebars', exphbs.engine())
app.set('view engine', 'handlebars')
```

**Template Example (views/index.handlebars):**
```html
<h1>{{title}}</h1>
<ul>
  {{#each users}}
    <li>{{this.name}}</li>
  {{/each}}
</ul>
```

### Other Popular Options

- **Mustache** - Logic-less templates
- **Nunjucks** - Powerful with template inheritance
- **Eta** - Lightweight and flexible
- **Marko** - Performance-focused
- **HBS** - Handlebars for Express

## Template Features

### Passing Data to Templates

```javascript
app.get('/user/:id', (req, res) => {
  const user = {
    name: 'John Doe',
    email: 'john@example.com',
    role: 'admin'
  }

  res.render('user', { user })
})
```

**In template (EJS):**
```html
<h1><%= user.name %></h1>
<p>Email: <%= user.email %></p>
<p>Role: <%= user.role %></p>
```

### Partials/Includes

Break templates into reusable components:

**views/header.ejs:**
```html
<header>
  <nav>
    <a href="/">Home</a>
    <a href="/about">About</a>
  </nav>
</header>
```

**views/index.ejs:**
```html
<!DOCTYPE html>
<html>
<head>
  <title>Home</title>
</head>
<body>
  <%- include('header') %>
  <main>
    <h1>Welcome</h1>
  </main>
</body>
</html>
```

### Template Inheritance/Layouts

Create a base layout and extend it:

**views/layout.pug:**
```pug
doctype html
html
  head
    title= pageTitle
  body
    nav
      a(href='/') Home
      a(href='/about') About
    block content
    footer
      p &copy; 2024 My Site
```

**views/index.pug:**
```pug
extends layout

block content
  h1= title
  p Welcome to our site
```

## Best Practices

### 1. Separate Logic from Templates
```javascript
// ✓ Good - logic in controller
app.get('/users', (req, res) => {
  const users = User.find()
  const sortedUsers = users.sort((a, b) => a.name.localeCompare(b.name))
  res.render('users', { users: sortedUsers })
})

// ✗ Bad - logic in template
// In template: <%= users.sort((a,b) => ...) %>
```

### 2. Use Partials for Reusable Components
```javascript
// components/userCard.ejs
<div class="user-card">
  <h3><%= name %></h3>
  <p><%= email %></p>
</div>

// In parent template
<% users.forEach(user => { %>
  <%- include('components/userCard', { name: user.name, email: user.email }) %>
<% }) %>
```

### 3. Escape User Input (XSS Prevention)
```javascript
// EJS - <%= escapes automatically, <%- does not
<p><%= user.bio %></p>      // Safe - escapes HTML
<p><%- user.bio %></p>      // Unsafe - renders HTML (avoid for user input)

// Pug - escapes by default
p= user.bio                // Safe
p!= user.bio               // Unsafe
```

### 4. Use Conditional Rendering
```html
<!-- EJS -->
<% if (user.role === 'admin') { %>
  <button>Delete User</button>
<% } %>

<!-- Pug -->
if user.role === 'admin'
  button Delete User
```

### 5. Iterating Over Arrays
```javascript
// EJS
<ul>
  <% users.forEach(user => { %>
    <li><%= user.name %></li>
  <% }) %>
</ul>

// Pug
ul
  each user in users
    li= user.name
```

## Rendering from Controllers

**Common pattern:**
```javascript
// controllers/userController.js
exports.index = async (req, res, next) => {
  try {
    const users = await User.find()
    res.render('users/index', {
      title: 'Users',
      users,
      message: 'User list'
    })
  } catch (err) {
    next(err)
  }
}

// Route
app.get('/users', userController.index)
```

## Template Engine Configuration

### Caching in Production
```javascript
if (process.env.NODE_ENV === 'production') {
  app.set('view cache', true)  // Cache compiled templates
}
```

### Custom Options by Engine

**EJS options:**
```javascript
const ejs = require('ejs')
res.render('index', {
  title: 'Home',
  cache: true,
  client: false
})
```

**Handlebars options:**
```javascript
const exphbs = require('express-handlebars')
app.engine('handlebars', exphbs.engine({
  defaultLayout: 'main',
  layoutsDir: __dirname + '/views/layouts',
  partialsDir: __dirname + '/views/partials'
}))
```

## Error Handling in Templates

```javascript
app.get('/user/:id', async (req, res, next) => {
  try {
    const user = await User.findById(req.params.id)
    if (!user) {
      res.status(404).render('404', { message: 'User not found' })
    } else {
      res.render('user', { user })
    }
  } catch (err) {
    next(err)
  }
})
```

## Common Pitfalls

1. **Forgetting to install the engine** - Always run `npm install`
2. **Wrong engine name** - Match the extension with `view engine`
3. **Missing views directory** - Create `views` folder
4. **Not escaping user input** - Always escape in templates
5. **Logic in templates** - Keep templates for display only
6. **Not using partials** - Reuse components to reduce duplication

## Performance Tips

1. **Enable caching in production**
2. **Use efficient template syntax**
3. **Minimize template file sizes**
4. **Consider pre-compiled templates**
5. **Cache rendered output when possible**
6. **Use streaming for large responses**

```javascript
// Streaming large responses
app.get('/large-list', (req, res) => {
  res.setHeader('Content-Type', 'text/html')
  res.write('<!DOCTYPE html><html><body>')

  // Stream items
  for (let i = 0; i < 10000; i++) {
    res.write(`<p>Item ${i}</p>`)
  }

  res.write('</body></html>')
  res.end()
})
```

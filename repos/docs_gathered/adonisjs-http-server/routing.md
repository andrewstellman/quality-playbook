# Routing

The routing subsystem is implemented across `src/router/main.ts` and its sibling files (`route.ts`, `group.ts`, `resource.ts`, `brisk.ts`, `store.ts`, `matchers.ts`). The `Router` class is exported from the package root and is also accessible through `server.getRouter()`.

## Registration phase vs commit phase

Route definitions exist in two temporal phases:

- **Registration phase** — after constructing the `Router` (or the `Server`) and before calling `commit()` / `server.boot()`. During this phase, routes are accumulated in a pending array `#routesToBeCommitted`. No matching is possible.
- **Committed phase** — after `commit()` is called, all pending routes are flattened (see `toRoutesJSON`), duplicate route names within the same domain cause a `RuntimeException`, and every route is added to the `RoutesStore`. The router is then frozen; new route definitions have no effect.

## Route registration API

```ts
// Verb-specific shortcuts
router.get(pattern, handler)
router.post(pattern, handler)
router.put(pattern, handler)
router.patch(pattern, handler)
router.delete(pattern, handler)
router.any(pattern, handler)   // HEAD, OPTIONS, GET, POST, PUT, PATCH, DELETE

// Generic form
router.route(pattern, ['GET', 'POST'], handler)
```

`pattern` is a URL pattern string such as `/users/:id` or `/files/*`. Parameters prefixed with `:` are dynamic segments; `*` is a wildcard.

### Handler forms

A handler can be one of three forms:

```ts
// 1. Inline closure
router.get('/ping', (ctx) => ctx.response.send('pong'))

// 2. Controller tuple (lazy import + optional method name)
router.get('/users/:id', [() => import('./controllers/users.ts'), 'show'])

// 3. String binding (resolved through the IoC container)
router.get('/users', 'UsersController.index')
```

## Route instances

`router.get(...)` returns a `Route` instance. The route can be further configured by chaining:

```ts
router
  .get('/admin/dashboard', handler)
  .as('admin.dashboard')                  // named route
  .where('id', /\d+/)                     // param constraint
  .middleware([namedMiddleware.auth()])    // route-level middleware
  .domain('admin.example.com')            // restrict to domain
```

## Route groups

```ts
router.group(() => {
  router.get('/users', handler)
  router.get('/users/:id', handler)
})
.prefix('/api/v1')
.as('api')
.middleware([namedMiddleware.auth()])
.domain('api.example.com')
```

`group` accepts a synchronous callback. Routes registered inside the callback are collected into a `RouteGroup`. After the callback returns, group-level transforms (prefix, name prefix, middleware, domain) are recursively applied to all contained routes.

Groups can be nested; inner group settings override outer group settings on a per-route basis according to the order of application.

## Route resources

```ts
router.resource('photos', PhotosController)
router.shallowResource('posts.comments', CommentsController)
```

`resource` registers the conventional set of seven routes (`index`, `create`, `store`, `show`, `edit`, `update`, `destroy`) for a named resource. `shallowResource` registers the same actions but omits the parent resource identifier from the URL for routes that can be uniquely identified by their own ID.

The resource API supports filtering to a subset of actions:

```ts
router.resource('posts', PostsController).only(['index', 'show'])
router.resource('posts', PostsController).except(['destroy'])
```

Parameter names can be renamed:

```ts
router.resource('posts', PostsController).params({ posts: 'post' })
```

## Brisk routes

A brisk route is a shorthand for redirecting a URL pattern to another destination without writing an explicit handler:

```ts
router.on('/').redirectToPath('/home')
router.on('/').redirect('home.index')
```

`router.on(pattern)` returns a `BriskRoute` which resolves to a regular `Route` once an action (redirect, render, etc.) is set.

## Parameter matchers

```ts
// Global matcher
router.where('id', /\d+/)

// Route-level matcher
router.get('/users/:id', handler).where('id', { match: /\d+/, cast: Number })
```

Matchers restrict which values a dynamic segment can match. The `cast` property transforms the raw string into a typed value before it is placed in `ctx.params`.

## Route store and matching

Committed routes are stored in `RoutesStore`, which uses `@poppinss/matchit` to tokenise patterns. At request time `router.match(uri, method, shouldDecodeParam, hostname?)` returns a `MatchedRoute` or `null`. The matched object contains `params`, `subdomains`, `route`, and `routeKey`.

## Domain-based routing

When routes are assigned a `.domain(...)`, the router sets `usingDomains = true` after commit. At match time the incoming `hostname` header is tested against domain tokens before route tokens.

## Route lookup

```ts
router.find('users.show')         // by name
router.find('UsersController.show') // by controller
router.find('/users/:id')          // by pattern

router.findOrFail('users.show')    // throws if not found
router.has('users.show')           // boolean check
```

Lookup searches the `routes` map (not the `RoutesStore`), so it is available both during and after the registration phase.

## Type generation

```ts
router.generateTypes()
```

Returns a `{ imports, types, routes }` object that can be written to a `.d.ts` file to give the URL builder compile-time route awareness. This is typically invoked by a build-time code-generation step in the AdonisJS framework CLI.

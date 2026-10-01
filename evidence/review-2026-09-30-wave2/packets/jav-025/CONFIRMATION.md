Confirmer: CONFIRMED. contextPath=/blog, plugin on, route /users/{name}: GET /blog/Users/John -> 301 Location=/users/John -> 404.
Docs: :1762 `enableRedirectToLowercasePaths(); // redirect /Users/John to /users/John`; :1508 contextPath "(ex '/blog' if you are hosting an app on a subpath, like 'mydomain.com/blog')". Neither line explicitly promises they combine. TestRedirectToLowercasePathPlugin has no context-path case.
Duplicates: none.
Fixer notes: relies on servlet getContextPath() being "" at root (no removeSuffix). Module suite: 3 WebDriver SessionNotCreated errors (random browser test selection), none in touched code. BUG-049 (same plugin) out of scope.

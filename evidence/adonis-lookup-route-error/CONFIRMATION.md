BUG-023: route lookup failures throw a plain Error instead of E_CANNOT_LOOKUP_ROUTE. CONFIRMED (regression from v6/http-server 7.x).
Claim: router.findOrFail('missing') and router.urlBuilder.urlFor('missing') throw `Error: Cannot lookup route "missing"` with no code/status; not instanceof errors.E_CANNOT_LOOKUP_ROUTE. The class is defined (src/errors.ts:41, JSDoc "Thrown when unable to lookup a route ... when trying to generate URLs or find routes") and listed in ExceptionHandler ignoreExceptions (src/exception_handler.ts:97) but nothing throws it.
Throw sites: src/router/main.ts:545-547 (findOrFail) and src/client/url_builder.ts:54-56 (client builder; browser-safe module, may avoid @poppinss/utils).
Doc: v6-docs_references_exceptions.md "## E_CANNOT_LOOKUP_ROUTE: The exception is raised when you attempt to create a URL for a route using the URL builder." with instanceof example, status 500.
Regression evidence: adonisjs/core#4456 stack trace shows RouteFinder.findOrFail throwing { status: 500, code: 'E_CANNOT_LOOKUP_ROUTE' } on core 6.2.2.
Tests: only assert message text. Keep messages unchanged.
Pushback: client builder is dependency-free on purpose; smallest fix may be only the server-side findOrFail path, or passing an error factory. Logging side-effect (ignoreExceptions) is by design.

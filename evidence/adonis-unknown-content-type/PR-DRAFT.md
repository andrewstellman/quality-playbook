**Title:** fix(response): fall back to octet-stream for unknown content types

## Problem
`response.type()` sets `Content-Type` to `mime.contentType(type)`, which returns `false` for an unknown or empty extension, and the literal string `false` is sent. `download()` calls `type(extname(file))`, so downloading a file like `LICENSE` sends `content-type: false`.

## Fix
Fall back to `application/octet-stream` when the type can't be resolved, as Express's `res.type()` does. This applies to direct `type()` calls too; values that resolve today are unchanged.

## Testing
- npm run quick:test (661 passed)
- npm run typecheck
- npx eslint and prettier --check on the changed files

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

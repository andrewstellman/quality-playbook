**Title:** fix(router): reject non-hex characters in uuid matcher

## Problem
`router.matchers.uuid()` accepts any lowercase letter, not just `a-f`, so `GET /posts/gggggggg-gggg-gggg-gggg-gggggggggggg` reaches a route guarded with `.where('id', router.matchers.uuid())`. The character class in `src/router/matchers.ts` is `[0-9a-zA-F]`; #50 asked for `[0-9A-Fa-f]` and #53 landed `a-z` for the lowercase half.

## Fix
Use `[0-9a-fA-F]`. Valid UUIDs in either case still match.

## Testing
- npm run quick:test (661 passed)
- npm run typecheck
- npx eslint and prettier --check on the changed files

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

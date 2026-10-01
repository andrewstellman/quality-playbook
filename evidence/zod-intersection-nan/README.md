
## Independent re-verification of the submitted branch (2026-09-30)

Re-run from a fresh clone of upstream main (1d1b35a1) and the branch actually pushed to andrewstellman/zod and linked from the issue. Project vitest suite, run from source.
- main as-is: the touched test file passes; the new test doesn't exist yet.
- RED, the branch's test file on unfixed main: exactly 1 failure, the new test.
- GREEN, the pushed branch: all tests in the file pass.
- The issue's code snippets, run verbatim: they misbehave on main and behave correctly on the branch. Controls behave the same on both: 0/-0 merge, and genuinely conflicting intersections still throw.
- Full src/v4 suite: main 2094 passed, branch 2095 passed, 0 failed. The same 5 test files fail to load on both, from missing optional dev dependencies.

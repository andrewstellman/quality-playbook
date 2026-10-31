# BUG-010 reproduction on current cron-parser main

Reproduce-only triage. Nothing was pushed, posted, or sent anywhere. All work is under /tmp/claude-0/sec/cron-parser/.

Record: /tmp/claude-0/sec/records/cron-parser/target/quality/BUGS.md, entry BUG-010 (a crontab line named `__proto__` replaces the prototype of the returned `errors` object in CronFileParser, or is dropped silently). The record's original run was against commit 5b08cdf on 2026-10-05/06.

## Commit and environment

```
$ date -u
Tue Oct 20 15:37:23 UTC 2026
$ git clone --depth 50 https://github.com/harrisiirak/cron-parser src   (GIT_LFS_SKIP_SMUDGE=1)
$ git log -1 --format='%H %cI %s'
a70b68e6bb97171a19d7efbd33c06f301e6f2804 2026-10-11T18:14:17+03:00 fix: accept the RFC 850 and asctime HTTP date formats as string dates (#455)
$ node -e "console.log(require('./package.json').version)"
5.10.2
$ node --version
v22.22.0
$ npm --version
10.9.4
```

Install: `npm ci --ignore-scripts` (completed; npm printed audit advice, not pasted here). Jest version was not re-queried in this run.

## Is the problem still present in src/CronFileParser.ts?

Yes. The last commits touching the file are ea75174 (#451, whitespace-separated fields), aeb2a15 (#417), c8afb3e (#407). None changed the two assignments. Current main, `src/CronFileParser.ts` lines 58 to 70, unmodified:

```ts
      const variableMatch = entry.match(/^(.*)=(.*)$/);
      if (variableMatch) {
        const [, key, value] = variableMatch;
        result.variables[key] = value.replace(/["']/g, ''); // Remove quotes
        continue;
      }

      try {
        const parsedEntry = CronFileParser.#parseEntry(entry);
        result.expressions.push(parsedEntry.interval);
      } catch (err: unknown) {
        result.errors[entry] = err;
      }
```

Both are plain bracket assignments on `{}` literals, so a key of `__proto__` hits the `Object.prototype.__proto__` setter. Line numbers are the same as in the record (61 and 69).

## Reproduction on unmodified main

Script: /tmp/claude-0/sec/cron-parser/notes/repro-bug010.cjs. The project uses nodenext module resolution, so ts-node could not import `../src/src` directly from outside the tree (error ERR_UNSUPPORTED_DIR_IMPORT); the script runs plain node against the compiled `dist/` after `npm run build`. It writes a real temp crontab file and calls both `parseFileSync` and `parseFile`.

Crontab content written: `__proto__`, `__proto__=polluted`, `0 0 * * * ok`, `constructor`, `FOO=bar` (newline separated).

Verbatim output (/tmp/claude-0/sec/cron-parser/notes/repro-main.log):

```
Tue Oct 20 15:38:37 UTC 2026
crontab content: "__proto__\n__proto__=polluted\n0 0 * * * ok\nconstructor\nFOO=bar"
errors keys: [ 'constructor' ]
errors proto is Object.prototype: false
errors proto: TypeError: expression.trim is not a function
    at #getRawFields (/tmp/claude-0/sec/cron-parser/src/dist/CronExpressionParser.js:122:34)
    at CronExpressionParser.parse (/tmp/claude-0/sec/cron-parser/src/dist/CronExpressionParser.js:86:61)
    at #parseEntry (/tmp/claude-0/sec/cron-parser/src/dist/CronFileParser.js:72:67)
    at #parseContent (/tmp/claude-0/sec/cron-parser/src/dist/CronFileParser.js:56:63)
    at CronFileParser.parseFileSync (/tmp/claude-0/sec/cron-parser/src/dist/CronFileParser.js:31:44)
    at Object.<anonymous> (/tmp/claude-0/sec/cron-parser/notes/repro-bug010.cjs:13:31)
    at Module._compile (node:internal/modules/cjs/loader:1706:14)
    at Object..js (node:internal/modules/cjs/loader:1839:10)
    at Module.load (node:internal/modules/cjs/loader:1441:32)
    at Function._load (node:internal/modules/cjs/loader:1263:12)
errors.message (inherited through replaced proto): expression.trim is not a function
JSON.stringify(errors): {"constructor":{}}
variables keys: [ 'FOO' ]
variables proto is Object.prototype: true
variables: { FOO: 'bar' }
expressions count: 1
global Object.prototype polluted? ({}).message: undefined ({}).polluted: undefined
async parseFile: errors proto is Object.prototype: false | errors keys: [ 'constructor' ] | variables keys: [ 'FOO' ]
exit=0
```

What this shows on current main:

- The bare line `__proto__` is not a valid entry, so the parser catches a TypeError and does `result.errors['__proto__'] = err`. That sets the prototype of `errors` to the TypeError object. `Object.keys(errors)` and `JSON.stringify(errors)` no longer show the line, and `errors.message` now resolves to the TypeError's message through the inherited chain.
- The line `__proto__=polluted` is a variable assignment with key `__proto__` and a string value. Assigning a non-object to `__proto__` is a no-op in JS, so the variable is dropped with no error recorded (`variables` has only `FOO`).
- The `constructor` line is recorded normally as an own key (it shadows the inherited `constructor`, no prototype effect).
- `({}).message` and `({}).polluted` are both undefined after parsing: global `Object.prototype` is not modified. Only the returned `errors` object (and, by omission, `variables`) is affected.
- Same result through the async `parseFile`.

Side note (same as in the record): the error for an unparseable one-word line is `TypeError: expression.trim is not a function` rather than a validation error. Not investigated here.

## Red: regression-test patch on unmodified main

Patch /tmp/claude-0/sec/records/cron-parser/target/quality/patches/BUG-010-regression-test.patch applied cleanly with `git apply --check` then `git apply` (no path adjustment needed; it adds tests/regression-BUG-010.test.ts).

```
$ git status --short
?? tests/regression-BUG-010.test.ts
Tue Oct 20 15:38:43 UTC 2026
$ TZ=UTC ./node_modules/.bin/jest --runTestsByPath tests/regression-BUG-010.test.ts --verbose
FAIL tests/regression-BUG-010.test.ts
  ● BUG-010 REQ-023: a crontab line named __proto__ does not replace the prototype of the result objects

    expect(received).toBe(expected) // Object.is equality

    - Expected  - 1
    + Received  + 1

    - Object {}
    + [TypeError: expression.trim is not a function]

      17 |   mockCrontab(['__proto__', '__proto__=polluted', 'ok=1'].join('\n'));
      18 |   const result = CronFileParser.parseFileSync('crontab');
    > 19 |   expect(Object.getPrototypeOf(result.errors)).toBe(Object.prototype);
         |                                                ^
      20 |   expect(Object.getPrototypeOf(result.variables)).toBe(Object.prototype);
      21 |   expect(Object.keys(result.errors)).toEqual(['__proto__']);
      22 |   expect(Object.keys(result.variables)).toEqual(['__proto__', 'ok']);

      at Object.<anonymous> (tests/regression-BUG-010.test.ts:19:48)

Test Suites: 1 failed, 1 total
Tests:       1 failed, 1 total
Snapshots:   0 total
Time:        1.404 s
Ran all test suites within paths "tests/regression-BUG-010.test.ts".
exit=1
```

Full log: /tmp/claude-0/sec/cron-parser/notes/red.log

## Green: fix patch applied

Patch /tmp/claude-0/sec/records/cron-parser/target/quality/patches/BUG-010-fix.patch applied cleanly (`git apply --check` then `git apply`; no adjustment needed. The index line in the patch names an older blob but the context matched).

```
$ git status --short
 M src/CronFileParser.ts
?? tests/regression-BUG-010.test.ts
Tue Oct 20 15:38:50 UTC 2026
$ TZ=UTC ./node_modules/.bin/jest --runTestsByPath tests/regression-BUG-010.test.ts --verbose
Test Suites: 1 passed, 1 total
Tests:       1 passed, 1 total
Snapshots:   0 total
Time:        1.052 s
Ran all test suites within paths "tests/regression-BUG-010.test.ts".
exit=0
```

Full log: /tmp/claude-0/sec/cron-parser/notes/green.log

## Full suite with the fix (`npm test` = eslint + build + tsd + jest --coverage)

```
Tue Oct 20 15:38:57 UTC 2026
$ npm test
> cron-parser@5.10.2 test
> cross-env TZ=UTC npm run lint && npm run test:types && npm run test:coverage
> cron-parser@5.10.2 lint
> eslint .
> cron-parser@5.10.2 test:types
> npm run build && tsd
[...coverage table, all src files 100 / 100 / 100 / 100...]
Test Suites: 8 passed, 8 total
Tests:       349 passed, 349 total
Snapshots:   0 total
Time:        27.576 s
Ran all test suites.
exit=0
```

Full log: /tmp/claude-0/sec/cron-parser/notes/suite.log. The count is 349 including the new regression test (the record's 2026-10-05 baseline was 338; main has gained tests since). I did not run the full suite on unmodified main separately, so the unfixed baseline count on this commit is not recorded here; the red run above shows the added test is the only one that fails before the fix.

Lint run separately as well:

```
Tue Oct 20 15:40:25 UTC 2026
$ npm run lint
> eslint .
lint exit=0
$ npx prettier --check src/CronFileParser.ts tests/regression-BUG-010.test.ts
Checking formatting...
All matched files use Prettier code style!
prettier exit=0
```

Note: `npx eslint tests/regression-BUG-010.test.ts` directly reports "File ignored because no matching configuration was supplied", so the project's eslint config does not cover tests/. `eslint .` passes.

## Repro script against the fixed build (for completeness)

/tmp/claude-0/sec/cron-parser/notes/repro-fixed.log:

```
Tue Oct 20 15:41:24 UTC 2026
crontab content: "__proto__\n__proto__=polluted\n0 0 * * * ok\nconstructor\nFOO=bar"
errors keys: [ '__proto__', 'constructor' ]
errors proto is Object.prototype: true
errors proto: [Object: null prototype] {}
errors.message (inherited through replaced proto): undefined
JSON.stringify(errors): {"__proto__":{},"constructor":{}}
variables keys: [ '__proto__', 'FOO' ]
variables proto is Object.prototype: true
variables: { ['__proto__']: 'polluted', FOO: 'bar' }
expressions count: 1
global Object.prototype polluted? ({}).message: undefined ({}).polluted: undefined
async parseFile: errors proto is Object.prototype: true | errors keys: [ '__proto__', 'constructor' ] | variables keys: [ '__proto__', 'FOO' ]
exit=0
```

(`errors proto: [Object: null prototype] {}` is just how node's console prints `Object.prototype` itself; the line above it confirms identity with `Object.prototype`.)

## Assessment

Who controls the input: whoever supplies the crontab file to `CronFileParser.parseFile()` / `parseFileSync()`, or whoever can write to that file. In the common case this is the application's own config, but SECURITY.md explicitly treats a crafted crontab file as an input surface (it lists both "crontab variable names" and "a crafted crontab file" pointed at `parseFile`).

What an attacker gains: object-integrity corruption of the returned `errors` object only. A line that is exactly `__proto__` makes the parser store the caught TypeError as the prototype of `errors`, so (a) the offending line disappears from `Object.keys`, `for...in`, and `JSON.stringify` output, breaking the "every bad line is reported" contract, and (b) `errors` now inherits `message`, `stack`, `name` from the Error, so consumer code doing `'message' in errors` or `errors.message` sees values derived from the file. A line `__proto__=value` silently vanishes from `variables` (a string assigned to `__proto__` is ignored). Caller-side code that iterates `errors` to decide whether the file is clean sees fewer errors than exist. There is no code execution, no global state change, and no effect on other objects.

Confirmed not global: `({}).message` and `({}).polluted` are undefined after parsing on both the unfixed and fixed builds. `Object.prototype` is untouched because the `__proto__` setter replaces the prototype of that one `errors` instance rather than writing into the shared prototype.

SECURITY.md fit: the policy lists "Prototype pollution or similar object-integrity issues via parsed field values or crontab variable names" as in scope. This is the "similar object-integrity issues via crontab variable names" case literally, so it is inside the maintainer's declared scope even though the practical severity is low (local to the returned object, requires control of the crontab file, no global pollution). My view: LOW, matching the record. If anything is sent it belongs in a private security-policy report rather than a public issue. Nothing was sent in this run.

## Patch

/tmp/claude-0/sec/cron-parser/out/0001-fix-define-crontab-variables-and-errors-as-own-prope.patch

Produced with `git format-patch -1` from local branch `bug010-proto-own-property` (commit 33e0b820adce0b457220462b6092d75b0915b8a7 on top of a70b68e), author and committer Andrew Stellman <andrew@stellman.com>, no trailers. Subject: `fix: define crontab variables and errors as own properties in CronFileParser`. The code change is the record's BUG-010-fix.patch unchanged. The test file is the record's regression test with the Quality Playbook header and the internal `quality/...` path references removed and the test name shortened (no `BUG-010 REQ-023:` prefix); the assertions are identical. The branch was committed locally only, not pushed.

## Not checked

- Full-suite count on unmodified main (only the targeted red run was done before applying the fix).
- Whether `Object.create(null)` for `variables`/`errors` would be a maintainer-preferred alternative (it changes the result objects' prototype, so the test's `toBe(Object.prototype)` expectations would need to change; left as is).
- Other inherited keys beyond `__proto__` and `constructor` (for example a line `hasOwnProperty`), which would shadow inherited methods as own properties; defineProperty does not change that and it was not in the record.
- Jest version on this clone (not queried).

## Files written

- /tmp/claude-0/sec/cron-parser/REPRO.md (this file)
- /tmp/claude-0/sec/cron-parser/out/0001-fix-define-crontab-variables-and-errors-as-own-prope.patch
- /tmp/claude-0/sec/cron-parser/notes/repro-bug010.cjs, repro-main.log, repro-fixed.log, red.log, green.log, suite.log, lint.log, prettier.log
- /tmp/claude-0/sec/cron-parser/src/ (clone; local branch bug010-proto-own-property holds the fix commit; main is untouched)

An earlier attempt to write this file hit a transient disk-full condition (ENOSPC) and left it empty; it was rewritten. No other output was affected (all logs above were written before that and are intact).

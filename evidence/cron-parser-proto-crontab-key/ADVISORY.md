Title: A crontab line or variable named __proto__ replaces the prototype of CronFileParser's result objects

Ecosystem: npm
Package: cron-parser
Affected versions: <= 5.10.2 (CronFileParser; confirmed on 5.10.2 and main at a70b68e)
Patched versions: none yet
Severity: Low (CVSS 3.1 suggestion: 3.3, AV:L/AC:L/PR:L/UI:N/S:U/C:N/I:L/A:N)
CWE: CWE-1321 Improperly Controlled Modification of Object Prototype Attributes
Credit: Andrew Stellman

Description

Your SECURITY.md lists "prototype pollution or similar object-integrity issues via parsed field values or crontab variable names" as in scope, so I am sending this here rather than as a public issue even though the practical impact is low.

`CronFileParser.#parseContent` (src/CronFileParser.ts:61 and :69) stores crontab variables and per-line parse errors with plain bracket assignments on `{}` literals:

    result.variables[key] = value.replace(/["']/g, '');
    ...
    result.errors[entry] = err;

A key of `__proto__` hits the `Object.prototype.__proto__` setter instead of creating a property. Two effects, both local to the returned `result` object (global `Object.prototype` is not modified):

1. A crontab line consisting of `__proto__` fails to parse, and the assignment `result.errors['__proto__'] = err` replaces the prototype of `result.errors` with the TypeError. Every property of that error (`message`, `stack`, `name`) then appears as an inherited property of `errors`, `Object.keys(errors)` omits the line, and code that walks `errors` with `in` or reads `errors.message` sees the error's properties as if they were entries.
2. A variable line `__proto__=value` is dropped silently: `result.variables` neither records it nor reports an error.

Preconditions: the attacker controls the crontab content being parsed. Applications that parse user-supplied crontab files (an admin UI, a scheduler that imports crontabs) and then inspect `errors` or `variables` are the ones affected.

Reproduction (unmodified main a70b68e, 2026-10-20)

Crontab content: `__proto__`, `__proto__=polluted`, `0 0 * * * ok`, `constructor`, `FOO=bar` (one per line), parsed with `CronFileParser.parseFileSync`:

    errors keys: [ 'constructor' ]
    errors proto is Object.prototype: false
    errors proto: TypeError: expression.trim is not a function
    errors.message (inherited through replaced proto): expression.trim is not a function
    variables keys: [ 'FOO' ]
    global Object.prototype polluted? ({}).message: undefined

Same result through the async `parseFile`.

Fix

Define both entries as own properties (`Object.defineProperty` with enumerable, writable and configurable set), so `__proto__` becomes an ordinary key. The patch below does that and adds a regression test in tests/CronFileParser.test.ts. With it: 349/349 tests pass, eslint, prettier and the type tests are clean. Happy to open it as a PR, or you can take the patch directly.

Found with the Quality Playbook (an AI code-review and test-generation skill I maintain); I reproduced it and reviewed the fix myself.

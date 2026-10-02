# Classifier brief 2: what does it take to notice this?

You will be given a list of observed behaviours in a codebase, each with a file:line. The question this time is not whether the behaviour is wrong, but **what a code reviewer would have needed in order to notice it**.

## Inputs

- Your findings list: `findings-<repo>-blind.md` in this folder. Read it with the Read tool.
- The read-only checkout at `/tmp/control/<repo>` (shell tool). Read the cited lines and whatever surrounds them.

Do not open any other file in this folder, nothing in `unblind/` or `classifications/`, and nothing else under `docs/research/` or `evidence/`. No web, no network, don't run the code.

## The question

Imagine a reviewer reading this code who has **not** seen the behaviour description you were given. For each finding, pick the *least* they would need in order to notice the problem:

- `line`: it is wrong on inspection of the cited lines alone. A wrong comparison, a missing argument, a substring match where a token match is needed, an unguarded unpack, a leftover variable.
- `nearby`: they'd need to read a sibling function, docstring, comment or test in the same file or a closely related one, and compare.
- `input`: they'd need to think up a specific input, value or scenario and execute it, in their head or for real. The lines look fine until you try that case.
- `trace`: they'd need to follow behaviour across files or components: a routing contract, a mount, a collator feeding a model, a wrapper around a wrapper.

If two apply, pick the one without which they would not notice it. Answer from your own reading of the code, not from how the description is phrased.

## Output

Return text, no files. One line per finding, in the order given:

```
<ID> | line|nearby|input|trace | one sentence saying what the reviewer needs
```

End with one short paragraph on the findings that were hardest to place.

# Classifier brief

You will be given a list of observed behaviours in a codebase, each with a file:line. For each one, decide what, if anything, establishes that the behaviour is wrong. In software testing this is called the **test oracle**: the thing that tells you whether an output is correct.

## Inputs

- Your findings list: `findings-<repo>-blind.md` in this folder. Read it with the Read tool.
- The read-only checkout of the code at `/tmp/control/<repo>` (shell tool). Read the cited code and anything near it you need: sibling functions, docstrings, comments, tests, README, CONTRIBUTING.

Do not open any other file in this folder or in `unblind/`, and nothing else under `docs/research/` or `evidence/`. Do not use the web or fetch anything from the network. Do not run the code.

## For each finding, answer three things

1. **Oracle.** In one or two sentences, name concretely what tells you this behaviour is wrong. Be specific: a function in the repo (file:line), a docstring or comment (quote it), a named spec section (e.g. "RFC 6265 §5.2.2"), "it raises / hangs / leaks", or "I believe X is expected, but I cannot point to anything."
2. **Type.** Exactly one of:
   - `in-repo`: the correct behaviour is shown by other code in the same repository (a sibling function, a parallel implementation, a docstring, a comment, an existing test, project docs in the checkout).
   - `implicit`: the behaviour is a crash, uncaught exception, hang, panic, or resource leak. No spec needed.
   - `known-external`: the correct behaviour comes from a contract outside the repo (an RFC, a language or library contract, a platform rule) that you already know well enough to cite from memory.
   - `fetch-external`: the correct behaviour comes from something outside the repo that you would have to go and read to be sure (a spec you know exists but can't quote, a project's routing or API contract that isn't in the checkout, a downstream consumer's expectation).
   - `none`: you cannot name an oracle. It may not be a defect, or it may be a matter of taste.
   If two types apply, pick the one you'd actually rely on, and say the other in the oracle sentence.
3. **Confidence** that the behaviour is a real defect, given the oracle you named: `high`, `medium`, `low`.

Answer from your own reading. Don't guess what a reviewer would say; say what *you* can point to.

## Output

Return your answer as text (do not write files). Use exactly this format, one block per finding, in the order given:

```
### <ID>
Oracle: <one or two sentences>
Type: <in-repo | implicit | known-external | fetch-external | none>
Confidence: <high | medium | low>
```

End with one paragraph: which findings you found hardest to classify and why.

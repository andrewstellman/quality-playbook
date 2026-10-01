**Title:** fix: keep flag-looking args after -- in completion args

## Summary

With `c.Flags().String("output", "", "")` and a `ValidArgsFunction` that records `args`:

- `prog __complete c -- --output ''` passes `[]` to `ValidArgsFunction`; `prog c -- --output` passes `[--output]` to `Run`.
- Same with `c.Flags().SetInterspersed(false)`: `prog __complete c pos1 --output ''` gives `[pos1]`, `Run` gets `[pos1 --output]`.

`getCompletions` (completions.go) calls `checkIfFlagCompletion`, which drops the previous word when it names a value-taking flag, before it detects that flag parsing had already stopped. `flag` stays set, so the word is lost from `args`. The fix keeps a copy of the args and, when flag parsing had stopped, restores them and treats the word as an argument.

The completions docs (site/content/completions/_index.md) say: "Cobra will call your registered function after having parsed all flags and arguments provided in the command-line. ... as it would have done when calling the `RunE` function."

## Test plan

- [x] Extended `TestFlagCompletionWithNotInterspersedArgs`; fails without the fix, passes with it
- [x] `go test ./...`, `go vet ./...`, `gofmt -l .` clean

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

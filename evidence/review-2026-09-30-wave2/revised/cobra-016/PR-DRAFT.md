**Title:** fix: keep flag-looking args after -- in completion args

## Summary

With `c.Flags().String("output", "", "")` and a `ValidArgsFunction` that records `args`:

- `prog __complete c -- --output ''` passes `[]` to `ValidArgsFunction`; `prog c -- --output` passes `[--output]` to `Run`.
- Same with `c.Flags().SetInterspersed(false)`: `prog __complete c pos1 --output ''` gives `[pos1]`, `Run` gets `[pos1 --output]`.

`getCompletions` (completions.go) calls `checkIfFlagCompletion`, which drops the previous word when it names a value-taking flag, before it detects that flag parsing had already stopped. The fix keeps a copy of the args and, when the existing `--` probe shows flag parsing had stopped, restores them before the flags are parsed, so flags are still parsed twice as before. The word being completed is restored too: after `--`, `--output=x` now reaches `ValidArgsFunction` as `toComplete` `--output=x` instead of `x`.

Open PR #2259 changes the same `--` probe lines, so one of the two will need a rebase.

The completions docs (site/content/completions/_index.md) say: "When using the `ValidArgsFunction`, Cobra will call your registered function after having parsed all flags and arguments provided in the command-line."

## Test plan

- [x] Extended `TestFlagCompletionWithNotInterspersedArgs`; fails without the fix, passes with it
- [x] `go test ./...`, `go vet ./...`, `gofmt -l .` clean

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

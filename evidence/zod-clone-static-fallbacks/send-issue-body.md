`.default()` and `.prefault()` copy a static value on each parse so the result can be mutated safely (#5855), but two static fallbacks are still shared. After `const s = z.array(z.string()).catch([]); s.parse(1).push("x")`, every later `s.parse(1)` returns `["x"]`, in both the runtime and the compiled path. And `util.shallowClone` returns a `Date` unchanged, so after `const d = z.date().default(new Date(0)); d.parse(undefined).setTime(1)`, the next `d.parse(undefined).getTime()` is `1`. `.prefault(new Date(0))` does the same.

A fix with tests is on <fork-branch-url>.

Found with the Quality Playbook, an AI code-review tool I maintain. The fix and tests were written with AI assistance and reviewed by me.

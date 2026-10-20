# Pull-request scan by the parent (2026-10-02T22:25Z)

Method: `git clone https://github.com/python-poetry/tomlkit.git`, then `git fetch origin '+refs/pull/*/head:refs/remotes/pr/*'` (364 pull-request heads, every state). For each head: `git diff $(git merge-base master pr/N) pr/N`, searched in added and removed lines.

- Upstream `master` is 0518af253901e57872c03835db6fe9bacab40ee7 (2026-09-30), the commit this run audited.
- Both defects are present on master: `tomlkit/parser.py:1090` `is_aot and name_parts[0] in self._aot_stack,`; `tomlkit/items.py:879` `if self._sign and result >= 0:`.
- Lines mentioning `_aot_stack`: pr/89 (2020, project rename) and pr/284 (2023, `List[Key]` to `list[Key]` type annotation). No pull request changes the comparison at parser.py:1090.
- Lines matching the Float sign condition (`_sign and result`, `raw = f"+{raw}"`, `copysign`, `startswith("-")`): pr/345 only (2024-05-07, "fix: don't add sign if the float is negative Fix #341"), the change that introduced the current line.
- Lines mentioning "negative zero", `-0.0` or `+-0`: pr/456 (deleted toml-test fixture lines `flt3 = -0.01`), pr/628 (a test tuple `("-0E-2", -0.0)` in a parser test). Neither concerns `Float._new`.

Overlaps with OTHER bugs from this run, found by the same scan and the operator's search:
- BUG-009 (slice deletion): open PR #599 "Fix Array.__delitem__ corrupting rendered output on slice deletion" (2026-09-08) makes the identical change (`range(*key.indices(length))`). BUG-009 is a duplicate of an open PR.
- BUG-016 (`+Inf`, `-NaN` accepted): PR #628 "Reject non-lowercase special float literals" (head dated 2026-10-03T04:39+08:00) fixes the same defect.
- BUG-006 (split array of tables reordered): open PR #601 "Render each run of a split array of tables where it was written".

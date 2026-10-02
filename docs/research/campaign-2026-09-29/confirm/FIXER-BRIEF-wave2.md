# Fixer brief (wave 2: cobra, pydantic, setuptools, addressable, javalin)

You produce a minimal, mergeable fix for ONE confirmed bug. YAGNI: change only what the bug requires. Andrew likes minimal commits; a reviewer will reject anything padded.

## Inputs
- The bug: `/sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/<repo>/quality/BUGS.md` (your entry) and `quality/patches/<BUG>-*.patch` if present (a starting point only; QPB's patches are often wider than needed).
- Confirmer's evidence: `/tmp/<repo>v/<BUG>/` (repro + output; cobra's are in /tmp/cobrav/<BUG>/) and the wave-2 table in `/sessions/kind-zealous-edison/mnt/QPB/docs/research/campaign-2026-09-29/confirm/LEDGER.md` (cobra: its own section).
- Citable docs: `.../campaign-2026-09-29/<repo>/reference_docs/cite/`. Quote verbatim, grep to prove it.
- Read the project's CONTRIBUTING / AGENTS / PR template and 2-3 recent merged outside bug-fix PRs (web_fetch github.com/<owner>/<repo>/pulls?q=is:merged) to copy their style for tests, commit subject and PR body.

## Worktree
`git clone -q /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/<repo> /tmp/w2fix/<id>` (a clean checkout of the pin; untracked QPB files are not cloned). Then `git -C /tmp/w2fix/<id> config user.name "Andrew Stellman"; git -C ... config user.email andrew@stellman.com`. Work ONLY there. Never modify anything under /sessions/.../mnt/QPB. Disk is tight (~1.8 GB free): delete build outputs you no longer need; never fill the disk.

## Toolchains
- cobra: `export PATH=/tmp/go/bin:$PATH GOPATH=/tmp/gopath GOCACHE=/tmp/gocache HOME=/tmp/home`; `go test ./...`; `gofmt -l .`; `go vet ./...`.
- setuptools: `/tmp/stv/.venv` exists (editable install of /tmp/setuptoolsw — install your worktree instead: `/tmp/stv/.venv/bin/pip install -e /tmp/w2fix/<id>`, or create /tmp/w2fix/<id>-venv). Run the touched test module with pytest; add a newsfragment per `newsfragments/README.rst` (`<issue-or-short-name>.bugfix.rst`; there is no issue number yet, use `+<short-name>.bugfix.rst` like the existing `+ghsa-...` files). Run ruff if configured.
- addressable: Ruby 3.0; gems at `/tmp/addressablev/gems` (GEM_PATH). For rspec: `gem install --install-dir /tmp/addressablev/gems rspec` if missing, then `GEM_PATH=/tmp/addressablev/gems ruby -I lib -S rspec spec/addressable/<file>_spec.rb` (or /tmp/addressablev/gems/bin/rspec).
- javalin: `JAVA_HOME=/tmp/jdk17 PATH=/tmp/jdk17/bin:$PATH HOME=/tmp/home MAVEN_OPTS="-Dmaven.repo.local=/tmp/m2" ./mvnw -B -o -pl javalin test -Dtest=<TestClass>` (drop -o if a dependency is missing). Add to the existing test class for the feature (Kotlin). Delete `javalin/target` when done.
- pydantic: the fix is in `pydantic-core/` (Rust). FIRST check feasibility: `df -h /`. Try `curl -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --no-modify-path` with `RUSTUP_HOME=/tmp/rust/rustup CARGO_HOME=/tmp/rust/cargo`, then build the worktree with maturin into a venv (`/tmp/w2fix/pyd-venv`; `pip install maturin`; `cd pydantic-core && CARGO_TARGET_DIR=/tmp/w2fix/pyd-target maturin develop`). If free space falls below 500 MB at any point, stop the build, delete /tmp/rust and the target dir, and instead deliver: the patch, the tests, and `/tmp/w2fix/<id>/out/RUN-ON-MAC.sh` (zsh script that builds and runs the red/green on Andrew's Mac). Say plainly that red/green was NOT run here. Only one pydantic fixer builds; the other waits for the toolchain (see your prompt).

## Steps
1. Test FIRST, in the existing test file that covers the feature (no new file unless the project has none). Named and written like its neighbours. Run it: the new test FAILS for the claimed reason (read the assertion message), the rest pass. Save output to `out/red.log`.
2. Smallest code change that fixes it.
3. The touched test file passes; the project's full test suite (or, if that is impractical, the whole module/package suite — say which) has no new failures. Save to `out/green.log`. Run the project's formatter/linter on touched files.
4. Revert only the source change, confirm the new test fails again (`out/revert.log`), restore.
5. Commit: subject in the repo's style (≤ 72 chars), body 2-4 lines. No trailers, no Signed-off-by, no Co-Authored-By.
6. `git format-patch -1 -o /tmp/w2fix/<id>/out` and write `/tmp/w2fix/<id>/out/PR-DRAFT.md`: first line `**Title:** <subject>`, then a short body in the project's usual PR style: a minimal repro (actual vs expected), one or two sentences of cause with file reference, one sentence on the fix, the doc/RFC/PEP sentence it relies on (verbatim, with where it lives). At most ~15 lines. Last line exactly: `Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.`

Return as text, under 40 lines: id; files changed (+/-); test name; red/green/revert summary lines (verbatim key lines); suite result; lint/format results; commit subject; anything you were unsure about or chose not to fix.

# Confirmer brief (wave 2: pydantic, setuptools, addressable, javalin)

You are confirming candidate bugs from a Quality Playbook run. Find out whether each one is real; do not just agree with the report.

Inputs:
- Run output (read-only): /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/<repo>/quality/BUGS.md (your entries), plus quality/patches/ if present.
- Citable docs (read-only): /sessions/kind-zealous-edison/mnt/QPB/repos/campaign-2026-09-29/<repo>/reference_docs/cite/. Quote the exact sentence you rely on, with file:line, and grep to prove it is there.
- Source at the pin: copy the repo (without quality/, reference_docs/, .claude/) to /tmp/<repo>w if it is not already there. Never edit anything under /sessions/.../mnt/QPB.
- Work only in /tmp/<repo>v/<bug-id>/. Disk is tight (~2 GB free): no caches outside /tmp, clean up build dirs you do not need.

Per-repo environment notes:
- pydantic: the bugs are in pydantic-core (Rust). Do NOT build Rust. Use a venv in /tmp/pydv/.venv with `pip install pydantic==<version closest to the pin>` (check `pydantic/version.py` and the pydantic-core pin in pyproject.toml at the pin). Say which version you used and whether the relevant Rust source in the wheel's release matches the pin (compare with the pydantic-core source at the pin if it is vendored; otherwise with the GitHub tag via web_fetch).
- setuptools: venv in /tmp/stv/.venv, `pip install -e /tmp/setuptoolsw`. Repro by building a tiny project in your work dir (`python -m build --sdist --no-isolation` or `python setup.py sdist`, whichever the bug needs).
- addressable: Ruby 3.0 is installed. `cd /tmp/addressablew && bundle config set path /tmp/addressablev/bundle && bundle install` if you need rspec; a plain `ruby -I lib repro.rb` is enough for a repro.
- javalin: `JAVA_HOME=/tmp/jdk17 PATH=/tmp/jdk17/bin:$PATH HOME=/tmp/home MAVEN_OPTS="-Dmaven.repo.local=/tmp/m2" ./mvnw -B -o -pl javalin test -Dtest=<YourTest>` in a COPY of /tmp/javalinw placed in your work dir (never edit /tmp/javalinw). Drop `-o` if a dependency is missing.

Steps, per bug:
1. Restate the claim in one sentence: input, actual, expected, and the source of "expected".
2. Write a repro that prints the actual behaviour and exits 1 if the bug is present, 0 if not. Run it. Paste the output verbatim.
3. Check the "expected" side: does the cited doc really say that? Is there a test in the project that pins the current behaviour (meaning it is intended)? A comment, changelog entry or closed issue explaining it?
4. Duplicate search via web_fetch on the GitHub issue/PR search (e.g. https://github.com/<owner>/<repo>/issues?q=...) or the REST search API. Closest match (number, title, state) or "none found" with the queries.
5. Security angle? yes/no, one line.
6. Verdict: CONFIRMED / CONFIRMED-DUPLICATE (cite) / NOT-A-BUG (why) / UNCLEAR (what a maintainer would need to decide) / COULD-NOT-RUN (what blocked you).

Never push, post, comment or open anything on GitHub.

Return as text, per bug in this order: id and title; claim; verdict; repro source; verbatim output; expectation check; duplicate search; security line; likely maintainer pushback. Under 60 lines per bug.

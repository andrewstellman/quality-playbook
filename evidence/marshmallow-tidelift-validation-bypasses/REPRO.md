# marshmallow reproduce-only security triage

Run started: `Tue Oct 20 15:37:25 UTC 2026` (from `date -u`). Nothing was pushed, posted, filed or sent. All work is under `/tmp/claude-0/sec/marshmallow/`.

Source record: `/tmp/claude-0/sec/records/marshmallow/target/quality/BUGS.md` (BUG-001, 002, 003, 004, 006). That run was done on 2026-10-05 against commit `1c63bdaf`, marshmallow 4.3.1.

## 1. Environment

Clone (depth 50, `GIT_LFS_SKIP_SMUDGE=1`) into `/tmp/claude-0/sec/marshmallow/src`. The default branch of this repository is `dev`, not `main`; "current main" in the task means `origin/dev`.

```
Tue Oct 20 15:37:47 UTC 2026
Cloning into 'src'...
b762ea2d59ca52fe5df76b90de14bed7e5ec5607 2026-10-19T18:57:37+02:00 Update CHANGELOG
4.3.1-18-gb762ea2
pyproject.toml:3:version = "4.3.1"
```

Head: `b762ea2d59ca52fe5df76b90de14bed7e5ec5607`, committed 2026-10-19T18:57:37+02:00, "Update CHANGELOG". `pyproject.toml` version is still `4.3.1` (18 commits past the 4.3.1 tag). The project uses PEP 735 `[dependency-groups]`, not optional extras; the `tests` group is `["pytest", "simplejson"]`, so `pip install -e .[tests]` is not the right spelling. I installed in a venv:

```
python3 -m venv venv
./venv/bin/pip install -q -e ./src pytest simplejson
Python 3.13.15
pytest 9.1.1
4.3.1 /tmp/claude-0/sec/marshmallow/src/src/marshmallow/__init__.py
```

(`marshmallow.__version__` does not exist; version read via `importlib.metadata`.)

Baseline suite on unmodified head (`Tue Oct 20 15:38:46 UTC 2026`):

```
1192 passed in 4.77s
```

(The 2026-10-05 record reported 1190 passed; the difference is two tests added by the Pluck commit below.)

### Changes since the 2026-10-05 run

`git diff --stat 1c63bda..HEAD`:

```
 .pre-commit-config.yaml   |  8 ++++----
 CHANGELOG.rst             |  1 +
 src/marshmallow/fields.py |  4 +++-
 tests/test_fields.py      | 16 ++++++++++++++++
 4 files changed, 24 insertions(+), 5 deletions(-)
```

The only source change is `5761beab 2026-10-19 "Fix Pluck handling of empty data_key"` (Jérôme Lafréchoux), which touches `Pluck._field_data_key` in `fields.py` (lines 710-715). `git log --since=2026-10-05 -- src/marshmallow/schema.py src/marshmallow/fields.py` lists only that commit. `schema.py` is untouched since the record was made. None of the five bugs is fixed on current head; the hunks all touch code that has not changed.

## 2. Reproduction on unmodified head

Scripts: `/tmp/claude-0/sec/marshmallow/repro/bug001.py` ... `bug006.py`, each run with `./venv/bin/python -I`. Verbatim output (`Tue Oct 20 15:38:38 UTC 2026`), also saved to `repro/baseline-output.txt`:

```
=== bug001.py
many=False result={'a': {'b': 'x'}}
many=True result=[{'a': {'b': 'x'}}]
exit=0
=== bug002.py
messages={'name': ['rejected']} valid_data={'n': 'x', 'age': 1}
{'a': {'b': 'x'}, 'age': 1}
exit=0
=== bug003.py
dump with load_only: {'by_class': {'a': 1}, 'by_instance': {'a': 1, 'b': 2}}
load with dump_only: ValidationError {'by_class': {'b': ['Unknown field.']}}
exit=0
=== bug004.py
ValueError: zip() argument 2 is shorter than argument 1
exit=0
=== bug006.py
data_key collision: {'first_name': 'evil'}
attribute collision: {'y': 'evil'}
exit=0
```

Reading:

- BUG-001: `@validates('name')` on `attribute='a.b'` never runs; load returns the data instead of raising, in both single and `many=True` form. Reproduces.
- BUG-002: with `attribute='n'`, `valid_data` still contains the rejected value under `n`. Reproduces. The second line (dotted attribute) shows no error at all, which is BUG-001 masking BUG-002 for the dotted case.
- BUG-003: `load_only=('by_instance.b',)` is ignored on dump for the instance form (`b: 2` leaks), and `dump_only=('by_instance.b',)` is ignored on load (only `by_class` rejects `b`). Reproduces.
- BUG-004: `pass_collection` `pre_load` that unwraps an envelope plus a plain `validates_schema` raises `ValueError` out of `Schema.load` under `many=True`. Reproduces.
- BUG-006: under `unknown=INCLUDE`, an input key equal to a declared field's output key (`first_name`, or `y` for `attribute='y'`) overwrites the validated value with the raw string `'evil'`. Reproduces.

All five reproduce on current head.

## 3. Red / green / full suite

Each bug on its own branch from `dev` (`b762ea2`), using the regression-test and fix patches from `/tmp/claude-0/sec/records/marshmallow/target/quality/patches/`. BUG-006 does have both a regression-test patch and a fix patch in that folder (the task note said there might be none). Every patch applied cleanly with `git apply --check` against current head. Full log in `repro/redgreen-output.txt`; the relevant lines:

```
##### BUG-001 2026-10-20T15:39:44Z
base=b762ea2 branch=bug-001
--- RED
FAILED tests/test_bug_001_regression.py::test_bug_001_validates_runs_for_dotted_attribute
FAILED tests/test_bug_001_regression.py::test_bug_001_validates_runs_for_dotted_attribute_many
2 failed in 0.09s
--- GREEN
2 passed in 0.03s
--- repro script after fix
many=False ValidationError {'name': ['rejected']}
many=True ValidationError {0: {'name': ['rejected']}}
--- FULL SUITE
1194 passed in 4.21s
##### BUG-002 2026-10-20T15:39:52Z
--- RED
FAILED tests/test_bug_002_regression.py::test_bug_002_valid_data_excludes_rejected_renamed_attribute
1 failed in 0.05s
--- GREEN
1 passed in 0.02s
--- repro script after fix
messages={'name': ['rejected']} valid_data={'age': 1}
{'a': {'b': 'x'}, 'age': 1}
--- FULL SUITE
1193 passed in 4.95s
##### BUG-003 2026-10-20T15:40:01Z
--- RED
FAILED tests/test_bug_003_regression.py::test_bug_003_instance_nested_honours_dotted_dump_only_and_load_only
1 failed in 0.08s
--- GREEN
1 passed in 0.03s
--- repro script after fix
dump with load_only: {'by_class': {'a': 1}, 'by_instance': {'a': 1}}
load with dump_only: ValidationError {'by_class': {'b': ['Unknown field.']}, 'by_instance': {'b': ['Unknown field.']}}
--- FULL SUITE
1193 passed in 3.98s
##### BUG-004 2026-10-20T15:40:09Z
--- RED
src/marshmallow/schema.py:1195: ValueError
FAILED tests/test_bug_004_regression.py::test_bug_004_per_item_schema_validator_with_envelope_pre_load
1 failed in 0.13s
--- GREEN
1 passed in 0.02s
--- repro script after fix
[{'n': 1}, {'n': 2}]
--- FULL SUITE
1193 passed in 4.14s
##### BUG-006 2026-10-20T15:40:18Z
--- RED
FAILED tests/test_bug_006_regression.py::test_bug_006_include_unknown_does_not_overwrite_declared_field
1 failed in 0.08s
--- GREEN
1 passed in 0.02s
--- repro script after fix
data_key collision: {'first_name': 5}
attribute collision: {'y': 1}
--- FULL SUITE
1193 passed in 2.85s
```

Summary (baseline 1192 passed):

| Bug | Red | Green | Full suite with fix + regression test |
|---|---|---|---|
| BUG-001 | 2 failed | 2 passed | 1194 passed, 0 failed |
| BUG-002 | 1 failed | 1 passed | 1193 passed, 0 failed |
| BUG-003 | 1 failed | 1 passed | 1193 passed, 0 failed |
| BUG-004 | 1 failed | 1 passed | 1193 passed, 0 failed |
| BUG-006 | 1 failed | 1 passed | 1193 passed, 0 failed |

Caveats:

- BUG-002's dotted-attribute case still shows no ValidationError after the BUG-002 fix alone (`{'a': {'b': 'x'}, 'age': 1}`), because BUG-001 is what stops the validator running for dotted attributes. The BUG-002 patch's `_pop_loaded_value` dotted path only matters once BUG-001 is also fixed. I did not test the two fixes together as a combined patch.
- The BUG-001 and BUG-002 fix patches do not stack: after `git am` of the 0001 patch, `git apply --check` of the 0002 patch fails with `error: patch failed: src/marshmallow/schema.py:1155`. They edit the same lines of `_invoke_field_validators`. They are fine as independent patches against head; a combined fix would need a manual merge (not done here, per the instruction not to invent new fixes).
- My first pass accidentally ran `git checkout main` (which does not exist) and so stacked the patches on one tree; that pass was discarded and redone on isolated branches. The stacked pass is what first surfaced the 001/002 conflict.
- I did not run ruff, mypy or pre-commit on the patched trees. I did not check the documentation build.

## 4. Security impact assessment

Context for all five: marshmallow is a (de)serialization and validation library. In the realistic deployment (a web API calling `Schema().load(request_json)`), the attacker controls the JSON body entirely. The schema definition (field names, `attribute`, `data_key`, `unknown` setting, hooks, nesting form) is chosen by the application developer and is not attacker-controlled. So every one of these needs a specific developer-side configuration to be reachable.

SECURITY.md in the repository says: "To report a security vulnerability, please use the Tidelift security contact (https://tidelift.com/security). Tidelift will coordinate the fix and disclosure." Anything judged a vulnerability goes there, not to a public issue. I did not contact anyone.

### BUG-001: `@validates` silently skipped for dotted `attribute`

- Attacker controls: the value of the field (any JSON value the field type accepts).
- What gets through: the field's `@validates` method never runs, so any custom validation on that field (length limits, allow-lists, business rules) is bypassed entirely. Field-level type coercion and `validate=` arguments on the field itself still run; only the decorator-based validator is lost.
- Realistic deployment: affected only if the developer uses `attribute='a.b'` (dotted path) together with `@validates` on that field. Dotted attributes on load are uncommon but documented. There is no error, warning or test that would show the developer their validator is dead; that silent failure is the concerning part.
- Verdict: I would call this a validation bypass with a narrow precondition. It is reportable as a security-relevant bug (silent loss of a validation control the developer explicitly wrote). I would not call it a high-severity vulnerability in marshmallow itself; it is closer to a correctness bug that has security consequences in applications relying on that validator. Routing through Tidelift is defensible but a maintainer would likely treat it as an ordinary bug fix. Agrees with the record's MEDIUM.

### BUG-002: rejected value retained in `ValidationError.valid_data` for renamed/dotted attribute

- Attacker controls: the rejected value.
- What gets through: nothing reaches a successful load; `load` still raises. The rejected value is only present in `valid_data`, a diagnostic attribute on the exception. It matters only if an application reads `e.valid_data` on the error path and acts on it (partial saves, "best effort" processing), which is an unusual pattern.
- Realistic deployment: a web API would normally return 4xx on ValidationError and discard the payload. Impact needs both a renamed attribute and code that consumes `valid_data` as trustworthy.
- Verdict: ordinary validation bug. Not a vulnerability. Agrees with the record's LOW.

### BUG-003: `Nested(SchemaInstance())` ignores parent's dotted `load_only` / `dump_only`

- Attacker controls: on load, the input JSON (can supply a field the developer declared dump-only via the parent's dotted `dump_only`). On dump, the attacker controls nothing; the issue is that a field the developer marked load-only via the parent's dotted `load_only` is still serialized out.
- What gets through: load side, a mass-assignment style bypass (attacker sets a field meant to be read-only, e.g. `child.id`, `child.role`). Dump side, information exposure (a field meant to be write-only, e.g. `child.password_hash` or `child.secret`, is emitted in responses).
- Realistic deployment: requires the developer to (a) nest with a Schema instance or a lambda returning one rather than a class, and (b) express the restriction via the parent's dotted `load_only`/`dump_only` rather than on the child field or child schema directly. The class form works correctly, so a developer who wrote a test for it with the class form and then switched to the instance form gets a silent regression. Both halves (hidden field accepted on load; hidden field emitted on dump) are real consequences in a web API.
- Verdict: the most security-relevant of the five in terms of outcome (information exposure and write-only field acceptance), but with a double precondition on the developer's schema setup and weak documentary basis (the challenge gate noted the docs cover dotted paths explicitly only for `only`/`exclude`). I would describe it as a security-relevant inconsistency bug rather than a vulnerability. If reporting, I would send it through Tidelift with the information-exposure angle stated plainly and let the maintainers downgrade.

### BUG-004: `ValueError` from `zip(strict=True)` when a `pass_collection` `pre_load` reshapes `many` input

- Attacker controls: the number of items in the enveloped list.
- What gets through: nothing is accepted; `Schema.load` raises `ValueError` instead of returning or raising `ValidationError`. In a web framework that is an unhandled exception, so a 500 instead of a 400. Any request whose envelope list length is not 1 triggers it, so the endpoint effectively does not work at all for N != 1; this is not a selectively exploitable condition so much as a broken feature.
- Realistic deployment: requires the documented envelope pattern (`pre_load(pass_collection=True)` unwrapping `data['items']`) combined with a per-item `validates_schema` on a `many=True` load. The developer would notice in basic testing because every multi-item request fails. A denial-of-service framing is weak since the crash is per-request and does not consume resources.
- Verdict: ordinary bug (crash on normal input, documented usage pattern). Not a vulnerability. The MEDIUM in the record is about correctness; I would not route this through Tidelift.

### BUG-006: `unknown=INCLUDE` lets an unknown key overwrite a declared field's validated value

- Attacker controls: the whole JSON body, so can send both `firstName` (the declared `data_key`) and `first_name` (the output key).
- What gets through: the declared field's deserialized and validated value is replaced by the raw, unvalidated value from the unknown key. Type coercion, `validate=`, and `@validates` for that field are all bypassed in the final output; the application sees `first_name='evil'` where the schema promised an int. Same with `attribute='y'` and an input key `y`.
- Realistic deployment: requires `unknown=INCLUDE` (which the docs describe as passing unknown keys through "with no validation performed") plus a field with `data_key` or `attribute` that differs from its name. Both are common individually. Developers who choose INCLUDE have already accepted unvalidated keys in their output, but the documented promise is that *unknown* keys pass through, not that known fields can be clobbered. The 2026-10-05 challenge gate judged this a design question not worth reporting; I disagree somewhat on the outcome side: of the five, this one is the cleanest "attacker sends an extra key, validated value replaced by raw value" story and needs the least unusual schema setup. On the other side, INCLUDE is an explicit opt-out of strictness, and a maintainer could reasonably say the fix (drop the colliding key) or raising is a design choice.
- Verdict: borderline. I would call it a validation bypass worth reporting, but I would present it to the maintainers as a hardening request with the collision case spelled out, rather than claim a CVE-grade vulnerability. If going through Tidelift, it is the one I would send alongside BUG-001 and BUG-003, with an honest note that INCLUDE is opt-in.

### Overall

- None of the five is exploitable against a default marshmallow configuration; each needs a specific developer choice (dotted `attribute`, renamed attribute, instance-form Nested with dotted options, envelope hook, INCLUDE with `data_key`/`attribute`).
- Closest to "vulnerability": BUG-003 (information exposure and read-only field acceptance) and BUG-006 (validated value replaced by raw input), followed by BUG-001 (silent loss of a validator). All three are better described as security-relevant validation bugs than as vulnerabilities in the CVE sense.
- Ordinary bugs: BUG-002 (diagnostic data on an error path) and BUG-004 (crash on a documented pattern, no bypass).
- Reporting route if any are reported as security issues: the Tidelift security contact per SECURITY.md. I did not report anything.

## 5. Outputs

- This file: `/tmp/claude-0/sec/marshmallow/REPRO.md`
- Clone: `/tmp/claude-0/sec/marshmallow/src` (branch `dev` at `b762ea2`; local branches `bug-001`, `bug-002`, `bug-003`, `bug-004`, `bug-006` each hold one commit with fix + regression test)
- Venv: `/tmp/claude-0/sec/marshmallow/venv`
- Repro scripts and raw outputs: `/tmp/claude-0/sec/marshmallow/repro/` (`bug00N.py`, `baseline-output.txt`, `baseline-suite.txt`, `redgreen-output.txt`)
- Format-patch files (author Andrew Stellman <andrew@stellman.com>, no trailers, each verified with `git apply --check` against clean `dev`):
  - `/tmp/claude-0/sec/marshmallow/out/0001-Run-validates-for-fields-with-a-dotted-attribute.patch`
  - `/tmp/claude-0/sec/marshmallow/out/0002-Drop-values-rejected-by-validates-from-valid_data-wh.patch`
  - `/tmp/claude-0/sec/marshmallow/out/0003-Apply-dotted-load_only-dump_only-to-Nested-built-fro.patch`
  - `/tmp/claude-0/sec/marshmallow/out/0004-Do-not-require-original_data-to-match-length-in-per-.patch`
  - `/tmp/claude-0/sec/marshmallow/out/0006-Do-not-let-an-unknown-key-under-INCLUDE-overwrite-a-.patch`

Each format-patch bundles the fix and its regression test (`tests/test_bug_00N_regression.py`) in one commit. 0001 and 0002 conflict with each other when stacked (see caveats above).

Not checked: upstream issue tracker for new duplicates since 2026-10-05 (no network searches beyond the clone); ruff/mypy/pre-commit on patched trees; behaviour on Python versions other than 3.13.15; the BUG-001 + BUG-002 fixes combined.

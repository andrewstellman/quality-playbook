"""QPB Test Harness — Phase 1 substrate (v1.5.7 091).

This subpackage holds the harness modules (schema/prepare/runner/
facts; graders/scheduler/manager/tui are Phases 2–4). It is
PROTECTED QPB SOURCE — built by the worker, dual-chat reviewed —
and MUST be excluded from the install bundle.

Bundle-safety contract (per
``docs/design/QPB_Test_Harness_1.5.7_Implementation_Plan.md`` §1):

1. No path under ``bin/harness/`` appears in
   ``bin.install_skill._bundle_files()`` (that function is an
   enumerated allowlist around ~lines 213–225; new subpackages are
   excluded by default, but the test pins this).
2. NO bundled module — and ``bin/__init__.py`` in particular —
   transitively imports ``bin.harness``. ``bin/__init__.py`` is
   bundled and runs on every ``import bin.*``, so a transitive
   import via ``__init__.py`` would leak the harness into every
   adopter install.

Both invariants are pinned by tests in
``bin/tests/test_publish_safety_090c.py`` that **run IN the
release gate** (NOT segregated) — their job is to catch a harness
change leaking into the shipped adopter closure.

Harness FUNCTIONALITY tests live in ``bin/tests/harness/`` and
are segregated from the skill-release gate per
``QPB_Test_Harness_1.5.7_Implementation_Plan.md`` §4.

See also:
- ``docs/design/QPB_Test_Harness_1.5.7_Design.md`` (architecture,
  the §F closed assertion vocabulary, two-sourced facts §C).
- ``docs/design/QPB_Test_Harness_1.5.7_Design.md`` (LOCKED contract — v1.5.7 098 moved
  it under the code it specifies; tracked but bundle-excluded).
"""

__all__ = [
    "schema",
    "prepare",
    "runner",
    "facts",
]

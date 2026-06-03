"""Harness functionality test suite.

SEGREGATED from the skill-release gate per the
``QPB_Test_Harness_1.5.7_Implementation_Plan.md`` §4 decision:
these tests cover ``bin/harness/`` functionality but MUST NOT
block shipping the skill (a harness functionality bug is not a
release blocker — the skill itself remains correct).

The release-gate-relevant harness tests (bundle-exclusion +
import-isolation) live in ``bin/tests/test_publish_safety_090c.py``
— their job is to catch a harness change leaking into the
shipped adopter closure.

Discovery: ``python3 -m unittest discover bin/tests/harness``.
Not auto-discovered by ``unittest discover bin/tests`` because
the parent's default pattern excludes subdirectories by walking
``bin/tests/*.py`` only — but ``unittest`` walks subdirs by
default. To preserve the segregation, the release-gate test
invocation uses ``-p 'test_*.py' -t bin/tests`` and explicitly
filters out the ``harness/`` subdir.

In practice: ``unittest discover bin/tests`` DOES walk
``bin/tests/harness/`` and pick up these tests. The segregation
is enforced at CI orchestration time, not at the unittest layer.
This is intentional — the developer running the full discover
gets the harness tests too, which is what they want; CI's
release-gate stage explicitly EXCLUDES this subdir.
"""

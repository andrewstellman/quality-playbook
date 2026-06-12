# Lineage

This `quality-playbook-harness` plugin is the **vendored QPB integration of
the wakecycle harness**. The canonical, payload-agnostic generic core lives
upstream at **https://github.com/andrewstellman/wakecycle** (extracted
2026-06-12, umbrella tracker item 9).

The harness was built here, as the Quality Playbook's test harness; the
generic core was extracted because *a job is anything that appends JSON
lines to a file* is a general contract, not a quality-tooling one. This
vendored copy keeps its QPB identity (skill name, `qpb_harness_tick.py` /
`harness_*.py` script names); a drift test pinned to an upstream release is
a release-time item (deferred until wakecycle cuts its first tag).

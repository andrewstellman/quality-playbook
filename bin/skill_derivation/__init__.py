"""bin/skill_derivation/ — QPB v1.5.4 four-pass skill-derivation pipeline.

The four-pass generate-then-verify architecture (Pass A naive coverage,
Pass B mechanical citation extraction, Pass C formal REQ production, Pass D
coverage audit) produces skill-shaped requirements from the files the
Phase-1 role map tagged ``skill-prose`` and ``skill-reference``.

v1.5.4 Part 1 redesigned activation: the pipeline activates iff
``bin.role_map.has_skill_prose(role_map)`` returns True. There is no
Code/Skill/Hybrid trichotomy gate — the always-Hybrid downstream model
runs the four-pass pipeline against whatever skill surface the role
map reports. Targets with zero skill-prose files (pure-code benchmarks)
no-op cleanly. Targets with both skill-prose AND code surface run both
the four-pass pipeline AND the code-review pipeline. See
``docs/design/QPB_v1.5.4_Design.md`` Part 1 for the redesign rationale
and ``docs/design/QPB_v1.5.4_Implementation_Plan.md`` for the phase
sequencing.

The original v1.5.3 four-pass spec (per-pass disk-as-ledger contract,
per-pass progress files, B4 upstream-status gate at every transition)
is unchanged. v1.5.4 changed only what files feed the pipeline (the
Phase-1 role map) and the activation predicate (``has_skill_prose``);
the four passes themselves did not move.

Module naming note: this directory is ``bin/skill_derivation/`` rather
than ``bin/phase3/`` to avoid collision with the Quality Playbook's
own internal Phase 3 (Code Review and Regression Tests, per SKILL.md).
The on-disk artifact directory is ``quality/phase3/`` (top-level
canonical layout per README spec; v1.5.7 fix F-4z dropped the
intermediate quality/workspace/ reshape).
"""

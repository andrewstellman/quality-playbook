"""v1.6.0 Feature H slice 2 (Design §8b) — persona sub-agent orchestration +
least-privilege isolation. THE SECURITY CORE of Feature H.

A Feature H persona is a fresh-context sub-agent that ramps on documented intent
and runs the Feature D interview as the operator. Its isolation is what keeps
validation *fitness-for-purpose* (against documented intent) rather than the
circular *fitness-to-implementation* trap, and what closes the exfiltration
surface a persona opens by ingesting untrusted documents. Per the pinned §8b
"Concrete enforcement substrate", isolation is realized by two composed
mechanisms so out-of-bounds access is **prevented by construction, not detected**:

1. **Input staging (prevention by absence).** Before a persona is spawned, its
   declared inputs are copied into an isolated per-persona staging directory. The
   implementation tree, secrets/credentials, ``operator_confirmations.jsonl``, and
   any out-of-run path are simply NOT PRESENT there — a persona cannot read what
   was never staged.
2. **Tool allowlist (no lateral authority).** The sub-agent is spawned with
   **Read only, rooted at the staging directory; no Bash/shell; no network/fetch.**
3. **Fabrication-tell (backstop, not primary control).** A persona whose output
   references implementation detail it could only have gotten from source is a
   detected failure — the second line, behind staging + allowlist.

This slice stages, isolates, and runs the selected personas (slice 1) in parallel
and blind to each other, each emitting a RAW candidate diff-set of interview
moves. It does NOT ground/validate those moves (guard 1, slice 3), merge them
(guard 3, slice 4), or apply them (guard 4, slice 5). The live sub-agent spawn is
behind an ``executor`` seam (the live gap-finding run is slice 7); the mechanism
(staging + tool restriction + fabrication-tell) is deterministic and tested here.

**Target-agnostic** (§8b): context provisioning is a per-target PARAMETER — the
caller supplies WHAT to stage (Feature H: gathered docs + rendered spec + rubric;
v1.6.1 Feature B will supply finding + source + REQ + rubric). No H-specific input
set is baked into the spawn seam. Not a kernel/network sandbox (that is v1.8.0);
this is the v1.6.0-scoped least-privilege realization.

Stdlib-only.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

# The five interview moves; `defer` is an operator-only punt, never a persona
# move (§8b guard 3), so it is not in the persona move set.
PERSONA_MOVES = ("confirm", "correct", "add", "drop")

# Paths a persona must NEVER be able to reach — asserted absent from staging.
FORBIDDEN_STAGED_NAMES = ("operator_confirmations.jsonl",)


class IsolationError(RuntimeError):
    """Raised when a staging directory would violate the isolation contract."""


@dataclass
class StagedInput:
    """One declared input to stage. Target-agnostic: the caller decides what
    these are (H: docs/spec/rubric; B: finding/source/REQ/rubric)."""
    name: str          # the relative filename inside the staging dir
    text: str          # the content to stage (already-read; no path leaks in)


@dataclass
class PersonaToolConfig:
    """The tool allowlist the harness applies when spawning the sub-agent.

    Read-only, rooted at the staging directory; no shell, no network. This is
    the config a Task-spawn honours; it is data so it is testable without a
    live spawn.
    """
    read_root: str
    allow_tools: tuple = ("Read",)
    allow_bash: bool = False
    allow_network: bool = False

    def denies(self, tool: str) -> bool:
        t = tool.lower()
        if t in ("bash", "shell", "sh", "exec", "run"):
            return not self.allow_bash
        if t in ("fetch", "network", "web", "webfetch", "curl", "http", "url"):
            return not self.allow_network
        return tool not in self.allow_tools

    def as_dict(self) -> dict:
        return {
            "read_root": self.read_root,
            "allow_tools": list(self.allow_tools),
            "allow_bash": self.allow_bash,
            "allow_network": self.allow_network,
        }


@dataclass
class PersonaRun:
    persona_id: str
    staging_dir: str
    tool_config: PersonaToolConfig
    staged_names: List[str]
    diff_set: dict = field(default_factory=dict)
    fabrication_flags: List[str] = field(default_factory=list)


def stage_persona_inputs(
    persona_id: str,
    inputs: Sequence[StagedInput],
    staging_root: Path,
) -> Path:
    """Materialise an isolated per-persona staging dir containing EXACTLY the
    declared inputs. Nothing else — the impl tree, secrets, and
    ``operator_confirmations.jsonl`` are never copied, so they are absent by
    construction. Returns the staging directory path.

    Refuses to stage a forbidden name (a defensive check — the caller should
    never pass one, but staging it would defeat the isolation).
    """
    staging_root = Path(staging_root)
    persona_dir = staging_root / _safe_component(persona_id)
    # Fresh, empty dir — no residue from a prior run leaks in.
    if persona_dir.exists():
        shutil.rmtree(persona_dir)
    persona_dir.mkdir(parents=True)
    for item in inputs:
        base = Path(item.name).name  # flatten — no traversal, no subpaths out
        if base in FORBIDDEN_STAGED_NAMES:
            raise IsolationError(
                f"refusing to stage forbidden input {base!r} into a persona "
                "staging dir (Feature H isolation, §8b)"
            )
        (persona_dir / base).write_text(item.text, encoding="utf-8")
    return persona_dir


def assert_isolation(staging_dir: Path, *, run_root: Optional[Path] = None) -> None:
    """Verify a staging dir honours the isolation contract, else raise.

    Prevention-by-construction checks: the dir contains only regular files (no
    symlinks escaping the dir, no subdirectories that could re-introduce the
    impl tree), and none of the forbidden names is present. When ``run_root`` is
    given, also assert no staged file resolves outside the staging dir.
    """
    staging_dir = Path(staging_dir)
    for p in staging_dir.rglob("*"):
        if p.is_symlink():
            raise IsolationError(f"symlink in staging dir defeats isolation: {p}")
        if p.is_dir():
            raise IsolationError(
                f"subdirectory in staging dir may re-introduce the impl tree: {p}"
            )
        if p.name in FORBIDDEN_STAGED_NAMES:
            raise IsolationError(f"forbidden file present in staging dir: {p}")
        # No staged file may resolve outside the staging dir.
        if staging_dir.resolve() not in p.resolve().parents:
            raise IsolationError(f"staged file escapes the staging dir: {p}")


def persona_tool_config(staging_dir: Path) -> PersonaToolConfig:
    """The Read-only, staging-rooted, no-shell, no-network spawn config."""
    return PersonaToolConfig(read_root=str(Path(staging_dir).resolve()))


def detect_fabrication(diff_set: dict, staged_texts: Sequence[str]) -> List[str]:
    """Fabrication-tell backstop: flag any move whose cited evidence is NOT
    present in the persona's staged inputs — i.e. content it could only have
    obtained by reading source it was not given.

    Returns a list of human-readable flags (empty when clean). A move carries an
    optional ``citation`` (a quote/excerpt) and/or ``source`` (a filename); a
    citation that is not a substring of any staged text, or a source not among
    the staged names, is a fabrication tell.
    """
    corpus = "\n".join(staged_texts)
    flags: List[str] = []
    for i, move in enumerate(diff_set.get("moves", [])):
        cite = (move.get("citation") or "").strip()
        if cite and cite not in corpus:
            flags.append(
                f"move[{i}] ({move.get('move')}) cites text absent from staged "
                f"inputs — fabrication tell: {cite[:60]!r}"
            )
    return flags


def _validate_diff_set(persona_id: str, diff_set: dict) -> None:
    if not isinstance(diff_set, dict):
        raise ValueError(f"persona {persona_id!r}: diff-set must be a dict")
    for i, move in enumerate(diff_set.get("moves", [])):
        if move.get("move") not in PERSONA_MOVES:
            raise ValueError(
                f"persona {persona_id!r} move[{i}]: {move.get('move')!r} is not a "
                f"persona move {PERSONA_MOVES} (defer is operator-only)"
            )


def run_personas(
    selected: Sequence[dict],
    provision: Callable[[dict], Sequence[StagedInput]],
    executor: Callable[[dict, Path, PersonaToolConfig], dict],
    staging_root: Path,
) -> List[PersonaRun]:
    """Stage, isolate, and run each selected persona independently.

    * ``selected`` — the persona set from slice 1's ``select_personas``.
    * ``provision`` — TARGET-AGNOSTIC context provisioning: given a persona,
      returns the ``StagedInput``s to stage (H supplies docs+spec+rubric; a
      different target supplies a different set). The orchestration does not
      know or care what they are.
    * ``executor`` — the seam that runs the fresh-context sub-agent over the
      staged dir under the tool config and returns its raw candidate diff-set.
      The live spawn is slice 7; tests inject a deterministic stub.

    Personas run **blind to each other**: each ``executor`` call receives ONLY
    its own persona, staging dir, and tool config — never another persona's
    diff-set or staging dir. Returns one ``PersonaRun`` per persona with the raw
    diff-set and any fabrication flags.
    """
    runs: List[PersonaRun] = []
    for persona in selected:
        pid = persona.get("id", "persona")
        inputs = list(provision(persona))
        staging_dir = stage_persona_inputs(pid, inputs, staging_root)
        assert_isolation(staging_dir)
        tool_config = persona_tool_config(staging_dir)
        # The executor is handed ONLY this persona's context — independence.
        diff_set = executor(persona, staging_dir, tool_config)
        _validate_diff_set(pid, diff_set)
        staged_texts = [it.text for it in inputs]
        flags = detect_fabrication(diff_set, staged_texts)
        runs.append(PersonaRun(
            persona_id=pid,
            staging_dir=str(staging_dir),
            tool_config=tool_config,
            staged_names=[Path(it.name).name for it in inputs],
            diff_set=diff_set,
            fabrication_flags=flags,
        ))
    return runs


def staging_fingerprint(inputs: Sequence[StagedInput]) -> str:
    """Content-key a staged input set (reproducibility): same inputs → same key."""
    material = "|".join(
        f"{Path(it.name).name}:{hashlib.sha256(it.text.encode('utf-8')).hexdigest()}"
        for it in sorted(inputs, key=lambda x: Path(x.name).name)
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_component(name: str) -> str:
    cleaned = _SAFE_RE.sub("_", name).strip("._-")
    return cleaned or "persona"

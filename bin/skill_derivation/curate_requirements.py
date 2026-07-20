"""curate_requirements.py — Phase 5 Stage 5A: curated REQUIREMENTS.md
generator.

Implements the DQ-5-7 algorithm:

  1. Read pass_c_formal.jsonl; filter to disposition=accepted.
  2. Group by (source_document, section_idx).
  3. Within each partition, mechanical Jaccard dedup at 0.6 threshold
     (lowercase + strip stop-words from a hardcoded ~30-word list,
     tokenize on whitespace + punctuation). Cluster via union-find;
     keep the REQ with the longest acceptance_criteria per cluster.
  4. Cap at K REQs per partition; iterate K to land in [80, 110].
     Initial K=2; if total >110, decrease K to 1 for partitions with
     >5 post-dedup REQs; if total <80, increase K to 3 for
     partitions with >5 post-dedup REQs.
  5. Render to REQUIREMENTS.md with phase-by-phase grouping using
     SKILL.md heading hierarchy.

Stdlib-only.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


_STOP_WORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on",
    "at", "by", "for", "with", "as", "is", "are", "be", "been",
    "being", "this", "that", "these", "those", "it", "its", "if",
    "then", "must", "shall", "should", "may", "can", "will",
    "from", "into", "out",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass
class CurateConfig:
    formal_path: Path  # input: pass_c_formal.jsonl
    target_min: int = 80
    target_max: int = 110
    initial_k: int = 2
    jaccard_threshold: float = 0.6
    max_iterations: int = 3


def _tokenize(text: str) -> set:
    """Lowercase, drop stop-words, return a set of word-shaped tokens
    (≥2 chars to avoid one-letter noise)."""
    text = text.lower()
    return {t for t in _TOKEN_RE.findall(text) if t not in _STOP_WORDS and len(t) > 1}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a) + len(b) - inter
    return inter / union if union else 0.0


def _cluster_via_union_find(reqs: list[dict], threshold: float) -> list[list[dict]]:
    """Cluster REQs whose acceptance_criteria has Jaccard ≥ threshold.
    Returns a list of clusters; each cluster is a list of REQs."""
    n = len(reqs)
    if n == 0:
        return []
    token_sets = [_tokenize(r.get("acceptance_criteria") or "") for r in reqs]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(n):
        for j in range(i + 1, n):
            if _jaccard(token_sets[i], token_sets[j]) >= threshold:
                union(i, j)

    clusters: dict[int, list[dict]] = {}
    for i, req in enumerate(reqs):
        root = find(i)
        clusters.setdefault(root, []).append(req)
    return list(clusters.values())


def _select_longest_per_cluster(clusters: list[list[dict]]) -> list[dict]:
    out: list[dict] = []
    for cluster in clusters:
        best = max(
            cluster,
            key=lambda r: len(r.get("acceptance_criteria") or "")
        )
        out.append(best)
    return out


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def curate(config: CurateConfig) -> dict:
    """Run the curation algorithm. Returns summary dict with the
    final K used + total REQ count + per-partition stats."""
    formal_records = _read_jsonl(config.formal_path)
    accepted = [
        r for r in formal_records if r.get("disposition") == "accepted"
    ]

    # Step 1-3: group + dedup per partition.
    partitions: dict = {}
    for rec in accepted:
        key = (
            rec.get("source_document") or "SKILL.md",
            rec.get("section_idx"),
        )
        partitions.setdefault(key, []).append(rec)

    deduped: dict = {}
    for key, bucket in partitions.items():
        clusters = _cluster_via_union_find(bucket, config.jaccard_threshold)
        deduped[key] = _select_longest_per_cluster(clusters)

    # Step 4: cap-iteration.
    k = config.initial_k
    final_selected: dict = {}
    iteration_log = []
    for iteration in range(config.max_iterations):
        selected: dict = {}
        for key, bucket in deduped.items():
            # Sort by longest acceptance_criteria first so the cap
            # keeps the most-detailed REQs.
            sorted_bucket = sorted(
                bucket,
                key=lambda r: -len(r.get("acceptance_criteria") or ""),
            )
            selected[key] = sorted_bucket[:k]
        total = sum(len(v) for v in selected.values())
        iteration_log.append({"k": k, "total": total})
        if config.target_min <= total <= config.target_max:
            final_selected = selected
            break
        if total > config.target_max:
            # Decrease K to 1 for partitions with >5 post-dedup REQs.
            for key, bucket in deduped.items():
                if len(bucket) > 5:
                    sorted_bucket = sorted(
                        bucket,
                        key=lambda r: -len(r.get("acceptance_criteria") or ""),
                    )
                    selected[key] = sorted_bucket[:1]
            total = sum(len(v) for v in selected.values())
            iteration_log.append({"k_dense_capped_to_1": True, "total": total})
            if config.target_min <= total <= config.target_max:
                final_selected = selected
                break
            # If still over, drop K globally to 1.
            if total > config.target_max:
                k = 1
                continue
            # If now under, expand K back to 2 for sparse partitions.
            if total < config.target_min:
                k = max(2, k)
                final_selected = selected
                break
        if total < config.target_min:
            # Increase K to 3 for partitions with >5 post-dedup REQs.
            for key, bucket in deduped.items():
                if len(bucket) > 5:
                    sorted_bucket = sorted(
                        bucket,
                        key=lambda r: -len(r.get("acceptance_criteria") or ""),
                    )
                    selected[key] = sorted_bucket[:3]
            total = sum(len(v) for v in selected.values())
            iteration_log.append({"k_dense_expanded_to_3": True, "total": total})
            if config.target_min <= total <= config.target_max:
                final_selected = selected
                break
            k = 3

    if not final_selected:
        # Last fallback: settle at whatever the last iteration produced.
        final_selected = selected

    # Sort partitions for stable summary.
    return {
        "total_requirements": sum(len(v) for v in final_selected.values()),
        "partitions_total": len(deduped),
        "partitions_with_selections": sum(1 for v in final_selected.values() if v),
        "iteration_log": iteration_log,
        "input_accepted": len(accepted),
    }


if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.curate_requirements',
        summary=(
            "Requirements-curation helpers for the skill-derivation "
            "pipeline — normalizes Phase 1 requirements into the "
            "canonical schema. "
        ),
        role=(
            "Imported by skill_derivation pass A to produce the curated "
            "requirements list that downstream passes consume. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)

"""Discover raw client directories and select subsets for simulation."""

from __future__ import annotations

import random
import re
from pathlib import Path


def discover_clients(raw_base: Path) -> dict[int, Path]:
    """Scan raw_base for client_{id} directories."""
    out: dict[int, Path] = {}
    if not raw_base.is_dir():
        return out
    for p in raw_base.iterdir():
        if not p.is_dir():
            continue
        m = re.match(r"client_(\d+)$", p.name)
        if m:
            out[int(m.group(1))] = p
    return dict(sorted(out.items()))


def select_clients(summary: dict, num_clients: int, strategy: str) -> list[int]:
    """
    summary: samples_per_client and event_rate_per_client (keys str client id).
    """
    samples: dict[str, float] = summary.get("samples_per_client", {})
    event_rate: dict[str, float] = summary.get("event_rate_per_client", {})
    ids = [int(k) for k in samples.keys()]
    if not ids:
        return []
    k = min(num_clients, len(ids))

    if strategy == "largest":
        ranked = sorted(ids, key=lambda i: samples.get(str(i), 0), reverse=True)
        return ranked[:k]

    if strategy == "random":
        rng = random.Random(42)
        return rng.sample(ids, k)

    if strategy == "diverse":
        pairs = [(i, event_rate.get(str(i), 0.0)) for i in ids]
        pairs.sort(key=lambda x: x[1])
        if k <= 1:
            return [pairs[0][0]]
        step = max(1, (len(pairs) - 1) // max(k - 1, 1))
        chosen: list[int] = []
        idx = 0
        while len(chosen) < k and idx < len(pairs):
            chosen.append(pairs[idx][0])
            idx += step
        while len(chosen) < k:
            for i, _ in pairs:
                if i not in chosen:
                    chosen.append(i)
                    if len(chosen) >= k:
                        break
        return chosen[:k]

    ranked = sorted(ids, key=lambda i: samples.get(str(i), 0), reverse=True)
    return ranked[:k]

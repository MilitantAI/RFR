"""Invariant-band vectorized field solver, bucketed.

- Safety by static invariant: band width = min possible step cost, so band
  members are mutually non-influencing (every edge >= band width). No runtime
  safety checks, no heap, no global order.
- Nodes are filed into their band bucket when improved (lazy deletion).
- A whole band is settled and relaxed as vectorized array ops, 4 per stencil
  direction. Exact Dijkstra-identical distances.
"""
import numpy as np


def banded_field(n, cost=None, resolution=1.0):
    N = n * n
    cflat = np.zeros(N) if cost is None else np.asarray(cost, dtype=np.float64).ravel()
    delta = resolution + float(cflat.min())      # static safety invariant
    step = resolution + cflat

    dist = np.full(N, np.inf)
    dist[0] = 0.0
    settled = np.zeros(N, dtype=bool)
    buckets = {0: [np.array([0], dtype=np.int64)]}
    k = 0

    while buckets:
        if k not in buckets:
            k = min(buckets)
        parts = buckets.pop(k)
        b = np.unique(np.concatenate(parts))
        b = b[~settled[b]]
        d = dist[b]
        live = d < (k + 1) * delta               # lazy-deletion filter
        b, d = b[live], d[live]
        if b.size == 0:
            k += 1
            continue
        settled[b] = True
        x = b % n
        for off, valid in ((-1, x > 0), (1, x < n - 1), (-n, b >= n), (n, b < N - n)):
            t = b[valid] + off
            cand = d[valid] + step[t]
            m = cand < dist[t]
            if not m.any():
                continue
            tm, cm = t[m], cand[m]
            dist[tm] = cm
            for key in np.unique(cm // delta).astype(np.int64):
                sel = (cm // delta).astype(np.int64) == key
                buckets.setdefault(int(key), []).append(tm[sel])
        k += 1
    return dist

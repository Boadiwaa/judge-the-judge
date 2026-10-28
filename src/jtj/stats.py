"""Statistics for the study (BUILD_SPEC §2.7). Implemented from first principles; cross-checked
against irrCAC in tests.

Gwet formulas follow Gwet (2014), *Handbook of Inter-Rater Reliability*, 4th ed., ch. 2–3:
  p_a = mean over subjects with r_i ≥ 2 of  Σ_k r_ik (r*_ik − 1) / (r_i (r_i − 1)),  r*_ik = Σ_l w_kl r_il
  p_e = T_w / (q (q − 1)) · Σ_k π_k (1 − π_k),   π_k = mean_i r_ik / r_i,   T_w = Σ_kl w_kl
  AC  = (p_a − p_e) / (1 − p_e)
With identity weights this is AC1; with ordinal/quadratic weights it is AC2.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Hashable, Sequence

import numpy as np
from scipy.stats import binom

BOOTSTRAP_SEED = 20261028
BOOTSTRAP_N = 2000


# ---------------- proportions ----------------


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float, float]:
    """Point estimate and Wilson score 95% interval. Returns (p, lo, hi); (nan, nan, nan) if n == 0."""
    if n == 0:
        return (math.nan, math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (p, max(0.0, centre - half), min(1.0, centre + half))


def n_for_halfwidth(p: float, halfwidth: float, z: float = 1.959963984540054) -> int:
    """Normal-approximation sample size for a CI of ±halfwidth around proportion p."""
    return math.ceil(z * z * p * (1 - p) / halfwidth**2)


# ---------------- paired tests ----------------


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value from discordant counts b (A only) and c (B only)."""
    n = b + c
    if n == 0:
        return 1.0
    return float(min(1.0, 2 * binom.cdf(min(b, c), n, 0.5)))


def mcnemar_from_pairs(a: Sequence[bool], b: Sequence[bool]) -> dict:
    if len(a) != len(b):
        raise ValueError("paired sequences differ in length")
    only_a = sum(1 for x, y in zip(a, b) if x and not y)
    only_b = sum(1 for x, y in zip(a, b) if y and not x)
    return {"only_a": only_a, "only_b": only_b, "n": len(a), "p": mcnemar_exact(only_a, only_b)}


def holm(pvals: Sequence[float]) -> list[float]:
    """Holm step-down adjusted p-values, returned in the input order."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


# ---------------- weights ----------------


def weight_matrix(q: int, kind: str = "identity") -> np.ndarray:
    k = np.arange(q)
    d = np.abs(k[:, None] - k[None, :]).astype(float)
    if kind == "identity":
        return np.eye(q)
    if kind == "quadratic":
        return 1 - (d / (q - 1)) ** 2
    if kind == "linear":
        return 1 - d / (q - 1)
    if kind == "ordinal":
        m = (d + 1) * d / 2  # C(|k-l|+1, 2)
        return 1 - m / m.max()
    raise ValueError(kind)


# ---------------- kappa ----------------


def weighted_kappa(a: Sequence, b: Sequence, categories: Sequence, weights: str = "quadratic") -> float:
    """Cohen's weighted kappa for two raters (agreement-weight formulation)."""
    if len(a) != len(b) or not a:
        return math.nan
    idx = {c: i for i, c in enumerate(categories)}
    q = len(categories)
    obs = np.zeros((q, q))
    for x, y in zip(a, b):
        obs[idx[x], idx[y]] += 1
    obs /= obs.sum()
    w = weight_matrix(q, weights)
    exp = np.outer(obs.sum(1), obs.sum(0))
    po, pe = (w * obs).sum(), (w * exp).sum()
    return math.nan if pe == 1 else float((po - pe) / (1 - pe))


# ---------------- Gwet ----------------


def gwet_ac(
    ratings: Sequence[Sequence[Hashable | None]],
    categories: Sequence[Hashable],
    weights: str = "identity",
) -> dict:
    """Gwet's AC1 (identity weights) or AC2 (other weights).

    ratings: one row per subject, one column per rater; None = not rated.
    Returns dict with pa, pe, coeff.
    """
    q = len(categories)
    idx = {c: i for i, c in enumerate(categories)}
    w = weight_matrix(q, weights)
    counts = np.zeros((len(ratings), q))
    for i, row in enumerate(ratings):
        for r in row:
            if r is not None:
                counts[i, idx[r]] += 1
    ri = counts.sum(1)
    rated = ri > 0
    multi = ri >= 2
    if multi.sum() == 0:
        return {"pa": math.nan, "pe": math.nan, "coeff": math.nan}
    rstar = counts @ w.T
    pa_i = (counts[multi] * (rstar[multi] - 1)).sum(1) / (ri[multi] * (ri[multi] - 1))
    pa = pa_i.mean()
    pi_k = (counts[rated] / ri[rated, None]).mean(0)
    tw = w.sum()
    pe = tw / (q * (q - 1)) * (pi_k * (1 - pi_k)).sum()
    coeff = math.nan if pe == 1 else (pa - pe) / (1 - pe)
    return {"pa": float(pa), "pe": float(pe), "coeff": float(coeff)}


def gwet_ac1(ratings, categories) -> float:
    return gwet_ac(ratings, categories, "identity")["coeff"]


def gwet_ac2(ratings, categories, weights: str = "ordinal") -> float:
    return gwet_ac(ratings, categories, weights)["coeff"]


# ---------------- cluster bootstrap ----------------


def cluster_bootstrap(
    items: Sequence,
    cluster_of: Callable[[object], Hashable],
    statistic: Callable[[list], float],
    n_boot: int = BOOTSTRAP_N,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float, float]:
    """Resample clusters (cases) with replacement; percentile 95% CI. Returns (estimate, lo, hi)."""
    est = statistic(list(items))
    groups: dict[Hashable, list] = {}
    for it in items:
        groups.setdefault(cluster_of(it), []).append(it)
    keys = list(groups)
    if len(keys) < 2:
        return (est, math.nan, math.nan)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(keys), len(keys))
        sample = [x for j in pick for x in groups[keys[j]]]
        v = statistic(sample)
        if not math.isnan(v):
            vals.append(v)
    if not vals:
        return (est, math.nan, math.nan)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (est, float(lo), float(hi))

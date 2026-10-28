import math

import numpy as np
import pandas as pd
import pytest

from jtj import stats


def test_wilson_known_values():
    # Newcombe (1998) / Wilson: 81/263 -> 0.2553 to 0.3662
    p, lo, hi = stats.wilson(81, 263)
    assert p == pytest.approx(0.30798, abs=1e-4)
    assert lo == pytest.approx(0.2553, abs=1e-3)
    assert hi == pytest.approx(0.3662, abs=1e-3)


def test_wilson_edges():
    assert stats.wilson(0, 10)[1] == 0.0
    assert stats.wilson(10, 10)[2] == pytest.approx(1.0)
    assert all(math.isnan(x) for x in stats.wilson(0, 0))


def test_spec_halfwidth_claim():
    # Spec §2.7: ~40 errors at 0.80 gives roughly ±0.13
    _, lo, hi = stats.wilson(32, 40)
    assert (hi - lo) / 2 == pytest.approx(0.12, abs=0.015)
    assert stats.n_for_halfwidth(0.8, 0.05) == 246


def test_mcnemar_exact():
    assert stats.mcnemar_exact(0, 0) == 1.0
    # b=1, c=9: 2 * P(X<=1 | n=10, .5) = 2 * 11/1024
    assert stats.mcnemar_exact(1, 9) == pytest.approx(22 / 1024)
    assert stats.mcnemar_exact(5, 5) == 1.0
    r = stats.mcnemar_from_pairs([1, 1, 0, 0, 1], [1, 0, 0, 1, 1])
    assert (r["only_a"], r["only_b"]) == (1, 1)


def test_holm():
    assert stats.holm([0.01, 0.04]) == pytest.approx([0.02, 0.04])
    assert stats.holm([0.04, 0.01]) == pytest.approx([0.04, 0.02])
    assert stats.holm([0.03, 0.02]) == pytest.approx([0.04, 0.04])  # monotonicity enforced


def test_weighted_kappa_perfect_and_known():
    cats = [1, 2, 3, 4, 5]
    assert stats.weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5], cats) == pytest.approx(1.0)
    a = [1, 2, 3, 3, 4, 5, 2, 1]
    b = [1, 3, 3, 2, 4, 4, 2, 2]
    sk = pytest.importorskip("sklearn.metrics")
    assert stats.weighted_kappa(a, b, cats) == pytest.approx(sk.cohen_kappa_score(a, b, weights="quadratic"))


def test_weighted_kappa_hand_computed():
    # 2x2 with quadratic weights reduces to unweighted kappa.
    # a=[1,1,2,2], b=[1,2,2,2]: po=.75, pe=.5*.25+.5*.75=.5 -> kappa=.5
    assert stats.weighted_kappa([1, 1, 2, 2], [1, 2, 2, 2], [1, 2]) == pytest.approx(0.5)


# Worked example: Gwet (2014) Table 2.16-style dataset, 2 raters, 3 categories.
TWO_RATER = [
    ("a", "a"), ("a", "a"), ("a", "b"), ("b", "b"), ("b", "b"),
    ("b", "c"), ("c", "c"), ("c", "c"), ("a", "a"), ("c", "b"),
]


def test_gwet_ac1_hand_computed():
    # pa = 7/10. pi = (a: 5/20, b: 7/20, c: 8/20 ... recount below)
    a = sum(r.count("a") for r in TWO_RATER) / 20
    b = sum(r.count("b") for r in TWO_RATER) / 20
    c = sum(r.count("c") for r in TWO_RATER) / 20
    pe = (a * (1 - a) + b * (1 - b) + c * (1 - c)) / 2
    expected = (0.7 - pe) / (1 - pe)
    assert stats.gwet_ac1(TWO_RATER, ["a", "b", "c"]) == pytest.approx(expected)


def test_gwet_perfect_agreement():
    assert stats.gwet_ac1([(1, 1), (2, 2), (1, 1)], [1, 2]) == pytest.approx(1.0)


@pytest.mark.parametrize("weights", ["identity", "quadratic", "ordinal", "linear"])
def test_gwet_matches_irrcac(weights):
    irr = pytest.importorskip("irrCAC.raw")
    rng = np.random.default_rng(1)
    cats = [1, 2, 3, 4, 5]
    truth = rng.integers(1, 6, 40)
    r1 = np.clip(truth + rng.integers(-1, 2, 40), 1, 5)
    r2 = np.clip(truth + rng.integers(-1, 2, 40), 1, 5)
    r3 = [None if i % 7 == 0 else int(x) for i, x in enumerate(np.clip(truth + rng.integers(-2, 3, 40), 1, 5))]
    rows = list(zip(r1.tolist(), r2.tolist(), r3))
    ours = stats.gwet_ac(rows, cats, weights)["coeff"]
    df = pd.DataFrame(rows, columns=["r1", "r2", "r3"]).astype("float")
    theirs = irr.CAC(df, weights=weights, categories=[float(c) for c in cats]).gwet()["est"]["coefficient_value"]
    assert ours == pytest.approx(theirs, abs=1e-4)


def test_cluster_bootstrap_deterministic():
    items = [(c, x) for c in range(10) for x in (0, 1)]
    stat = lambda xs: float(np.mean([x for _, x in xs]))
    a = stats.cluster_bootstrap(items, lambda it: it[0], stat, n_boot=200)
    b = stats.cluster_bootstrap(items, lambda it: it[0], stat, n_boot=200)
    assert a == b and a[0] == 0.5

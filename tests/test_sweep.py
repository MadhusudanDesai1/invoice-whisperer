"""Unit tests for the threshold sweep."""
import pandas as pd

from invoice_whisperer.sweep import best_operating_point, sweep


def make() -> pd.DataFrame:
    return pd.DataFrame({"confidence": [0.99, 0.9, 0.6], "correct": [True, True, False]})


def test_sweep_values():
    sw = sweep(make(), [0.5, 0.8, 0.95])
    assert list(sw["auto_accept_rate"].round(3)) == [1.0, 0.667, 0.333]
    assert sw.loc[0, "confident_errors"] == 1
    assert sw.loc[1, "confident_errors"] == 0


def test_best_point_picks_most_auto_at_target():
    sw = sweep(make(), [0.5, 0.8, 0.95])
    assert best_operating_point(sw, 0.99)["threshold"] == 0.8


def test_best_point_none_when_unreachable():
    df = pd.DataFrame({"confidence": [0.9], "correct": [False]})
    assert best_operating_point(sweep(df, [0.5]), 0.9) is None

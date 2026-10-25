"""Unit tests for the token budget (fake clock, no real sleeping)."""
from invoice_whisperer.ratelimit import TokenBudget


def test_three_calls_fit_fourth_waits():
    t = [0.0]
    b = TokenBudget(8000, safety=0.95, clock=lambda: t[0], sleeper=lambda s: None)
    b.record(2400)
    t[0] = 10
    assert b.wait_time() == 0          # 2 calls fit
    b.record(2400)
    t[0] = 20
    assert b.wait_time() == 0          # 3 calls fit
    b.record(2400)
    w = b.wait_time()                  # 4th must wait for the first to expire (t=60)
    assert 39 <= w <= 41


def test_min_gap_respected():
    t = [0.0]
    b = TokenBudget(8000, min_gap=5, clock=lambda: t[0], sleeper=lambda s: None)
    b.record(1000)
    t[0] = 2
    assert 2.9 <= b.wait_time() <= 3.1

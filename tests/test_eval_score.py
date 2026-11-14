"""Scoring rules and Wilson CI. See evalkit/score.py."""
from __future__ import annotations

import math

from evalkit.score import (
    normalize_text,
    score,
    score_count,
    score_quantity,
    score_text,
    wilson,
)


def test_score_count_exact_match_after_rounding():
    assert score_count(4, 4) is True
    assert score_count(4.0, 4) is True
    assert score_count("4", 4) is True
    assert score_count(4.49, 4) is True  # rounds to 4
    assert score_count(3, 4) is False
    assert score_count(None, 4) is False
    assert score_count(4, None) is False


def test_score_quantity_relative_error_2pct():
    # exactly at the 2% boundary is accepted
    assert score_quantity(102.0, 100.0) is True
    assert score_quantity(98.0, 100.0) is True
    assert score_quantity(102.1, 100.0) is False
    assert score_quantity(97.9, 100.0) is False


def test_score_quantity_zero_truth_requires_exact():
    assert score_quantity(0, 0) is True
    assert score_quantity(0.01, 0) is False


def test_score_text_normalised_exact_match():
    assert score_text("Apartment A, difference: 2", "apartment a difference 2") is True
    assert normalize_text("  Hello, World!  ") == "hello world"
    assert score_text("yes", "no") is False


def test_score_dispatch_by_kind():
    assert score("count", 3, 3) is True
    assert score("area", 50.5, 50.0) is True
    assert score("length", 1000, 100) is False
    assert score("volume", 10, 10) is True
    assert score("text", "A", "a") is True
    assert score("other", 1, 1) is False  # unscored kind: never silently "correct"


def test_wilson_known_bounds():
    # classic textbook value: 8/10 Wilson 95% CI is about (0.49, 0.94)
    lo, hi = wilson(8, 10)
    assert math.isclose(lo, 0.49, abs_tol=0.02)
    assert math.isclose(hi, 0.94, abs_tol=0.02)


def test_wilson_n_zero():
    assert wilson(0, 0) == (0.0, 0.0)


def test_wilson_bounds_within_0_1():
    for k, n in [(0, 5), (5, 5), (1, 1000), (999, 1000)]:
        lo, hi = wilson(k, n)
        assert 0.0 <= lo <= hi <= 1.0

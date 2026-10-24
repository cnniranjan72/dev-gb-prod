from __future__ import annotations

import math

import pytest

from app.services.metrics import compute_metrics, error_histogram


def test_mae_rmse_bias_hand_computed():
    pairs = [(120.0, 100.0), (90.0, 100.0), (100.0, 90.0)]
    result = compute_metrics(pairs)
    assert result.count == 3
    assert result.mae_mw == pytest.approx(13.3, abs=0.1)
    assert result.rmse_mw == pytest.approx(math.sqrt(200.0), abs=0.05)
    # bias = forecast - actual; overforecasting => positive
    assert result.mean_bias_mw == pytest.approx(6.7, abs=0.1)


def test_bias_convention_negative_means_underforecast():
    result = compute_metrics([(80.0, 100.0)])
    assert result.mean_bias_mw < 0  # underforecast
    assert result.mae_mw == 20.0


def test_empty_pairs_give_count_zero_and_no_nan():
    result = compute_metrics([])
    assert result.count == 0
    assert result.mae_mw is None and result.rmse_mw is None and result.mean_bias_mw is None


def test_invalid_pairs_excluded_not_zeroed():
    result = compute_metrics([(None, 100.0), (150.0, None), (float("nan"), 90.0), (110.0, 100.0)])
    assert result.count == 1
    assert result.mae_mw == 10.0


def test_zero_and_near_zero_actuals_are_valid_pairs():
    result = compute_metrics([(50.0, 0.0), (1.0, 0.5)])
    assert result.count == 2
    # metrics report to 1 decimal MW everywhere
    assert result.mean_bias_mw == 25.2


def test_histogram_zero_centred_fixed_width():
    bins = error_histogram([-1200.0, -300.0, 100.0, 1400.0], bin_width_mw=500)
    shape = [(b.lower_mw, b.upper_mw, b.count) for b in bins]
    assert shape == [(-1500.0, -1000.0, 1), (-500.0, 0.0, 1), (0.0, 500.0, 1), (1000.0, 1500.0, 1)]


def test_histogram_empty_is_empty():
    assert error_histogram([]) == []
    assert error_histogram([float("nan")]) == []

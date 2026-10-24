from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class MetricsResult:
    count: int
    mae_mw: object | None
    rmse_mw: object | None
    mean_bias_mw: object | None

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "mae_mw": self.mae_mw,
            "rmse_mw": self.rmse_mw,
            "mean_bias_mw": self.mean_bias_mw,
        }


def compute_metrics(pairs: Sequence[tuple[object, object]]) -> MetricsResult:
    """Forecast-accuracy metrics over (forecast, actual) pairs in MW.

    Valid-pair policy (documented and tested):
      * a pair is valid only when BOTH values are finite numbers
        (missing actuals stay missing — never treated as zero);
      * `mean_bias = forecast - actual`: positive = overforecast,
        negative = underforecast — the single documented convention reused by
        every accuracy view in the product;
      * empty input yields `count: 0` and None metrics, never NaN, so the API
        distinguishes "no aligned observations" from a computation error.
    """
    finite = [
        (f, a)
        for f, a in ((pair[0], pair[1]) for pair in pairs)
        if isinstance(f, (int, float))
        and isinstance(a, (int, float))
        and not isinstance(f, bool)
        and not isinstance(a, bool)
        and math.isfinite(float(f))
        and math.isfinite(float(a))
    ]
    if not finite:
        return MetricsResult(count=0, mae_mw=None, rmse_mw=None, mean_bias_mw=None)
    errors = [float(f) - float(a) for f, a in finite]
    n = len(errors)
    mae = sum(abs(e) for e in errors) / n
    rmse = math.sqrt(sum(e * e for e in errors) / n)
    bias = sum(errors) / n
    return MetricsResult(count=n, mae_mw=round(mae, 1), rmse_mw=round(rmse, 1), mean_bias_mw=round(bias, 1))


@dataclass(frozen=True)
class ErrorHistogramBin:
    lower_mw: float
    upper_mw: float
    count: int


def error_histogram(errors_mw: Sequence[float], bin_width_mw: float = 500) -> list[ErrorHistogramBin]:
    """Fixed-width bins centred on zero; degrees of freedom fixed by policy,
    never data-dependent, so two datasets are comparable."""
    if not errors_mw or bin_width_mw <= 0:
        return []
    binned: dict[tuple[float, float], int] = {}
    values = [float(e) for e in errors_mw if isinstance(e, (int, float)) and math.isfinite(float(e))]
    if not values:
        return []
    lo = -math.ceil(max(abs(min(values)), abs(max(values))) / bin_width_mw) * bin_width_mw
    for value in values:
        lower = lo + (math.floor((value - lo) / bin_width_mw) * bin_width_mw)
        upper = lower + bin_width_mw
        binned[(round(lower, 6), round(upper, 6))] = binned.get((round(lower, 6), round(upper, 6)), 0) + 1
    keys = sorted(binned)
    return [ErrorHistogramBin(lower_mw=k[0], upper_mw=k[1], count=binned[k]) for k in keys]

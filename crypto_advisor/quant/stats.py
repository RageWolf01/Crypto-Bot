"""Small statistics helpers. Standard library only, on purpose.

No numpy, no pandas. This is deliberate: the user reads and modifies this code,
and a few explicit loops are easier to audit than a stack of vectorised
one-liners whose edge cases are invisible. Nothing here is performance-critical
-- the universe is at most a few hundred assets.
"""

from __future__ import annotations

import math


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: list[float]) -> float:
    """Sample standard deviation (n-1). Returns 0.0 for degenerate input."""
    n = len(values)
    if n < 2:
        return 0.0
    mu = sum(values) / n
    variance = sum((v - mu) ** 2 for v in values) / (n - 1)
    return math.sqrt(max(0.0, variance))


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def percentile(values: list[float], fraction: float) -> float:
    """Linear-interpolated percentile. ``fraction`` in 0.0 - 1.0."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, fraction)) * (len(ordered) - 1)
    low = int(math.floor(position))
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def log_interp(value: float | None, low: float, high: float) -> float | None:
    """Map a positive quantity onto 0-1 across a log scale.

    Log scale because every quantity this is used for (volume, depth, market
    cap) spans several orders of magnitude, and the difference between $1M and
    $10M matters far more than between $1B and $1.01B.
    """
    if value is None or value <= 0:
        return None
    if low <= 0 or high <= low:
        return None
    scaled = (math.log10(value) - math.log10(low)) / (math.log10(high) - math.log10(low))
    return clamp(scaled)


def descending_interp(value: float | None, good: float, bad: float) -> float | None:
    """Map a quantity onto 0-1 where *lower is better* (e.g. spreads, ratios).

    ``good`` scores 1.0, ``bad`` scores 0.0, linear in between.
    """
    if value is None:
        return None
    if bad == good:
        return None
    return clamp((bad - value) / (bad - good))


def ascending_interp(value: float | None, bad: float, good: float) -> float | None:
    """Map a quantity onto 0-1 where *higher is better*, linear in between."""
    if value is None:
        return None
    if good == bad:
        return None
    return clamp((value - bad) / (good - bad))


def band_score(value: float | None, low: float, high: float, fade: float) -> float | None:
    """Score a quantity that is good in a *band* and suspicious outside it.

    Built for turnover: too little volume means you cannot exit, but a
    suspiciously large turnover on a small coin usually means wash trading, so
    both tails are penalised and the middle is rewarded.
    """
    if value is None:
        return None
    if value <= 0:
        return 0.0
    if low <= value <= high:
        return 1.0
    if value < low:
        return clamp(value / low) if low > 0 else 0.0
    return clamp(1.0 - (value - high) / fade) if fade > 0 else 0.0


def winsorize(values: list[float], low: float = 0.02, high: float = 0.98) -> list[float]:
    """Clip extreme values to percentile bounds.

    Cross-sectional z-scores are fragile when one asset has a 4000% return, so
    the tails are clipped before standardising.
    """
    if len(values) < 3:
        return list(values)
    lo = percentile(values, low)
    hi = percentile(values, high)
    return [max(lo, min(hi, v)) for v in values]


def zscores(values: list[float], clamp_abs: float | None = None) -> list[float]:
    """Standardise to mean 0, sd 1. Returns zeros if there is no dispersion."""
    if not values:
        return []
    mu = mean(values)
    sd = stdev(values)
    if sd <= 0:
        return [0.0 for _ in values]
    out = [(v - mu) / sd for v in values]
    if clamp_abs is not None:
        out = [max(-clamp_abs, min(clamp_abs, z)) for z in out]
    return out


def logistic(value: float, scale: float = 1.0) -> float:
    """Squash a z-score onto 0-1.

    ``scale`` controls how fast it saturates; 1.6 maps a z of roughly +/-2.5 to
    about 0.02/0.98, which keeps the extremes from becoming 0 or 1 and looking
    more certain than they are.
    """
    try:
        return 1.0 / (1.0 + math.exp(-value / scale))
    except OverflowError:  # pragma: no cover - defensive
        return 0.0 if value < 0 else 1.0


def max_drawdown(closes: list[float]) -> float | None:
    """Largest peak-to-trough decline, as a positive fraction.

    0.60 means the asset fell 60% from a prior high at some point in the window.
    """
    if len(closes) < 2:
        return None
    peak = closes[0]
    worst = 0.0
    for price in closes:
        if price > peak:
            peak = price
        if peak > 0:
            decline = (peak - price) / peak
            if decline > worst:
                worst = decline
    return worst


def daily_log_returns(closes: list[float]) -> list[float]:
    out: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        if previous > 0 and current > 0:
            out.append(math.log(current / previous))
    return out


def downside_deviation(returns: list[float]) -> float:
    """Root-mean-square of the negative returns only.

    This is the denominator of the Sortino ratio. Only downside counts, because
    upside volatility is not a risk the way downside is.
    """
    negatives = [r for r in returns if r < 0]
    if not negatives:
        return 0.0
    return math.sqrt(sum(r * r for r in negatives) / len(negatives))


def safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator

"""Cross-sectional scoring: assemble the factor groups into one 0-100 number.

The only genuinely cross-sectional work lives here. Momentum is scored *relative
to the rest of the universe* because a 40% quarterly gain means something
completely different in a bull market than in a bear one, so the raw Sortino
ratios are standardised across all candidates first.

Everything else is absolute and comes from :mod:`crypto_advisor.quant.factors`.

The output is a ``ScoreCard`` per asset, including disqualified ones -- the
report shows those deliberately, because "why is X missing?" is the most common
question a screener raises.
"""

from __future__ import annotations

from typing import Any

from ..model import Asset, FactorScore, ScoreCard
from . import disqualifiers, factors, stats

# Logistic steepness when mapping a momentum z-score onto 0-1. At 1.3, a z of
# +2 lands near 0.82 and a z of -2 near 0.18: informative in the middle, without
# instantly saturating at the tails.
MOMENTUM_LOGISTIC_SCALE = 1.3

# Both momentum adjustments are deliberately blunt and deliberately few. A long
# list of small multipliers is how a score becomes unfalsifiable.
BELOW_TREND_MULTIPLIER = 0.75
DRAWDOWN_PENALTY_WEIGHT = 0.40
DRAWDOWN_PENALTY_FLOOR = 0.50

# Longer windows carry more weight: a 30-day pop is mostly noise, a 180-day
# trend is closer to an actual regime.
WINDOW_WEIGHTS = {30: 0.25, 90: 0.35, 180: 0.40}
DEFAULT_WINDOW_WEIGHT = 0.30

FACTOR_ORDER = ["liquidity", "momentum", "tokenomics", "traction", "valuation"]


def _window_weight(window: int) -> float:
    return WINDOW_WEIGHTS.get(window, DEFAULT_WINDOW_WEIGHT)


def _clipped_zscores(values: list[float], clamp_abs: float) -> list[float]:
    """Winsorise then standardise, preserving index alignment.

    Returns results in the same order as ``values``. ``stats.zscores`` alone is
    not enough because a single parabolic return can dominate both the mean and
    the standard deviation, so the tails are clipped first.
    """
    if len(values) < 3:
        return [0.0 for _ in values]
    low = stats.percentile(values, 0.02)
    high = stats.percentile(values, 0.98)
    clipped = [max(low, min(high, v)) for v in values]
    return stats.zscores(clipped, clamp_abs=clamp_abs)


def _momentum_group(assets: list[Asset], cfg: Any) -> dict[str, FactorScore]:
    """Score the momentum group for every asset, cross-sectionally."""
    windows = [int(w) for w in cfg.quant.momentum.windows]
    rf = float(cfg.quant.momentum.risk_free_annual)
    clamp_abs = float(cfg.quant.momentum.max_window_z)

    raws: dict[str, dict[str, Any]] = {
        a.symbol: factors.momentum_raw(a, windows, rf) for a in assets
    }

    # -- per-window cross-sectional scores -----------------------------------
    window_score: dict[int, dict[str, float]] = {}
    for window in windows:
        pairs: list[tuple[str, float]] = []
        for asset in assets:
            entry = (raws[asset.symbol].get("windows") or {}).get(window)
            if entry and entry.get("sortino") is not None:
                pairs.append((asset.symbol, float(entry["sortino"])))
        if len(pairs) < 3:
            # Too few candidates to rank relative to anything. Leave the window
            # unscored rather than inventing an absolute cut-off.
            window_score[window] = {}
            continue
        zs = _clipped_zscores([v for _, v in pairs], clamp_abs)
        window_score[window] = {
            symbol: stats.logistic(z, MOMENTUM_LOGISTIC_SCALE)
            for (symbol, _), z in zip(pairs, zs)
        }

    # -- assemble -------------------------------------------------------------
    out: dict[str, FactorScore] = {}
    for asset in assets:
        raw = raws[asset.symbol]
        available = {
            w: window_score.get(w, {}).get(asset.symbol) for w in windows
        }
        present = {w: s for w, s in available.items() if s is not None}

        if present:
            weight_sum = sum(_window_weight(w) for w in present)
            base = sum(_window_weight(w) * s for w, s in present.items()) / weight_sum
            coverage = weight_sum / sum(_window_weight(w) for w in windows)
        else:
            base = None
            coverage = 0.0

        notes: list[str] = []
        metrics: dict[str, float | None] = {}

        for window in windows:
            entry = (raw.get("windows") or {}).get(window)
            metrics[f"sortino_{window}"] = entry["sortino"] if entry else None
            metrics[f"return_{window}"] = entry["return"] if entry else None

        for window, entry in (raw.get("windows") or {}).items():
            if entry:
                notes.append(
                    f"{window}d: {entry['return'] * 100:+.1f}% return, "
                    f"{entry['vol_annual'] * 100:.0f}% annualised volatility, "
                    f"Sortino {entry['sortino']:.2f}"
                )

        if base is not None:
            if raw.get("above_200dma") is False:
                base *= BELOW_TREND_MULTIPLIER
                notes.append(
                    f"Price is below its 200-day average "
                    f"({raw.get('trend_distance_pct'):+.1f}%), so the momentum score is "
                    f"cut by {(1 - BELOW_TREND_MULTIPLIER) * 100:.0f}%."
                )
            elif raw.get("above_200dma") is True:
                notes.append(
                    f"Price is {raw.get('trend_distance_pct'):+.1f}% above its 200-day average."
                )

            drawdown = raw.get("max_drawdown")
            if drawdown:
                penalty = max(DRAWDOWN_PENALTY_FLOOR, 1 - DRAWDOWN_PENALTY_WEIGHT * drawdown)
                base *= penalty
                notes.append(
                    f"Worst peak-to-trough fall in the past year was {drawdown * 100:.0f}%, "
                    f"applying a {(1 - penalty) * 100:.0f}% penalty."
                )
            metrics["max_drawdown"] = drawdown
            metrics["trend_distance_pct"] = raw.get("trend_distance_pct")

        if not present:
            notes.append(
                "Not enough price history to score momentum at all, so this group "
                "is held at neutral."
            )
        elif len(present) < len(windows):
            missing = sorted(set(windows) - set(present))
            notes.append(f"No data for the {missing} day window(s).")

        out[asset.symbol] = FactorScore(
            name="momentum",
            weight=0.0,
            score=factors.shrink_toward_neutral(base, coverage),
            coverage=coverage,
            metrics=metrics,
            notes=notes,
        )
    return out


def score_universe(assets: list[Asset], cfg: Any) -> list[ScoreCard]:
    """Score and rank every asset. Disqualified assets are included, at the end."""
    weights = cfg.quant.weights.as_dict()
    momentum = _momentum_group(assets, cfg)

    cards: list[ScoreCard] = []
    for asset in assets:
        groups: list[FactorScore] = [
            factors.liquidity(asset),
            momentum[asset.symbol],
            factors.tokenomics(asset),
            factors.traction(asset),
            factors.valuation(asset),
        ]

        total_weight = 0.0
        weighted_sum = 0.0
        for group in groups:
            group.weight = float(weights.get(group.name, 0.0))
            total_weight += group.weight
            weighted_sum += group.weight * group.score
        total = (weighted_sum / total_weight * 100.0) if total_weight else 0.0

        dq, flags = disqualifiers.check(asset, cfg)

        cards.append(
            ScoreCard(
                symbol=asset.symbol,
                name=asset.name,
                rank=asset.rank,
                total=total,
                factors=groups,
                disqualified=bool(dq),
                disqualifications=dq,
                flags=flags,
                data_warnings=list(asset.data_warnings),
            )
        )

    # Ranked first by score, then by market-cap rank as the tie-breaker. Sorting
    # disqualified cards to the end happens in the reporter, so the order here
    # stays meaningful for both groups.
    cards.sort(key=lambda c: (-c.total, c.rank))
    return cards


def ranked(cards: list[ScoreCard]) -> list[ScoreCard]:
    return [c for c in cards if not c.disqualified]


def excluded(cards: list[ScoreCard]) -> list[ScoreCard]:
    return [c for c in cards if c.disqualified]

"""The factor groups: liquidity, momentum, tokenomics, traction, valuation.

Two design rules govern everything in this file.

**Rule 1: a group only counts as far as it has data.** Each group is a weighted
average of its metrics, but the result is then shrunk toward neutral (0.5) in
proportion to how much of the group was actually measurable::

    score = 0.5 + (raw - 0.5) * coverage

Without this, a coin with one available metric scoring well would look like it
had aced the whole group. Shrinking means missing data costs you *confidence*,
not a free pass.

**Rule 2: liquidity uses absolute thresholds, momentum uses relative ones.**
$5M of daily volume is $5M of daily volume regardless of what else is in the
universe, so liquidity is scored against fixed log-scaled bands. Momentum has no
absolute meaning -- a 40% quarterly gain is excellent in a bear market and
mediocre in a bull one -- so it is only ever scored *relative to the universe*,
which happens in :mod:`crypto_advisor.quant.score`, not here.
"""

from __future__ import annotations

from typing import Any

from ..model import Asset, FactorScore
from ..sources.binance import trend_filter
from . import stats


class _Parts:
    """Collects ``(score, weight)`` pairs and tracks how much had data."""

    def __init__(self) -> None:
        self.items: list[tuple[str, float | None, float]] = []
        # Instance-level on purpose. A class-level dict here would be shared by
        # every _Parts ever created and would silently accumulate details
        # across assets.
        self.details: dict[str, str] = {}

    def add(self, name: str, score: float | None, weight: float, detail: str | None = None) -> None:
        self.items.append((name, score, weight))
        if detail is not None:
            self.details[name] = detail

    def resolve(self) -> tuple[float | None, float, dict[str, float | None]]:
        available = [(n, s, w) for n, s, w in self.items if s is not None]
        metrics = {n: s for n, s, _ in self.items}
        if not available:
            return None, 0.0, metrics
        total_weight = sum(w for _, _, w in available)
        raw = sum(s * w for _, s, w in available) / total_weight if total_weight else None
        # Coverage is measured against the group's full weight, not just the
        # available part, so a group that is half missing really does report half.
        full_weight = sum(w for _, _, w in self.items) or 1.0
        coverage = total_weight / full_weight
        return raw, coverage, metrics


def shrink_toward_neutral(raw: float | None, coverage: float) -> float:
    """Pull a partial group toward neutral in proportion to its coverage.

    Public because :mod:`crypto_advisor.quant.score` applies the identical rule
    to the momentum group, and the two must stay consistent.
    """
    if raw is None:
        return 0.5
    return stats.clamp(0.5 + (raw - 0.5) * coverage)


def _log_desc(value: float | None, good: float, bad: float) -> float | None:
    """Log-scaled version of "lower is better" for ratios spanning decades."""
    forward = stats.log_interp(value, good, bad)
    return None if forward is None else 1.0 - forward


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if abs(value) >= threshold:
            return f"${value / threshold:,.1f}{suffix}"
    return f"${value:,.0f}"


def _fmt_pct(value: float | None, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"


# ---------------------------------------------------------------------------
# Liquidity -- "can you get in and out without moving the price?"
# ---------------------------------------------------------------------------


def liquidity(asset: Asset) -> FactorScore:
    parts = _Parts()
    notes: list[str] = []

    volume = asset.median_volume_30d or asset.quote_volume_24h
    parts.add(
        "median_volume_30d",
        stats.log_interp(volume, 1e6, 5e8),
        0.30,
        f"median 30d volume {_fmt_money(volume)}",
    )
    if asset.median_volume_30d:
        notes.append(
            "Volume is the *median* of the last 30 days, not the mean: one "
            "wash-traded spike drags a mean far off."
        )

    depth = asset.book.total_depth_usd if asset.book else None
    parts.add("book_depth_usd", stats.log_interp(depth, 1e5, 2.5e7), 0.25,
              f"order-book depth {_fmt_money(depth)}")

    spread = asset.book.spread_bps if asset.book else None
    parts.add("spread_bps", stats.descending_interp(spread, good=2.0, bad=60.0), 0.20,
              f"spread {spread:.1f} bps" if spread is not None else "spread n/a")

    parts.add(
        "turnover",
        stats.band_score(asset.turnover, low=0.005, high=0.5, fade=1.5),
        0.15,
        f"turnover {_fmt_pct(asset.turnover)} of market cap per day",
    )
    if asset.turnover is not None and asset.turnover > 1.0:
        notes.append(
            f"Turnover of {asset.turnover:.1f}x market cap per day is high enough "
            "to be worth treating as a possible wash-trading signal."
        )

    parts.add(
        "market_cap",
        stats.log_interp(asset.market_cap, 1e8, 5e11),
        0.10,
        f"market cap {_fmt_money(asset.market_cap)}",
    )
    if asset.book is None:
        notes.append("No order-book data, so depth and spread are scored as unknown.")

    raw, coverage, metrics = parts.resolve()
    return FactorScore(
        name="liquidity",
        weight=0.0,  # filled in by the scorer from config
        score=shrink_toward_neutral(raw, coverage),
        coverage=coverage,
        metrics=metrics,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Momentum -- "risk-adjusted trend"
# ---------------------------------------------------------------------------


def momentum_raw(asset: Asset, windows: list[int], risk_free_annual: float) -> dict[str, Any]:
    """Per-asset momentum inputs. Cross-sectional scoring happens in ``score.py``.

    The headline per-window number is a **Sortino ratio over that window**::

        sortino = (window_return - rf_scaled) / (downside_deviation * sqrt(window))

    Note the deliberate absence of annualisation. Annualising a 30-day return
    turns a 1.0 multiple into 10^12 and makes the ordering meaningless; keeping
    the window's own scale means a 30-, 90- and 180-day figure are all
    comparable to each other.
    """
    out: dict[str, Any] = {"windows": {}, "available_windows": 0}
    closes = [b.close for b in asset.bars]
    if len(closes) < 30:
        return out

    for window in windows:
        if len(closes) < window + 1:
            out["windows"][window] = None
            continue
        segment = closes[-(window + 1):]
        total_return = segment[-1] / segment[0] - 1.0
        returns = stats.daily_log_returns(segment)
        downside = stats.downside_deviation(returns)
        rf_scaled = risk_free_annual * (window / 365.0)

        if downside > 0:
            sortino = (total_return - rf_scaled) / (downside * (window ** 0.5))
        else:
            # No down days at all in the window. Rather than divide by zero into
            # an infinite score, cap it at a large finite value; the subsequent
            # cross-sectional clamp means the exact cap does not matter.
            sortino = 10.0 if total_return > 0 else 0.0

        out["windows"][window] = {
            "sortino": sortino,
            "return": total_return,
            "vol_annual": stats.stdev(returns) * (365 ** 0.5),
            "downside_annual": downside * (365 ** 0.5),
        }
        out["available_windows"] += 1

    out["max_drawdown"] = stats.max_drawdown(closes[-365:])
    trend = trend_filter(asset.bars, window=200)
    out["above_200dma"] = trend.get("above")
    out["trend_distance_pct"] = trend.get("distance_pct")
    return out


# ---------------------------------------------------------------------------
# Tokenomics -- "how much future dilution are you exposed to?"
# ---------------------------------------------------------------------------


def tokenomics(asset: Asset) -> FactorScore:
    """The weakest group, and it says so.

    Free APIs do not expose emission schedules, unlock cliffs or vesting
    contracts, so this reduces to two things that *are* computable: how far the
    fully diluted valuation sits above the market cap, and whether supply is
    capped at all. Real tokenomics work needs the vesting spreadsheet, which
    means this group should never be the reason to buy something.
    """
    parts = _Parts()
    notes: list[str] = [
        "Tokenomics is the weakest factor group here. Free APIs expose no "
        "emission schedule or unlock calendar, so this measures dilution risk "
        "only, not supply dynamics."
    ]

    parts.add(
        "fdv_to_mcap",
        stats.descending_interp(asset.fdv_to_mcap, good=1.0, bad=6.0),
        0.75,
        f"FDV / market cap {asset.fdv_to_mcap:.2f}x" if asset.fdv_to_mcap else "FDV n/a",
    )
    if asset.fdv_to_mcap and asset.fdv_to_mcap > 3.0:
        notes.append(
            f"Fully diluted valuation is {asset.fdv_to_mcap:.1f}x the market cap: "
            "most of the eventual supply does not exist yet, so today's holders "
            "face heavy future dilution."
        )

    capped = asset.max_supply is not None and asset.max_supply > 0
    parts.add("supply_cap", 1.0 if capped else 0.3, 0.25,
              "supply is capped" if capped else "supply is uncapped (perpetual issuance)")

    raw, coverage, metrics = parts.resolve()
    return FactorScore(
        name="tokenomics",
        weight=0.0,
        score=shrink_toward_neutral(raw, coverage),
        coverage=coverage,
        metrics=metrics,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Traction -- "is the thing actually used, and does it earn anything?"
# ---------------------------------------------------------------------------


def traction(asset: Asset) -> FactorScore:
    parts = _Parts()
    notes: list[str] = []

    if asset.revenue_yield is not None:
        parts.add(
            "revenue_yield",
            stats.log_interp(asset.revenue_yield, 0.002, 0.15),
            0.35,
            f"annualised revenue is {_fmt_pct(asset.revenue_yield)} of market cap",
        )
    else:
        parts.add("revenue_yield", None, 0.35)

    if asset.revenue_change_7d is not None:
        change = asset.revenue_change_7d
        reading = (
            "revenue collapsed week-over-week (prior week was near zero)"
            if change <= -1.0
            else f"revenue 7d-over-7d {_fmt_pct(change)}"
        )
        parts.add("revenue_change_7d",
                  stats.ascending_interp(change, bad=-0.30, good=0.30),
                  0.20, reading)
    else:
        parts.add("revenue_change_7d", None, 0.20)

    if asset.tvl is not None:
        parts.add("tvl", stats.log_interp(asset.tvl, 1e6, 5e9), 0.15,
                  f"TVL {_fmt_money(asset.tvl)}")
    else:
        parts.add("tvl", None, 0.15)

    parts.add("trades_24h", stats.log_interp(asset.trades_24h, 500, 2e5), 0.20,
              f"{asset.trades_24h:,} trades in 24h")
    if asset.trades_24h and asset.trades_24h < 1_000:
        notes.append(
            "Very few trades per day. Reported volume built from a handful of "
            "prints is weak evidence of real demand."
        )

    if not asset.has_protocol_data:
        notes.append(
            "No DefiLlama protocol match, so this coin has no measurable "
            "revenue or TVL. Traction is scored toward neutral rather than "
            "penalised -- for an asset whose value does not depend on protocol "
            "income the concept does not apply, but it does mean we cannot "
            "verify usage independently."
        )
    elif not asset.has_protocol_financials:
        notes.append(
            f"Matched '{asset.protocol_name}' on DefiLlama, but it reports "
            "neither revenue nor TVL, so traction rests on trading activity alone."
        )
    if asset.tvl:
        notes.append(
            f"TVL is {_fmt_money(asset.tvl)} and is shown for context only: TVL "
            "is heavily double-counted across protocols and is easy to rent."
        )
    if asset.revenue_methodology:
        notes.append(f"Revenue definition (per DefiLlama): {asset.revenue_methodology}")

    raw, coverage, metrics = parts.resolve()
    return FactorScore(
        name="traction",
        weight=0.0,
        score=shrink_toward_neutral(raw, coverage),
        coverage=coverage,
        metrics=metrics,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Valuation -- "are you paying a sane price for that traction?"
# ---------------------------------------------------------------------------


def valuation(asset: Asset) -> FactorScore:
    """Price relative to fees earned.

    Only definable for a protocol that actually earns. There is no honest
    valuation anchor for a coin with no cash flow -- network-value-to-transactions
    needs on-chain volume that these endpoints do not provide, and using
    *exchange* volume as a stand-in would be a category error. So assets without
    revenue score neutral, and the report says why.
    """
    parts = _Parts()
    notes: list[str] = []

    if asset.price_to_fees is not None:
        parts.add("price_to_fees", _log_desc(asset.price_to_fees, good=8.0, bad=250.0), 0.70,
                  f"market cap / annualised revenue = {asset.price_to_fees:.1f}x")
        if asset.price_to_fees > 150:
            notes.append(
                f"Paying {asset.price_to_fees:.0f}x annualised revenue. Growth has "
                "to be exceptional for that to be justified."
            )
    else:
        parts.add("price_to_fees", None, 0.70)
        notes.append(
            "No revenue to value against, so valuation is left at neutral. That "
            "is an absence of evidence, not evidence of cheapness."
        )

    if asset.fdv_to_mcap is not None:
        parts.add("fdv_to_mcap", stats.descending_interp(asset.fdv_to_mcap, good=1.0, bad=5.0),
                  0.30, f"FDV / market cap {asset.fdv_to_mcap:.2f}x")
    else:
        parts.add("fdv_to_mcap", None, 0.30)

    raw, coverage, metrics = parts.resolve()
    return FactorScore(
        name="valuation",
        weight=0.0,
        score=shrink_toward_neutral(raw, coverage),
        coverage=coverage,
        metrics=metrics,
        notes=notes,
    )

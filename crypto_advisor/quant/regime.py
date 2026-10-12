"""Regime filter: how much total exposure, not which coin.

This is where a market-timing view belongs, and it is the only place in the tool
where one is expressed. The reasoning is blunt: ranking coins well is hard,
knowing that the whole market is extended is comparatively easy, and expressing
caution as "hold less of everything" is far more defensible than pretending to
know which coin will fall.

Three inputs:

* **BTC against its 200-day moving average** -- the classic risk-on/risk-off
  switch. Crude, widely watched, and it works well enough as a coarse filter.
* **Fear & Greed** -- used only at the extremes. A reading of 50 is noise; a
  reading of 85 is a reason to be careful, and a reading of 12 is a reason to be
  interested. Applying it in the middle would just add churn.
* **Stablecoin supply** -- rising supply is idle capital on the sidelines.

The output is a single exposure fraction with the reasons attached, so the user
can disagree with it and see exactly what to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..sources import defillama, sentiment
from ..sources.binance import Bar, trend_filter

# Never recommend more than this, whatever the signals say. A tool like this has
# no business suggesting anyone go all in on crypto.
MAX_EXPOSURE = 0.90


@dataclass
class Regime:
    label: str
    exposure: float
    btc_above_200dma: bool | None = None
    btc_trend_distance_pct: float | None = None
    btc_200dma: float | None = None
    fear_greed: int | None = None
    fear_greed_label: str = ""
    fear_greed_avg_30d: float | None = None
    stablecoin_supply_usd: float | None = None
    stablecoin_change_30d: float | None = None
    rationale: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "exposure": self.exposure,
            "btc_above_200dma": self.btc_above_200dma,
            "btc_trend_distance_pct": self.btc_trend_distance_pct,
            "fear_greed": self.fear_greed,
            "fear_greed_label": self.fear_greed_label,
            "stablecoin_change_30d": self.stablecoin_change_30d,
            "rationale": self.rationale,
            "warnings": self.warnings,
        }


def assess(fetcher: Any, cfg: Any, btc_bars: list[Bar]) -> Regime:
    """Build the regime assessment from trend, sentiment and stablecoin supply."""
    reg_cfg = cfg.quant.regime
    rationale: list[str] = []
    warnings: list[str] = []

    # -- 1. trend -------------------------------------------------------------
    trend = {"available": False, "above": None, "distance_pct": None, "ma": None}
    if getattr(reg_cfg, "use_btc_200dma", True):
        trend = trend_filter(btc_bars, window=200)

    if not trend.get("available"):
        exposure = float(reg_cfg.exposure_neutral)
        label = "unknown"
        warnings.append(
            "Not enough BTC history to compute the 200-day average, so the "
            "regime is unknown and neutral exposure is assumed."
        )
        rationale.append(
            f"No trend signal available; defaulting to the neutral exposure of "
            f"{reg_cfg.exposure_neutral:.0%}."
        )
    elif trend["above"]:
        exposure = float(reg_cfg.exposure_neutral)
        label = "risk-on"
        rationale.append(
            f"BTC is {trend['distance_pct']:+.1f}% versus its 200-day average "
            f"(${trend['ma']:,.0f}), which is the risk-on condition."
        )
    else:
        exposure = float(reg_cfg.exposure_risk_off)
        label = "risk-off"
        rationale.append(
            f"BTC is {trend['distance_pct']:+.1f}% versus its 200-day average "
            f"(${trend['ma']:,.0f}), which is the risk-off condition. This is the "
            "single biggest input into total exposure."
        )

    # -- 2. sentiment extremes ------------------------------------------------
    fng = sentiment.fear_greed(fetcher)
    fng_value = fng.get("value") if fng.get("available") else None
    if fng_value is None:
        warnings.append("Fear & Greed index unavailable; sentiment adjustment skipped.")
    else:
        greed_threshold = int(reg_cfg.fear_greed_greed_threshold)
        fear_threshold = int(reg_cfg.fear_greed_fear_threshold)
        if fng_value >= greed_threshold:
            capped = min(exposure, float(reg_cfg.exposure_euphoric))
            if capped < exposure:
                rationale.append(
                    f"Fear & Greed is {fng_value} ({fng.get('classification')}), at or "
                    f"above the greed threshold of {greed_threshold}. Exposure is "
                    "capped: buying euphoria is how most retail money is lost."
                )
            exposure = capped
            label = "euphoric" if label != "risk-off" else "risk-off / euphoric"
        elif fng_value <= fear_threshold:
            raised = max(exposure, float(reg_cfg.exposure_fearful))
            rationale.append(
                f"Fear & Greed is {fng_value} ({fng.get('classification')}), at or "
                f"below the fear threshold of {fear_threshold}. Historically these "
                "readings have been better buying conditions than selling ones, so "
                "the floor on exposure is raised."
            )
            exposure = raised
            if label == "risk-on":
                label = "risk-on / fearful"
        else:
            rationale.append(
                f"Fear & Greed is {fng_value} ({fng.get('classification')}), in the "
                "neutral middle band where the index carries little information, so "
                "no adjustment is applied."
            )

    # -- 3. stablecoin dry powder --------------------------------------------
    trend_data = defillama.stablecoin_supply_trend(fetcher, days=30)
    stable_change = trend_data.get("change_pct") if trend_data.get("available") else None
    if stable_change is None:
        warnings.append("Stablecoin supply trend unavailable; dry-powder input skipped.")
    elif stable_change > 0.03:
        exposure = min(MAX_EXPOSURE, exposure + 0.05)
        rationale.append(
            f"Stablecoin supply grew {stable_change:+.1%} over 30 days, suggesting "
            "capital is waiting on the sidelines rather than having left. Exposure "
            "nudged up by 5 points."
        )
    elif stable_change < -0.03:
        exposure = max(0.0, exposure - 0.05)
        rationale.append(
            f"Stablecoin supply shrank {stable_change:+.1%} over 30 days, which "
            "points to capital leaving the ecosystem rather than waiting in it. "
            "Exposure nudged down by 5 points."
        )
    else:
        rationale.append(
            f"Stablecoin supply was roughly flat ({stable_change:+.1%} over 30 days), "
            "so it adds no signal either way."
        )

    exposure = max(0.0, min(MAX_EXPOSURE, exposure))
    rationale.append(
        f"Final recommended total exposure: {exposure:.0%}. This is a cap on how "
        "much of the portfolio this strategy should occupy, not a target to reach "
        "immediately, and it is the number to argue with first."
    )

    return Regime(
        label=label,
        exposure=exposure,
        btc_above_200dma=trend.get("above"),
        btc_trend_distance_pct=trend.get("distance_pct"),
        btc_200dma=trend.get("ma"),
        fear_greed=fng_value,
        fear_greed_label=str(fng.get("classification") or ""),
        fear_greed_avg_30d=fng.get("avg_30d"),
        stablecoin_supply_usd=trend_data.get("latest_usd"),
        stablecoin_change_30d=stable_change,
        rationale=rationale,
        warnings=warnings,
    )

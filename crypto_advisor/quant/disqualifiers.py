"""Hard disqualifiers and soft risk flags.

The organising belief here: **it is far more reliable to identify what will hurt
you than to identify what will make money.** So the screener is built as a set of
gates that remove assets for concrete, checkable reasons, and only then ranks
whatever survives.

A disqualification is absolute -- the asset is excluded from the ranked shortlist
and the reason is printed. A flag is a warning that does not exclude.

Every gate here maps to a specific way people lose money in this asset class:
illiquidity you cannot exit, a listing too young to have any history, a book too
thin to fill, a spread that eats the trade, a stablecoin masquerading as an
investment, or a protocol that DefiLlama itself has labelled a Ponzi.
"""

from __future__ import annotations

from typing import Any

from ..model import Asset

# DefiLlama category values that mean "this is a scam", not "this is a risk".
# DefiLlama really does publish this label.
FATAL_CATEGORIES = {"ponzi"}

# Categories that are not fatal but are worth naming in the report.
NOTABLE_CATEGORIES = {
    "meme": "classified as a meme coin: no cash flow, value rests entirely on attention",
    "stablecoin issuer": "issues a pegged asset rather than earning from a product",
    "chain": "a layer-1 or layer-2 network: value accrues only if the network is used",
    "cex": "a centralised exchange token: a claim on an off-chain business, not a bearer asset",
    "rwa": "real-world-asset token: check what it is actually backed by and who custodies it",
    "liquid staking": "liquid staking: staking rewards are the yield, which raises the riba question",
    "yield aggregator": "yield aggregator: returns come from lending and liquidity provision, which raises the riba question",
    "lending": "lending protocol: the business model is interest, which raises the riba question",
    "prediction market": "prediction market: betting on outcomes, which raises the maysir question",
    "leveraged farming": "leveraged farming: leverage plus yield farming, gharar and riba together",
    "basis trading": "basis trading: a delta-neutral carry trade, which is riba-adjacent by construction",
    "options": "options venue: derivatives, generally treated as gharar",
    "derivatives": "derivatives venue: generally treated as gharar",
}


def check(asset: Asset, cfg: Any) -> tuple[list[str], list[str]]:
    """Return ``(disqualifications, flags)`` for one asset."""
    dq: list[str] = []
    flags: list[str] = []
    rules = cfg.quant.disqualifiers

    # -- tradability ----------------------------------------------------------
    volume = asset.median_volume_30d or asset.quote_volume_24h
    if volume <= 0:
        dq.append("no usable volume data: cannot assess tradability")
    elif volume < rules.min_daily_volume_usd:
        dq.append(
            f"median daily volume ${volume:,.0f} is below the "
            f"${rules.min_daily_volume_usd:,.0f} floor"
        )

    if asset.market_cap < getattr(rules, "min_market_cap_usd", 0):
        dq.append(
            f"market cap ${asset.market_cap:,.0f} is below the "
            f"${rules.min_market_cap_usd:,.0f} floor"
        )

    if asset.pair is None:
        dq.append("no Binance spot pair, so it cannot be traded through the reference venue")

    if asset.age_days is None:
        flags.append("listing date unknown; age-based checks could not be applied")
    elif asset.age_days < rules.min_listing_age_days:
        dq.append(
            f"listed {asset.age_days} days ago, below the {rules.min_listing_age_days}-day minimum"
        )

    # -- execution cost -------------------------------------------------------
    if asset.book is None:
        flags.append("no order-book snapshot; depth and spread gates could not be applied")
    else:
        if asset.book.total_depth_usd < rules.min_book_depth_usd:
            dq.append(
                f"order-book depth ${asset.book.total_depth_usd:,.0f} within "
                f"{cfg.quant.depth.band_pct:.0%} of mid is below the "
                f"${rules.min_book_depth_usd:,.0f} floor"
            )
        if asset.book.spread_bps > rules.max_spread_bps:
            dq.append(
                f"bid/ask spread {asset.book.spread_bps:.0f} bps exceeds the "
                f"{rules.max_spread_bps:.0f} bp ceiling"
            )

    # -- peg ------------------------------------------------------------------
    if getattr(rules, "exclude_stablecoins", True) and asset.is_stablecoin:
        dq.append("stablecoin or pegged asset: excluded from the investment ranking by config")

    # -- provenance -----------------------------------------------------------
    for category in asset.defillama_categories:
        if category.strip().lower() in FATAL_CATEGORIES:
            dq.append(f"DefiLlama classifies this protocol as '{category}'")

    if not asset.bars or len(asset.bars) < 200:
        flags.append(
            f"only {len(asset.bars)} daily candles available: momentum and "
            "drawdown figures are on a short history"
        )

    # -- soft flags -----------------------------------------------------------
    if asset.turnover is not None and asset.turnover > 1.0:
        flags.append(
            f"turnover of {asset.turnover:.1f}x market cap per day is high enough "
            "to warrant suspicion of wash trading"
        )
    if asset.fdv_to_mcap is not None and asset.fdv_to_mcap > 5.0:
        flags.append(
            f"fully diluted valuation is {asset.fdv_to_mcap:.1f}x market cap: "
            "heavy future dilution ahead"
        )
    if asset.pct_from_ath is not None and asset.pct_from_ath < -95:
        flags.append(
            f"{abs(asset.pct_from_ath):.0f}% below its all-time high: this may be a "
            "broken asset rather than a discount"
        )
    if asset.pct_change_1y is not None and asset.pct_change_1y < -80:
        flags.append(f"down {abs(asset.pct_change_1y):.0f}% over the past year")
    # DefiLlama's change_7dover7d is a ratio, not a bounded percentage: when the
    # prior week was near zero it reports things like -23.8, which renders as a
    # nonsensical "-2382% fell". Only a real fractional decline is quotable.
    change = asset.revenue_change_7d
    if change is not None and change < -0.30:
        if change <= -1.0:
            flags.append(
                "protocol revenue collapsed to almost nothing week-over-week "
                "(the prior week was near zero, so no meaningful percentage applies)"
            )
        else:
            flags.append(f"protocol revenue fell {abs(change):.0%} week-over-week")
    if asset.has_protocol_data and not asset.revenue_annualized:
        flags.append(
            f"matched '{asset.protocol_name}' on DefiLlama but it reports no fee "
            "revenue, so value accrual cannot be verified"
        )

    for category in asset.defillama_categories:
        note = NOTABLE_CATEGORIES.get(category.strip().lower())
        if note:
            flags.append(note)

    if len(asset.chains) > 20:
        flags.append(
            f"deployed across {len(asset.chains)} chains: liquidity is fragmented "
            "and harder to verify"
        )

    return dq, flags

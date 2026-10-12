"""The Markdown digest -- the actual deliverable.

Everything upstream exists to make this file honest. So the layout is chosen to
put the caveats where they cannot be missed rather than at the bottom:

* The framing note is at the top, because a ranked table is the most persuasive
  thing in the document and the least trustworthy.
* Every number carries its data coverage, so a high score built on missing data
  is visibly a high score built on missing data.
* The Sharia section reports disagreement rather than a verdict, and the
  prohibitions that apply to *how you use any coin* are stated once, prominently,
  because they are the findings that actually matter most.
* Disqualified assets are shown, not hidden. A screener that only shows winners
  teaches you nothing about its own judgment.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .model import Asset, ScoreCard
from .sharia import screen as sharia_screen
from .sharia.types import ShariaAssessment, Verdict
from .store import utcnow


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _money(value: float | None) -> str:
    if value is None:
        return "n/a"
    magnitude = abs(value)
    if magnitude >= 1e12:
        return f"${value / 1e12:,.2f}T"
    if magnitude >= 1e9:
        return f"${value / 1e9:,.2f}B"
    if magnitude >= 1e6:
        return f"${value / 1e6:,.2f}M"
    if magnitude >= 1e3:
        return f"${value / 1e3:,.2f}K"
    return f"${value:,.2f}"


def _price(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.2f}"
    return f"${value:,.6f}"


def _pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.{digits}f}%"


def _plain_pct(value: float | None, digits: int = 1) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}%"


def _ratio(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _turnover_pct(value: float | None) -> str:
    """Turnover as a share of market cap traded per day.

    Rendered as a percentage rather than a bare ratio: typical values are
    0.001-0.05, which all collapse to "0.00" as a two-decimal ratio and make
    real liquidity differences invisible.
    """
    if value is None:
        return "n/a"
    return f"{value * 100:.2f}%"


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _bar(score: float, width: int = 10) -> str:
    filled = int(round(max(0.0, min(1.0, score)) * width))
    return "#" * filled + "." * (width - filled)


# ---------------------------------------------------------------------------
# Watchpoints: what would change the view
# ---------------------------------------------------------------------------


def _watchpoints(asset: Asset, card: ScoreCard, cfg: Any) -> list[str]:
    """The specific, checkable conditions that would invalidate the verdict.

    A recommendation without an invalidation condition is not advice, it is a
    slogan. These are derived from the configured thresholds rather than invented,
    so they move when the user moves the settings.
    """
    dq = cfg.quant.disqualifiers
    points: list[str] = []

    floor = float(getattr(dq, "min_daily_volume_usd", 5_000_000))
    volume = asset.median_volume_30d or asset.quote_volume_24h
    if volume and volume < floor * 2:
        points.append(
            f"Liquidity is close to the floor: median daily volume {_money(volume)} "
            f"against a {_money(floor)} minimum. A drop below it disqualifies."
        )

    if asset.book is not None:
        depth = asset.book.total_depth_usd
        min_depth = float(getattr(dq, "min_book_depth_usd", 250_000))
        if depth and depth < min_depth * 2:
            points.append(
                f"Order-book depth within 2x of the floor: {_money(depth)} against "
                f"{_money(min_depth)}. Thinning liquidity would disqualify."
            )
        spread_limit = float(getattr(dq, "max_spread_bps", 25))
        if asset.book.spread_bps and asset.book.spread_bps > spread_limit * 0.6:
            points.append(
                f"Spread is {asset.book.spread_bps:.1f} bps against a "
                f"{spread_limit:.0f} bps limit, so execution costs are already material."
            )

    if asset.fdv_to_mcap and asset.fdv_to_mcap > 2.0:
        points.append(
            f"Dilution risk: fully diluted valuation is {_ratio(asset.fdv_to_mcap)}x "
            f"the market cap, so supply can still expand substantially."
        )

    if asset.age_days is not None:
        minimum = int(getattr(dq, "min_listing_age_days", 365))
        if asset.age_days < minimum * 2:
            points.append(
                f"Track record is short: {asset.age_days} days listed against a "
                f"{minimum}-day minimum. A full cycle has not been observed."
            )

    if asset.pct_from_ath is not None and asset.pct_from_ath < -80:
        points.append(
            f"Down {abs(asset.pct_from_ath):.1f}% from its all-time high. Confirm the "
            "thesis still holds rather than anchoring on the old price."
        )

    if not asset.has_protocol_data:
        points.append(
            "No independent protocol fundamentals were available, so the traction "
            "and valuation factors are largely unmeasured."
        )

    for flag in card.flags[:2]:
        points.append(flag)

    return points


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------


def _header(generated: datetime, regime: Any, run_id: str, cfg: Any, analysed: int) -> list[str]:
    target = int(cfg.general.universe_size)
    scope = (
        f"top {analysed} assets by market cap"
        if analysed < target
        else f"top {target} assets by market cap"
    )
    if analysed < target:
        scope += f" (a run capped at {analysed}, not the full {target})"
    return [
        f"# Crypto research digest - {generated:%Y-%m-%d}",
        "",
        f"*Generated {generated:%Y-%m-%d %H:%M} UTC | run `{run_id}` | "
        f"{scope} on {cfg.general.quote_asset} pairs*",
        "",
        "> **What this is.** A transparent screen over market, order-flow and "
        "protocol data, plus a separate survey of published scholarly positions on "
        "each asset. It does not predict prices and it cannot tell you what to buy.",
        ">",
        "> **What it is not.** Investment advice, and not a fatwa. The quant score "
        "measures how well an asset passes *this* checklist. A high score means "
        "nothing more than that.",
        "",
        "---",
        "",
    ]


def _regime_section(regime: Any) -> list[str]:
    lines = ["## Market conditions", ""]
    if regime is None:
        lines += ["Regime assessment unavailable for this run.", ""]
        return lines

    lines.append(
        f"**Regime: {regime.label}** - suggested maximum crypto exposure "
        f"**{regime.exposure:.0%}** of a portfolio."
    )
    lines.append("")

    rows = [
        ("BTC vs 200-day average", _bin(regime.btc_above_200dma, "above", "below")),
        ("Distance from 200-day", _pct(regime.btc_trend_distance_pct)),
        ("Fear & Greed", f"{regime.fear_greed} ({regime.fear_greed_label})"
            if regime.fear_greed is not None else "n/a"),
        ("Fear & Greed 30d average", _ratio(regime.fear_greed_avg_30d, 1)),
        ("Stablecoin supply 30d change", _pct(regime.stablecoin_change_30d)),
    ]
    lines.append("| Signal | Reading |")
    lines.append("| --- | --- |")
    for label, value in rows:
        lines.append(f"| {_cell(label)} | {_cell(value)} |")
    lines.append("")

    if regime.rationale:
        lines.append("**Why this stance:**")
        lines.append("")
        for item in regime.rationale:
            lines.append(f"- {item}")
        lines.append("")

    if regime.warnings:
        lines.append("**Caveats:**")
        lines.append("")
        for item in regime.warnings:
            lines.append(f"- {item}")
        lines.append("")

    lines.append(
        "Exposure is a ceiling derived from trend and sentiment, not a target. It "
        "gates position size; it never changes the ranking below."
    )
    lines.append("")
    return lines


def _bin(value: Any, yes: str, no: str) -> str:
    if value is None:
        return "unknown"
    return yes if value else no


def _shortlist_table(
    cards: list[ScoreCard],
    assets: dict[str, Asset],
    assessments: dict[str, ShariaAssessment],
    top_n: int,
) -> list[str]:
    lines = [f"## Shortlist - top {min(top_n, len(cards))}", ""]
    if not cards:
        lines += ["No asset passed the disqualification gates this run.", ""]
        return lines

    lines.append(
        "| # | Asset | Score | Confidence | Sharia | 30d | Volume | Depth | Flags |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for position, card in enumerate(cards[:top_n], start=1):
        asset = assets.get(card.symbol)
        assessment = assessments.get(card.symbol)
        sharia = assessment.verdict.value if assessment else "n/a"
        volume = ""
        depth = ""
        change = ""
        if asset is not None:
            volume = _money(asset.median_volume_30d or asset.quote_volume_24h)
            if asset.book is not None and asset.book.total_depth_usd:
                depth = _money(asset.book.total_depth_usd)
            change = _pct(asset.pct_change_30d)
        flags = "; ".join(card.flags[:2]) if card.flags else ""
        lines.append(
            f"| {position} | **{_cell(card.symbol)}** {_cell(card.name)} "
            f"| {card.total:.1f} | {card.confidence} | {_cell(sharia)} "
            f"| {_cell(change)} | {_cell(volume)} | {_cell(depth)} | {_cell(flags)} |"
        )
    lines.append("")
    lines.append(
        "*Score is this tool's own 0-100 composite. Confidence reflects how much "
        "data was actually available; a high score at low confidence means the "
        "ranking is mostly guesswork.*"
    )
    lines.append("")
    return lines


def _factor_table(card: ScoreCard) -> list[str]:
    lines = ["| Factor | Weight | Score | Coverage |", "| --- | --- | --- | --- |"]
    for factor in card.factors:
        lines.append(
            f"| {_cell(factor.name)} | {factor.weight:.0%} "
            f"| {_bar(factor.score)} {factor.score * 100:.0f} "
            f"| {factor.coverage:.0%} |"
        )
    lines.append("")
    return lines


def _asset_detail(
    card: ScoreCard,
    asset: Asset | None,
    assessment: ShariaAssessment | None,
    cfg: Any,
) -> list[str]:
    lines = [f"### {card.symbol} - {card.name}", ""]
    lines.append(
        f"*Market-cap rank {card.rank} | composite {card.total:.1f}/100 | "
        f"confidence {card.confidence} ({card.coverage:.0%} data coverage)*"
    )
    lines.append("")

    if asset is not None:
        lines.append("| Metric | Value |")
        lines.append("| --- | --- |")
        metrics = [
            ("Price", _price(asset.price)),
            ("Market cap", _money(asset.market_cap)),
            ("Fully diluted valuation", _money(asset.fdv)),
            ("FDV / market cap", _ratio(asset.fdv_to_mcap)),
            ("Median daily volume (30d)", _money(asset.median_volume_30d)),
            ("Turnover (volume / mcap)", _turnover_pct(asset.turnover)),
            ("30d / 1y change", f"{_pct(asset.pct_change_30d)} / {_pct(asset.pct_change_1y)}"),
            ("From all-time high", _pct(asset.pct_from_ath)),
            ("Listed", f"{asset.age_days:,} days ago" if asset.age_days else "unknown"),
            ("Protocol revenue (annualised)",
             _money(asset.revenue_annualized) if asset.revenue_annualized else "n/a"),
            ("Market cap / annual revenue", _ratio(asset.price_to_fees, 1)),
            ("Total value locked", _money(asset.tvl) if asset.tvl else "n/a"),
        ]
        if asset.book is not None:
            metrics.append(("Order-book depth, 2% band", _money(asset.book.total_depth_usd)))
            metrics.append(("Spread", f"{asset.book.spread_bps:.1f} bps"))
            metrics.append(("Book imbalance", _ratio(asset.book.imbalance)))
        for label, value in metrics:
            lines.append(f"| {_cell(label)} | {_cell(value)} |")
        lines.append("")

    lines.append("**Factor breakdown**")
    lines.append("")
    lines.extend(_factor_table(card))

    notes = [
        note
        for factor in card.factors
        for note in factor.notes
    ]
    if notes:
        lines.append("**Notable readings**")
        lines.append("")
        for note in notes[:8]:
            lines.append(f"- {note}")
        lines.append("")

    if asset is not None:
        watchpoints = _watchpoints(asset, card, cfg)
        if watchpoints:
            lines.append("**What would change this view**")
            lines.append("")
            for point in watchpoints:
                lines.append(f"- {point}")
            lines.append("")

    if asset is not None and asset.data_warnings:
        lines.append("**Data warnings**")
        lines.append("")
        for warning in asset.data_warnings:
            lines.append(f"- {warning}")
        lines.append("")

    if assessment is not None:
        lines.extend(_asset_sharia(assessment))

    lines.append("---")
    lines.append("")
    return lines


def _asset_sharia(assessment: ShariaAssessment) -> list[str]:
    lines = [f"**Sharia screen: {assessment.verdict.label}** "
             f"*(confidence: {assessment.confidence})*", ""]
    lines.append(f"- Asset class as classified: {assessment.asset_class}")

    if assessment.positions:
        lines.append("- Published positions found:")
        lines.append("")
        for position in assessment.positions:
            lines.append(
                f"  - **{_cell(position.who)}** ({position.stance.value}): "
                f"{position.summary}"
            )
        lines.append("")
    else:
        lines.append(
            "- No curated scholarly position covers this asset; the result rests on "
            "the rule engine alone."
        )
        lines.append("")

    if assessment.rule_hits:
        lines.append("- Concerns triggered by the rule engine:")
        lines.append("")
        for hit in assessment.rule_hits:
            lines.append(
                f"  - `{hit.rule_id}` **{hit.label}** ({hit.concern}, {hit.severity})"
            )
        lines.append("")

    if assessment.purification_note:
        lines.append(f"- Purification: {assessment.purification_note}")
        lines.append("")

    if assessment.open_questions:
        lines.append("- Questions to put to a qualified scholar:")
        lines.append("")
        for question in assessment.open_questions:
            lines.append(f"  - {question}")
        lines.append("")

    if assessment.sources:
        lines.append("- Sources: " + "; ".join(s.as_markdown() for s in assessment.sources))
        lines.append("")

    return lines


def _sharia_section(
    cards: list[ScoreCard], assessments: dict[str, ShariaAssessment], top_n: int
) -> list[str]:
    lines = ["## Sharia screening", ""]
    lines.append(
        "> There is **no scholarly consensus** on cryptocurrency, and AAOIFI has "
        "issued **no final standard** on it. This section reports what named "
        "scholars and bodies have published and applies transparent rules. It does "
        "not rule, and it is not a fatwa."
    )
    lines.append("")

    # -- the prohibitions that apply to every asset ---------------------------
    lines.append("### Applies to every asset, regardless of which coin")
    lines.append("")
    lines.append(
        "These are the findings that matter most, and they concern *how* you use "
        "crypto rather than *which* coin you hold:"
    )
    lines.append("")
    for rule in sharia_screen.usage_rules():
        lines.append(f"**{rule['label']}** (`{rule['id']}`, {rule['concern']}, "
                     f"{rule['severity']})")
        lines.append("")
        lines.append(rule["detail"])
        lines.append("")

    # -- the landscape --------------------------------------------------------
    landscape = sharia_screen.landscape()
    lines.append("### Where the authorities stand")
    lines.append("")
    lines.append(landscape["headline"])
    lines.append("")
    for position in landscape["positions"]:
        links = ", ".join(f"[source]({url})" for url in position["sources"][:3])
        lines.append(f"- **{_cell(position['who'])}** ({position['stance']}): "
                     f"{position['summary']} {links}")
    lines.append("")

    # -- per-asset verdicts ---------------------------------------------------
    lines.append(f"### Verdicts for the shortlist")
    lines.append("")
    lines.append("| Asset | Classification | Screen result | Concerns |")
    lines.append("| --- | --- | --- | --- |")
    for card in cards[:top_n]:
        assessment = assessments.get(card.symbol)
        if assessment is None:
            continue
        concerns = ", ".join(assessment.concerns) if assessment.concerns else "-"
        lines.append(
            f"| **{_cell(card.symbol)}** | {_cell(assessment.asset_class)} "
            f"| {_cell(assessment.verdict.value)} | {_cell(concerns)} |"
        )
    lines.append("")

    disputed = [
        a for a in assessments.values()
        if a.verdict is Verdict.DISPUTED and a.symbol in {c.symbol for c in cards[:top_n]}
    ]
    if disputed:
        lines.append(
            "Every coin above is disputed or worse under at least one recognised "
            "position. None of them is a settled matter. If you need a single "
            "answer, that is a question for a scholar who can consider your "
            "circumstances, not for a program."
        )
        lines.append("")

    # -- what standard does and does not exist --------------------------------
    standards = sharia_screen.standards_note()
    lines.append("### A note on standards, so nobody misquotes one")
    lines.append("")
    lines.append(standards["note"])
    lines.append("")
    thresholds = standards["equity_analogy_thresholds"]
    lines.append(
        f"For reference, the equity thresholds from "
        f"[AAOIFI Shari'a Standard No. 21]({thresholds['source']}) are: "
        f"interest-bearing debt under {thresholds['interest_bearing_debt_pct_of_market_cap']:.0f}% "
        f"of market cap, interest-bearing securities under "
        f"{thresholds['interest_bearing_securities_pct_of_market_cap']:.0f}%, and "
        f"non-permissible income under "
        f"{thresholds['non_permissible_income_pct_of_revenue']:.0f}% of revenue. "
        "These were written for shares. Applying them to tokens is an analogy, and "
        "this tool does not present analogies as standards."
    )
    lines.append("")
    lines.append(f"*{standards['verification_note']}*")
    lines.append("")
    return lines


def _disqualified_section(
    cards: list[ScoreCard], assets: dict[str, Asset], cfg: Any
) -> list[str]:
    if not bool(getattr(cfg.report, "show_disqualified", True)):
        return []
    limit = int(getattr(cfg.report, "max_disqualified_shown", 15))
    lines = ["## Screened out", ""]
    if not cards:
        lines += ["Nothing was excluded by the hard gates this run.", ""]
        return lines

    lines.append(
        "Shown deliberately. A screen you cannot audit is a screen you cannot "
        "trust, and knowing what was rejected is as informative as the shortlist."
    )
    lines.append("")
    lines.append("| Asset | Score | Reason |")
    lines.append("| --- | --- | --- |")
    for card in cards[:limit]:
        reason = "; ".join(card.disqualifications) or "n/a"
        lines.append(f"| **{_cell(card.symbol)}** {_cell(card.name)} "
                     f"| {card.total:.1f} | {_cell(reason)} |")
    lines.append("")
    if len(cards) > limit:
        lines.append(f"*{len(cards) - limit} further assets were excluded; see the JSON output for all of them.*")
        lines.append("")
    return lines


def _quality_section(
    selection: Any, assets: list[Asset], fetcher: Any, cfg: Any
) -> list[str]:
    from . import universe

    lines = ["## Data quality", ""]
    coverage = universe.summarise(assets) if assets else {}
    if coverage:
        rows = [
            ("Assets analysed", f"{coverage.get('assets', 0):,}"),
            ("With order-book data", f"{coverage.get('with_book', 0):,}"),
            ("With 200+ days of price history", f"{coverage.get('with_bars', 0):,}"),
            ("With a protocol match", f"{coverage.get('with_protocol', 0):,}"),
            ("With revenue or TVL figures",
             f"{coverage.get('with_protocol_financials', 0):,}"),
            ("With revenue data", f"{coverage.get('with_revenue', 0):,}"),
            ("With a diluted-valuation figure", f"{coverage.get('with_fdv', 0):,}"),
            ("With a listing date", f"{coverage.get('with_age', 0):,}"),
            ("Revenue coverage", _plain_pct(coverage.get("pct_with_revenue"))),
        ]
        lines.append("| Measure | Count |")
        lines.append("| --- | --- |")
        for label, value in rows:
            lines.append(f"| {_cell(label)} | {_cell(value)} |")
        lines.append("")

    if selection is not None and getattr(selection, "matched_protocols", 0):
        total = max(1, len(assets))
        lines.append(
            f"- Protocol fundamentals were matched for {selection.matched_protocols} "
            f"of {total} assets, of which {selection.high_confidence_matches} were "
            "high-confidence matches on both ticker and name."
        )
        low = getattr(selection, "low_confidence_matches", 0)
        if low:
            lines.append(
                f"- {low} of those rested on the ticker alone and are marked as "
                "low-confidence in the per-asset warnings. A ticker is not a unique "
                "identifier, so those figures may belong to a different protocol."
            )
        lines.append("")

    if fetcher is not None and getattr(fetcher, "warnings", None):
        lines.append("**Fetch warnings**")
        lines.append("")
        for warning in fetcher.warnings[:12]:
            lines.append(f"- {warning}")
        lines.append("")

    stats = getattr(fetcher, "stats", None)
    if stats is not None:
        lines.append("```")
        lines.append(stats.line())
        lines.append("```")
        lines.append("")
    return lines


def _method_section(cfg: Any) -> list[str]:
    lines = ["## Method", ""]
    lines.append("### Data sources")
    lines.append("")
    lines.append(
        "- **CoinPaprika** - market caps, ranks and prices. Chosen because it "
        "returns the whole market in a single unmetered call, where CoinGecko's "
        "free tier rate-limits after a handful of requests."
    )
    lines.append(
        "- **Binance** - OHLCV history, live order books and 24h tickers. The "
        "exchange is the only source of what liquidity actually looks like, as "
        "opposed to what a market-cap aggregator reports."
    )
    lines.append(
        "- **DefiLlama** - protocol revenue, TVL, categories and stablecoin data. "
        "The `category` field is the independent classification the Sharia sector "
        "screen depends on, precisely because it is not written by the projects."
    )
    lines.append("- **alternative.me** - the Fear & Greed index, used only for regime sizing.")
    lines.append("")

    lines.append("### The six factor groups")
    lines.append("")
    weights = cfg.quant.weights.as_dict()
    descriptions = {
        "liquidity": "Order-book depth, spread and turnover. Depth is measured "
                     "within a 2% price band, because slippage is what you actually pay.",
        "momentum": "Risk-adjusted returns across 30/90/180-day windows, z-scored "
                    "against the peer set and clipped so one outlier cannot dominate.",
        "tokenomics": "Dilution, float and supply schedule. FDV versus market cap is "
                      "the most-missed risk in token investing.",
        "traction": "Whether the protocol earns real revenue, and how that revenue "
                    "is trending.",
        "valuation": "Revenue multiple and revenue yield, against the peer set.",
    }
    lines.append("| Group | Weight | What it measures |")
    lines.append("| --- | --- | --- |")
    for name in ("liquidity", "momentum", "tokenomics", "traction", "valuation"):
        lines.append(
            f"| {name} | {weights.get(name, 0):.0%} | {_cell(descriptions.get(name, ''))} |"
        )
    lines.append("")
    lines.append(
        "Regime is deliberately **not** a factor. Market conditions should change "
        "how much you hold, not which asset you pick, and blending the two produces "
        "a score that rises in a bull market for reasons unrelated to the asset."
    )
    lines.append("")

    lines.append("### Hard disqualifiers")
    lines.append("")
    dq = cfg.quant.disqualifiers
    lines.append("| Gate | Threshold |")
    lines.append("| --- | --- |")
    lines.append(f"| Median daily volume | under {_money(float(dq.min_daily_volume_usd))} |")
    lines.append(f"| Market cap | under {_money(float(dq.min_market_cap_usd))} |")
    lines.append(f"| Order-book depth | under {_money(float(dq.min_book_depth_usd))} |")
    lines.append(f"| Bid-ask spread | over {dq.max_spread_bps:.0f} bps |")
    lines.append(f"| Listing age | under {dq.min_listing_age_days} days |")
    lines.append(f"| Stablecoins | {'excluded' if dq.exclude_stablecoins else 'included'} |")
    lines.append("")

    lines.append("### Known limitations, stated up front")
    lines.append("")
    lines.append(
        "- **Survivorship bias.** Market-cap aggregators list coins that survived. "
        "The thousands that went to zero are largely absent, so the universe is "
        "optimistically selected by construction."
    )
    lines.append(
        "- **Volume can be faked.** Wash trading inflates reported volume on thinly "
        "supervised venues. The tool uses median rather than mean volume, measures "
        "order-book depth directly on Binance, and treats turnover far above 1.0 on "
        "a small cap as a warning rather than a strength."
    )
    lines.append(
        "- **TVL is gameable and double-counted.** Deposits can be recycled across "
        "protocols and counted twice. It is reported, but it is not the traction "
        "measure that matters; revenue is."
    )
    lines.append(
        "- **No forward signal exists.** Nothing here predicts returns. The factors "
        "measure the quality and tradability of what is already visible."
    )
    lines.append(
        "- **Overfitting is the default failure mode** of this kind of tool. The "
        "weights in `config.toml` are judgement calls, not fitted parameters, and "
        "should be treated as such."
    )
    lines.append(
        "- **Professionals lose to the market anyway.** A tool that ranks coins "
        "does not change the difficulty of picking winners, which is why the report "
        "emphasises risk and position sizing over selection."
    )
    lines.append("")
    return lines


def _disclaimer_section() -> list[str]:
    return [
        "## Disclaimer",
        "",
        "This digest is research output from a program you run yourself. It is not "
        "investment advice, and it is not a fatwa. The Sharia section reports "
        "published positions with citations and applies transparent rules; it does "
        "not issue a religious ruling, and reasonable scholars disagree with parts "
        "of it.",
        "",
        "Crypto assets are volatile, sometimes fraudulent, and can lose all their "
        "value. Nothing here is a recommendation to buy or sell anything. Verify "
        "every figure against a primary source before acting on it.",
        "",
        "For religious questions about your own circumstances, ask a qualified "
        "scholar. For financial decisions, consider whether you can afford to lose "
        "the money entirely.",
        "",
    ]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build(
    cfg: Any,
    *,
    assets: list[Asset],
    cards: list[ScoreCard],
    assessments: dict[str, ShariaAssessment],
    regime: Any = None,
    selection: Any = None,
    fetcher: Any = None,
    run_id: str = "",
    generated: datetime | None = None,
) -> str:
    """Render the whole digest as Markdown."""
    generated = generated or utcnow()
    by_symbol = {a.symbol.upper(): a for a in assets}
    top_n = int(getattr(cfg.report, "top_n", 12))
    active = [c for c in cards if not c.disqualified]
    excluded = [c for c in cards if c.disqualified]

    lines: list[str] = []
    lines.extend(_header(generated, regime, run_id, cfg, len(assets)))
    lines.extend(_regime_section(regime))
    lines.extend(_shortlist_table(active, by_symbol, assessments, top_n))

    if active:
        lines.append("## Shortlist detail")
        lines.append("")
        for card in active[:top_n]:
            lines.extend(
                _asset_detail(
                    card,
                    by_symbol.get(card.symbol),
                    assessments.get(card.symbol),
                    cfg,
                )
            )

    lines.extend(_sharia_section(active, assessments, top_n))
    lines.extend(_disqualified_section(excluded, by_symbol, cfg))
    lines.extend(_quality_section(selection, assets, fetcher, cfg))
    lines.extend(_method_section(cfg))
    lines.extend(_disclaimer_section())

    return "\n".join(lines).rstrip() + "\n"

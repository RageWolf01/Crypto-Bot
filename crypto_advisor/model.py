"""The shared vocabulary: one ``Asset`` flowing through quant, Sharia and report.

Quant, Sharia and reporting all need to talk about the same coin without
importing each other, so the data shapes live here and everything else depends
on this module only.

An ``Asset`` is deliberately a *bundle of what we managed to fetch*, not a
promise that every field exists. Most fields are optional because most coins
are missing most data, and pretending otherwise is how a screener starts
fabricating confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .sources.binance import Bar, Book


@dataclass
class Asset:
    """One candidate coin, joined across sources."""

    # -- identity -------------------------------------------------------------
    symbol: str
    name: str
    rank: int

    # -- market data (CoinPaprika, the primary source) ------------------------
    price: float
    market_cap: float
    total_supply: float | None = None
    max_supply: float | None = None
    pct_from_ath: float | None = None
    pct_change_7d: float | None = None
    pct_change_30d: float | None = None
    pct_change_1y: float | None = None
    beta: float | None = None
    first_data_at: str | None = None

    # -- Binance order-flow ---------------------------------------------------
    pair: str | None = None
    quote_volume_24h: float = 0.0
    median_volume_30d: float = 0.0
    trades_24h: int = 0
    book: Book | None = None
    bars: list[Bar] = field(default_factory=list)

    # -- DefiLlama fundamentals ----------------------------------------------
    defillama_categories: list[str] = field(default_factory=list)
    revenue_24h: float | None = None
    revenue_30d: float | None = None
    revenue_annualized: float | None = None
    revenue_change_7d: float | None = None
    revenue_methodology: str | None = None
    tvl: float | None = None
    protocol_name: str | None = None
    chains: list[str] = field(default_factory=list)

    # -- stablecoin metadata (DefiLlama) -------------------------------------
    is_stablecoin: bool = False
    stablecoin: dict[str, Any] | None = None

    # -- provenance -----------------------------------------------------------
    age_days: int | None = None
    data_warnings: list[str] = field(default_factory=list)

    # -- derived --------------------------------------------------------------

    @property
    def circulating_supply(self) -> float | None:
        """Implied circulating supply, from market cap divided by price.

        Both inputs come from CoinPaprika, so this is self-consistent. It is the
        honest way to get a float figure when the free tier will not hand one
        over directly.
        """
        if self.price and self.price > 0 and self.market_cap > 0:
            return self.market_cap / self.price
        return None

    @property
    def fdv(self) -> float | None:
        """Fully diluted valuation: every possible token valued at today's price."""
        if self.max_supply and self.price > 0:
            return self.max_supply * self.price
        return None

    @property
    def fdv_to_mcap(self) -> float | None:
        """How much future dilution you are exposed to. 1.0 means fully diluted.

        A value of 5.0 means only a fifth of the eventual supply exists today, so
        you are buying something whose supply can grow fivefold. That is the
        single most-missed risk in token investing.
        """
        if not self.fdv or self.market_cap <= 0:
            return None
        return self.fdv / self.market_cap

    @property
    def float_ratio(self) -> float | None:
        circ = self.circulating_supply
        if not circ or not self.max_supply or self.max_supply <= 0:
            return None
        return min(1.0, circ / self.max_supply)

    @property
    def turnover(self) -> float | None:
        """Daily exchange volume divided by market cap.

        Roughly: what fraction of the asset changes hands per day. Sustained
        values far above ~1.0 on a small cap usually mean wash trading rather
        than genuine interest.
        """
        if not self.market_cap or self.market_cap <= 0:
            return None
        return self.median_volume_30d / self.market_cap

    @property
    def price_to_fees(self) -> float | None:
        """Market cap divided by annualised protocol revenue."""
        if not self.market_cap or not self.revenue_annualized or self.revenue_annualized <= 0:
            return None
        return self.market_cap / self.revenue_annualized

    @property
    def revenue_yield(self) -> float | None:
        """Annualised protocol revenue as a fraction of market cap."""
        p2f = self.price_to_fees
        return (1.0 / p2f) if p2f else None

    @property
    def has_protocol_data(self) -> bool:
        """Whether an independent protocol record was attached at all.

        Deliberately separate from whether that record contained any *numbers*:
        plenty of protocols are listed on DefiLlama with neither revenue nor TVL,
        and conflating the two made the report's coverage counts disagree with
        each other.
        """
        return self.protocol_name is not None

    @property
    def has_protocol_financials(self) -> bool:
        """Whether the matched protocol reported any revenue or TVL figure."""
        return self.revenue_annualized is not None or self.tvl is not None

    def warn(self, message: str) -> None:
        if message not in self.data_warnings:
            self.data_warnings.append(message)


@dataclass
class FactorScore:
    """One factor group's contribution, with its own provenance."""

    name: str
    weight: float
    score: float                      # 0.0 - 1.0
    coverage: float                   # fraction of the group's metrics that had data
    metrics: dict[str, float | None] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    @property
    def weighted(self) -> float:
        return self.weight * self.score


@dataclass
class ScoreCard:
    """The full quant verdict on one asset."""

    symbol: str
    name: str
    rank: int
    total: float                                  # 0 - 100
    factors: list[FactorScore] = field(default_factory=list)
    disqualified: bool = False
    disqualifications: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    data_warnings: list[str] = field(default_factory=list)

    @property
    def coverage(self) -> float:
        """Weighted data coverage. Low coverage means a low-confidence score."""
        if not self.factors:
            return 0.0
        total_weight = sum(f.weight for f in self.factors) or 1.0
        return sum(f.weight * f.coverage for f in self.factors) / total_weight

    @property
    def confidence(self) -> str:
        """A blunt label. A score built on missing data should not look solid."""
        c = self.coverage
        if c >= 0.85:
            return "high"
        if c >= 0.6:
            return "medium"
        if c >= 0.35:
            return "low"
        return "very low"

    def factor(self, name: str) -> FactorScore | None:
        for f in self.factors:
            if f.name == name:
                return f
        return None

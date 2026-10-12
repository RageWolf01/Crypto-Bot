"""CoinPaprika: market caps, ranks and supply.

Used instead of CoinGecko deliberately. A single request returns ~2000 coins
with market cap, rank, supply and ATH distance, on an unmetered endpoint. The
CoinGecko free tier throttled a rapid probe into a hard 429 after about eight
calls, which makes it unusable on the critical path -- it is kept only as
optional enrichment.

Supply fields deserve a caveat: ``total_supply`` is what the *project* reports
and is not the same as circulating supply. Float-ratio calculations below are
therefore labelled as estimates everywhere they surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

BASE = "https://api.coinpaprika.com/v1"
TTL_TICKERS = 3_600


@dataclass(frozen=True)
class MarketCap:
    coin_id: str
    symbol: str
    name: str
    rank: int
    price: float
    market_cap: float
    volume_24h: float
    total_supply: float | None
    max_supply: float | None
    ath_price: float | None
    pct_from_ath: float | None
    pct_change_7d: float | None
    pct_change_30d: float | None
    pct_change_1y: float | None
    beta: float | None
    first_data_at: str | None

    @property
    def float_ratio(self) -> float | None:
        """Estimated circulating/total ratio proxy, from total_supply/max_supply.

        A low value implies a large share of supply is not yet in circulation,
        which usually means future dilution. This is a rough proxy, not a real
        float calculation, because ``total_supply`` is self-reported.
        """
        if not self.max_supply or not self.total_supply:
            return None
        if self.max_supply <= 0:
            return None
        return min(1.0, self.total_supply / self.max_supply)


def tickers(fetcher: Any) -> dict[str, MarketCap]:
    """All coins, keyed by uppercase symbol.

    Symbols are not unique across projects, so when several coins share a
    ticker the one with the best (lowest) rank wins -- that is almost always
    the canonical asset rather than a wrapped or fork derivative.
    """
    raw = fetcher.get_json(
        f"{BASE}/tickers",
        provider="coinpaprika",
        ttl=TTL_TICKERS,
        cache_key="coinpaprika:tickers",
    )
    out: dict[str, MarketCap] = {}
    for row in raw or []:
        try:
            usd = (row.get("quotes") or {}).get("USD") or {}
            symbol = (row.get("symbol") or "").upper().strip()
            if not symbol:
                continue
            rank = row.get("rank")
            entry = MarketCap(
                coin_id=row.get("id") or "",
                symbol=symbol,
                name=row.get("name") or symbol,
                rank=int(rank) if isinstance(rank, (int, float)) else 10_000,
                price=_f(usd.get("price")),
                market_cap=_f(usd.get("market_cap")),
                volume_24h=_f(usd.get("volume_24h")),
                total_supply=_f(row.get("total_supply")),
                max_supply=_f(row.get("max_supply")),
                ath_price=_f(usd.get("ath_price")),
                pct_from_ath=_f(usd.get("percent_from_price_ath")),
                pct_change_7d=_f(usd.get("percent_change_7d")),
                pct_change_30d=_f(usd.get("percent_change_30d")),
                pct_change_1y=_f(usd.get("percent_change_1y")),
                beta=_f(row.get("beta_value")),
                first_data_at=row.get("first_data_at"),
            )
            existing = out.get(symbol)
            if existing is None or entry.rank < existing.rank:
                out[symbol] = entry
        except (TypeError, ValueError, AttributeError):
            continue
    return out


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result


def global_row(caps: dict[str, MarketCap]) -> dict[str, Any]:
    """A few aggregate numbers for the report header."""
    ranked = [c for c in caps.values() if c.market_cap > 0]
    total = sum(c.market_cap for c in ranked)
    top10 = sorted(ranked, key=lambda c: -c.market_cap)[:10]
    btc = caps.get("BTC")
    eth = caps.get("ETH")
    return {
        "total_market_cap": total,
        "coins_tracked": len(ranked),
        "top10_share": (sum(c.market_cap for c in top10) / total) if total else None,
        "btc_dominance": (btc.market_cap / total) if (btc and total) else None,
        "eth_dominance": (eth.market_cap / total) if (eth and total) else None,
    }

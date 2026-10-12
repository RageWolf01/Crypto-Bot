"""Binance public API: the primary market-data source.

Chosen deliberately. The public endpoints need no API key, are not throttled
the way CoinGecko's free tier is, and give something the aggregators do not:
the *real* order book. That matters because reported 24h volume is trivially
inflated, whereas the actual bid/ask ladder is expensive to fake.

Endpoints used:

* ``/api/v3/exchangeInfo``  -- which pairs exist and are tradable
* ``/api/v3/ticker/24hr``   -- volume and last price for *every* pair in one call
* ``/api/v3/klines``        -- real OHLCV history (daily)
* ``/api/v3/depth``         -- order-book ladder, for genuine liquidity
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

BASE = "https://api.binance.com"

# Listing dates never change, so cache them for a month.
TTL_LISTING = 2_592_000
TTL_EXCHANGE_INFO = 86_400
TTL_TICKER = 900
TTL_KLINES = 3_600
TTL_DEPTH = 900


@dataclass(frozen=True)
class Pair:
    symbol: str
    base: str
    quote: str

    @property
    def display(self) -> str:
        return self.base


@dataclass(frozen=True)
class Ticker:
    symbol: str
    last_price: float
    quote_volume: float   # 24h volume denominated in the quote asset (USDT)
    base_volume: float
    trades: int
    high: float
    low: float
    open_price: float

    @property
    def change_pct(self) -> float:
        if self.open_price <= 0:
            return 0.0
        return (self.last_price / self.open_price - 1.0) * 100.0


@dataclass(frozen=True)
class Bar:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int


@dataclass
class Book:
    symbol: str
    best_bid: float
    best_ask: float
    bid_depth_usd: float
    ask_depth_usd: float
    spread_bps: float
    mid: float
    levels: int

    @property
    def total_depth_usd(self) -> float:
        return self.bid_depth_usd + self.ask_depth_usd

    @property
    def imbalance(self) -> float:
        """Positive means more resting bids than asks (mild buy pressure)."""
        total = self.total_depth_usd
        if total <= 0:
            return 0.0
        return (self.bid_depth_usd - self.ask_depth_usd) / total


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------


def spot_pairs(fetcher: Any, quote: str = "USDT") -> dict[str, Pair]:
    """All tradable spot pairs against ``quote``, keyed by symbol."""
    data = fetcher.get_json(
        f"{BASE}/api/v3/exchangeInfo",
        provider="binance",
        ttl=TTL_EXCHANGE_INFO,
        cache_key="binance:exchangeInfo",
    )
    out: dict[str, Pair] = {}
    for sym in data.get("symbols", []):
        if (
            sym.get("quoteAsset") == quote
            and sym.get("status") == "TRADING"
            and sym.get("isSpotTradingAllowed", True)
        ):
            out[sym["symbol"]] = Pair(
                symbol=sym["symbol"], base=sym["baseAsset"], quote=sym["quoteAsset"]
            )
    return out


def tickers_24h(fetcher: Any) -> dict[str, Ticker]:
    """24h stats for every pair in a single request.

    This is the reason Binance is the primary source: one call covers the whole
    market, instead of one call per coin.
    """
    data = fetcher.get_json(
        f"{BASE}/api/v3/ticker/24hr",
        provider="binance",
        ttl=TTL_TICKER,
        cache_key="binance:ticker24h",
    )
    out: dict[str, Ticker] = {}
    for row in data:
        try:
            out[row["symbol"]] = Ticker(
                symbol=row["symbol"],
                last_price=float(row["lastPrice"]),
                quote_volume=float(row["quoteVolume"]),
                base_volume=float(row["volume"]),
                trades=int(row["count"]),
                high=float(row["highPrice"]),
                low=float(row["lowPrice"]),
                open_price=float(row["openPrice"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def klines_daily(fetcher: Any, symbol: str, limit: int = 1000) -> list[Bar]:
    """Daily candles, oldest first.

    Binance currently returns at most ~1000 daily bars, which is roughly 2.7
    years -- comfortably more than the longest momentum window used here.
    """
    raw = fetcher.get_json(
        f"{BASE}/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}",
        provider="binance",
        ttl=TTL_KLINES,
        cache_key=f"binance:klines1d:{symbol}:{limit}",
    )
    bars: list[Bar] = []
    for row in raw:
        try:
            bars.append(
                Bar(
                    ts=datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    quote_volume=float(row[7]),
                    trades=int(row[8]),
                )
            )
        except (IndexError, TypeError, ValueError):
            continue
    return bars


def listing_date(fetcher: Any, symbol: str) -> date | None:
    """Approximate first-trade date, via the earliest available daily candle.

    Asking for ``startTime=0&limit=1`` makes Binance return just the first bar
    it holds, which is a good proxy for the spot listing date.
    """
    try:
        raw = fetcher.get_json(
            f"{BASE}/api/v3/klines?symbol={symbol}&interval=1d&startTime=0&limit=1",
            provider="binance",
            ttl=TTL_LISTING,
            cache_key=f"binance:firstbar:{symbol}",
        )
    except Exception:
        return None
    if not raw:
        return None
    try:
        return datetime.fromtimestamp(raw[0][0] / 1000, tz=timezone.utc).date()
    except (IndexError, TypeError, ValueError):
        return None


def depth(fetcher: Any, symbol: str, levels: int = 500, band_pct: float = 0.02) -> Book | None:
    """Order-book ladder reduced to depth-within-band and spread.

    ``levels`` is capped at 5000 by Binance; weight scales with it, so 500 is a
    good balance between fidelity and rate-limit cost.
    """
    levels = max(5, min(5000, int(levels)))
    try:
        data = fetcher.get_json(
            f"{BASE}/api/v3/depth?symbol={symbol}&limit={levels}",
            provider="binance",
            ttl=TTL_DEPTH,
            cache_key=f"binance:depth:{symbol}:{levels}",
        )
    except Exception:
        return None
    try:
        bids = [(float(p), float(q)) for p, q in data.get("bids", [])]
        asks = [(float(p), float(q)) for p, q in data.get("asks", [])]
    except (TypeError, ValueError):
        return None
    if not bids or not asks:
        return None
    return book_metrics(symbol, bids, asks, band_pct=band_pct, levels=len(bids))


def book_metrics(
    symbol: str,
    bids: Iterable[tuple[float, float]],
    asks: Iterable[tuple[float, float]],
    *,
    band_pct: float = 0.02,
    levels: int = 0,
) -> Book:
    """Compute depth within ``band_pct`` of mid, plus spread in basis points."""
    bids = list(bids)
    asks = list(asks)
    best_bid = max(p for p, _ in bids)
    best_ask = min(p for p, _ in asks)
    mid = (best_bid + best_ask) / 2.0
    spread_bps = ((best_ask - best_bid) / mid * 10_000.0) if mid > 0 else float("inf")

    floor = mid * (1 - band_pct)
    ceiling = mid * (1 + band_pct)
    bid_depth = sum(p * q for p, q in bids if p >= floor)
    ask_depth = sum(p * q for p, q in asks if p <= ceiling)

    return Book(
        symbol=symbol,
        best_bid=best_bid,
        best_ask=best_ask,
        bid_depth_usd=bid_depth,
        ask_depth_usd=ask_depth,
        spread_bps=spread_bps,
        mid=mid,
        levels=levels or len(bids),
    )


# ---------------------------------------------------------------------------
# Small helpers used by the pipeline
# ---------------------------------------------------------------------------


def age_days(listed: date | None, *, today: date | None = None) -> int | None:
    if listed is None:
        return None
    today = today or datetime.now(timezone.utc).date()
    return max(0, (today - listed).days)


def median_daily_quote_volume(bars: list[Bar], window: int = 30) -> float:
    """Median (not mean) of recent daily quote volume.

    Medians are used deliberately: a single wash-traded spike drags a mean far
    off and makes an illiquid pair look deep.
    """
    if not bars:
        return 0.0
    recent = bars[-window:]
    values = sorted(b.quote_volume for b in recent)
    n = len(values)
    if n == 0:
        return 0.0
    if n % 2:
        return values[n // 2]
    return (values[n // 2 - 1] + values[n // 2]) / 2.0


def trend_filter(bars: list[Bar], window: int = 200) -> dict[str, Any]:
    """Is price above its moving average, and by how much?"""
    if len(bars) < window + 1:
        return {"available": False, "above": None, "distance_pct": None, "ma": None}
    closes = [b.close for b in bars[-(window + 1):-1]]
    ma = sum(closes) / len(closes)
    last = bars[-1].close
    return {
        "available": True,
        "above": last > ma,
        "distance_pct": (last / ma - 1.0) * 100.0 if ma > 0 else None,
        "ma": ma,
    }

"""Universe construction: join CoinPaprika, Binance and DefiLlama into ``Asset``s.

This is the messiest part of the system, and the mess is concentrated here on
purpose so the rest of the code can pretend the world is clean.

Three joins are being performed, and each can go wrong in a specific way:

1. **CoinPaprika symbol -> Binance spot pair.** Tickers are not unique across
   projects, so ``marketcap.tickers`` already resolves collisions by keeping the
   best-ranked coin for each symbol. Here we additionally require a live USDT
   spot pair.
2. **Binance pair -> price history and order book.** Straightforward, but each
   call is a separate request, so this is where the run spends its time.
3. **Coin -> DefiLlama protocol.** The dangerous one. Matching on ticker alone
   would happily attach a wrapped-BTC bridge's revenue to Bitcoin itself. So a
   match also gets a confidence grade based on how well the *names* line up, and
   the confidence is carried all the way into the report rather than being
   silently trusted.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .model import Asset
from .quant import factors
from .sources import binance, defillama, marketcap

# Protocols in these categories are wrappers or infrastructure around another
# asset, not the asset itself, so their revenue must not be attributed to a coin
# that merely shares the ticker.
WRAPPER_CATEGORIES = {
    "bridge",
    "canonical bridge",
    "wrapped",
    "cross chain",
    "cex",
}

#: Words that declare a protocol to be a wrapper around something else. Used to
#: tell a genuine wrapper match from a base-layer asset that merely shares a
#: name prefix with a bridge built on top of it.
WRAPPER_WORDS = {
    "wrapped",
    "bridged",
    "staked",
    "canonical",
    "bridge",
    "cross",
    "portal",
    "gateway",
    "wormhole",
    "multichain",
}


def _wrapper_words(name: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", (name or "").lower()) if word in WRAPPER_WORDS}


def _is_same_wrapper(coin_name: str, protocol_name: str) -> bool:
    """Is the protocol the coin's own wrapper, rather than a wrapper *of* it?

    "Wrapped Bitcoin" against "Wrapped Bitcoin" is the same asset. "Avalanche"
    against "Avalanche Core Bridge" is not: the second is a bridge built on the
    first, and attributing the bridge's revenue to AVAX would be a category
    error. The test is whether the coin's own name already declares it a
    wrapper, which is exactly what the real wrapper tokens do.
    """
    if _normalise(coin_name) == _normalise(protocol_name):
        return True
    return bool(_wrapper_words(coin_name) & _wrapper_words(protocol_name))


@dataclass
class Selection:
    assets: list[Asset] = field(default_factory=list)
    considered: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)
    matched_protocols: int = 0
    high_confidence_matches: int = 0
    low_confidence_matches: int = 0


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _change_from_bars(bars: list[binance.Bar], days: int) -> float | None:
    """Percentage change over ``days`` from daily closes.

    CoinPaprika returns a literal ``0`` for ``percent_change_30d`` and
    ``percent_change_1y`` on its free tier, which would otherwise render as an
    authoritative-looking "+0.0%" in the report. So these are computed from the
    Binance history we already download, and the aggregator's value is only used
    when it is actually populated.
    """
    if len(bars) < 2:
        return None
    last = bars[-1].close
    index = max(0, len(bars) - 1 - days)
    first = bars[index].close
    if not first:
        return None
    # Refuse a window far shorter than requested: a "1 year" figure derived from
    # three weeks of data is worse than no figure at all.
    span = (bars[-1].ts - bars[index].ts).days
    if days > 2 and span < days * 0.6:
        return None
    return ((last / first) - 1.0) * 100.0


def _name_affinity(coin_name: str, protocol_name: str) -> int:
    """How much the two names look like the same thing. 2 strong, 1 weak, 0 none."""
    coin = _normalise(coin_name)
    proto = _normalise(protocol_name)
    if not coin or not proto:
        return 0
    if coin.startswith(proto) or proto.startswith(coin):
        return 2
    if coin in proto or proto in coin:
        return 1
    return 0


def match_protocol(
    symbol: str, name: str, index: dict[str, list[defillama.Protocol]]
) -> tuple[defillama.Protocol | None, str, str]:
    """Pick the best DefiLlama protocol for a coin.

    Returns ``(protocol, confidence, reason)``. Confidence is ``high`` when the
    symbol matches *and* the names look alike, ``medium`` when the symbol matches
    and the category is not a wrapper, and ``low`` when it is only a bare ticker
    collision -- in which case the fundamentals are reported but explicitly
    marked as unverified.
    """
    candidates = index.get(symbol.upper())
    if not candidates:
        return None, "none", "no DefiLlama protocol with this ticker"

    scored: list[tuple[int, float, defillama.Protocol]] = []
    for protocol in candidates:
        affinity = _name_affinity(name, protocol.name)
        material = (protocol.revenue_annualized or 0.0) + (protocol.tvl or 0.0)
        scored.append((affinity, material, protocol))
    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)

    affinity, _, best = scored[0]
    category = (best.categories[0].lower() if best.categories else "")
    is_wrapper = category in WRAPPER_CATEGORIES

    # A wrapper/bridge match has to be the coin's *own* wrapper. Matching on name
    # similarity alone attributes a bridge's revenue and category to the chain it
    # serves, which is how a base-layer asset ends up classified as a bridge and
    # scored on another protocol's economics.
    if is_wrapper and affinity >= 1 and not _is_same_wrapper(name, best.name):
        return None, "none", (
            f"'{best.name}' ({category}) shares a name with this coin but is a "
            "separate protocol built on top of it, so its revenue and TVL are not "
            "attributed here"
        )

    if affinity == 2:
        return best, "high", f"ticker and name both match '{best.name}'"
    if affinity == 1:
        return best, "medium", f"ticker matches and the name is similar to '{best.name}'"
    if is_wrapper:
        return None, "none", (
            f"ticker collision with '{best.name}' ({category}), which is a wrapper "
            "around another asset rather than this coin"
        )
    return best, "low", (
        f"only the ticker matched ('{best.name}'); the fundamentals shown may "
        "belong to a different protocol"
    )


def _apply_protocol(asset: Asset, protocol: defillama.Protocol, confidence: str, reason: str) -> None:
    asset.defillama_categories = list(protocol.categories)
    asset.revenue_24h = protocol.revenue_24h
    asset.revenue_30d = protocol.revenue_30d
    asset.revenue_annualized = protocol.revenue_annualized
    asset.revenue_change_7d = protocol.revenue_change_7d
    asset.revenue_methodology = protocol.methodology
    asset.tvl = protocol.tvl
    asset.protocol_name = protocol.name
    asset.chains = list(protocol.chains)

    if confidence == "low":
        asset.warn(
            f"Protocol fundamentals are a low-confidence match ({reason}). "
            "Treat the revenue and TVL figures as unverified."
        )
    elif confidence == "medium":
        asset.warn(f"Protocol match is medium confidence ({reason}).")


def build(
    cfg: Any,
    fetcher: Any,
    *,
    limit: int | None = None,
    verbose: bool = False,
    on_progress: Any = None,
) -> Selection:
    """Assemble the candidate universe. ``limit`` caps how many assets to fetch."""
    selection = Selection()
    quote = str(cfg.general.quote_asset)

    def say(message: str) -> None:
        if verbose:
            print(message)
        if on_progress is not None:
            on_progress(message)

    # -- 1. market caps -------------------------------------------------------
    caps = marketcap.tickers(fetcher)
    say(f"  CoinPaprika returned {len(caps):,} tickers")

    # -- 2. tradable pairs ----------------------------------------------------
    pairs = binance.spot_pairs(fetcher, quote)
    by_base: dict[str, binance.Pair] = {}
    for pair in pairs.values():
        by_base.setdefault(pair.base, pair)
    say(f"  Binance has {len(pairs):,} {quote} spot pairs ({len(by_base):,} base assets)")

    # -- 3. reference data ----------------------------------------------------
    stablecoins = defillama.stablecoins(fetcher)
    say(f"  DefiLlama lists {len(stablecoins):,} pegged assets")
    protocol_index = defillama.build_index(fetcher)
    say(f"  DefiLlama protocol index covers {len(protocol_index):,} tickers")
    tickers_24h = binance.tickers_24h(fetcher)
    say(f"  Binance 24h tickers: {len(tickers_24h):,}")

    # -- 4. selection ---------------------------------------------------------
    exclude_stables = bool(getattr(cfg.quant.disqualifiers, "exclude_stablecoins", True))
    ranked_coins = sorted(caps.values(), key=lambda c: c.rank)

    wanted = int(cfg.general.universe_size)
    if limit:
        wanted = min(wanted, int(limit))

    chosen: list[marketcap.MarketCap] = []
    for coin in ranked_coins:
        if len(chosen) >= wanted:
            break
        if coin.market_cap <= 0:
            selection.skipped.append((coin.symbol, "no market cap reported"))
            continue
        if coin.symbol not in by_base:
            continue  # no USDT venue; too common to bother listing
        if exclude_stables and coin.symbol.upper() in stablecoins:
            selection.skipped.append((coin.symbol, "stablecoin or pegged asset"))
            continue
        chosen.append(coin)

    selection.considered = len(chosen)
    say(f"  Selected {len(chosen)} candidates for detailed analysis")

    # -- 5. per-asset detail --------------------------------------------------
    for position, coin in enumerate(chosen, start=1):
        pair = by_base[coin.symbol]
        if verbose and (position % 10 == 1 or position == len(chosen)):
            print(f"  [{position}/{len(chosen)}] {coin.symbol} ...")

        asset = Asset(
            symbol=coin.symbol,
            name=coin.name,
            rank=coin.rank,
            price=coin.price,
            market_cap=coin.market_cap,
            total_supply=coin.total_supply,
            max_supply=coin.max_supply,
            pct_from_ath=coin.pct_from_ath,
            pct_change_7d=coin.pct_change_7d,
            pct_change_30d=coin.pct_change_30d or None,
            pct_change_1y=coin.pct_change_1y or None,
            beta=coin.beta,
            first_data_at=coin.first_data_at,
            pair=pair.symbol,
        )

        # Stablecoin metadata is recorded even when stablecoins are excluded,
        # because the Sharia section reports on them separately.
        peg = stablecoins.get(coin.symbol.upper())
        if peg:
            asset.is_stablecoin = True
            asset.stablecoin = peg

        try:
            asset.bars = binance.klines_daily(fetcher, pair.symbol, 1000)
        except Exception as exc:
            asset.warn(f"price history unavailable: {type(exc).__name__}")
            asset.bars = []

        try:
            asset.book = binance.depth(
                fetcher,
                pair.symbol,
                levels=int(cfg.quant.depth.levels),
                band_pct=float(cfg.quant.depth.band_pct),
            )
        except Exception as exc:
            asset.warn(f"order book unavailable: {type(exc).__name__}")
            asset.book = None

        try:
            listed = binance.listing_date(fetcher, pair.symbol)
            asset.age_days = binance.age_days(listed)
        except Exception:
            asset.age_days = None

        ticker = tickers_24h.get(pair.symbol)
        if ticker is not None:
            asset.quote_volume_24h = ticker.quote_volume
            asset.trades_24h = ticker.trades

        asset.median_volume_30d = binance.median_daily_quote_volume(asset.bars, window=30)
        if asset.median_volume_30d <= 0:
            asset.median_volume_30d = asset.quote_volume_24h
            asset.warn("30-day volume history unavailable; used the 24h figure instead")

        # Prefer a figure computed from real closes over the aggregator's field,
        # which is unpopulated (literally 0) on the free tier.
        for window, attribute in ((30, "pct_change_30d"), (365, "pct_change_1y")):
            derived = _change_from_bars(asset.bars, window)
            if derived is not None:
                setattr(asset, attribute, derived)

        protocol, confidence, reason = match_protocol(coin.symbol, coin.name, protocol_index)
        if protocol is not None:
            _apply_protocol(asset, protocol, confidence, reason)
            selection.matched_protocols += 1
            if confidence == "high":
                selection.high_confidence_matches += 1
            elif confidence == "low":
                selection.low_confidence_matches += 1
        elif confidence == "none" and "wrapper" in reason:
            asset.warn(reason)

        selection.assets.append(asset)

    return selection


def summarise(assets: list[Asset]) -> dict[str, Any]:
    """A few coverage numbers, so the report can be honest about data gaps."""
    if not assets:
        return {}
    total = len(assets)
    return {
        "assets": total,
        "with_book": sum(1 for a in assets if a.book is not None),
        "with_bars": sum(1 for a in assets if len(a.bars) >= 200),
        "with_protocol": sum(1 for a in assets if a.has_protocol_data),
        "with_protocol_financials": sum(1 for a in assets if a.has_protocol_financials),
        "with_revenue": sum(1 for a in assets if a.revenue_annualized),
        "with_fdv": sum(1 for a in assets if a.fdv_to_mcap is not None),
        "with_age": sum(1 for a in assets if a.age_days is not None),
        "pct_with_revenue": (sum(1 for a in assets if a.revenue_annualized) / total) * 100.0,
    }

"""Data sources.

Each module wraps one provider and returns plain dataclasses or dicts, so the
scoring and screening layers never touch HTTP or JSON directly.

Provider roles, chosen from what is actually reliable and unmetered:

===============  ==========================================================
Binance          Primary. Universe, price, real volume, real OHLCV, order
                 book depth, listing dates. No API key, generous limits.
CoinPaprika      Market caps, ranks, supply. One call returns ~2000 coins.
DefiLlama        Protocol revenue and category -- the core of the Sharia
                 business-activity screen. Large payloads, cached hard.
alternative.me   Fear & Greed index.
CoinGecko        *Optional* enrichment only. Heavily throttled on the free
                 tier, so it is never on the critical path.
===============  ==========================================================
"""

from .binance import Bar, Book, Pair, Ticker, book_metrics
from . import binance, defillama, marketcap, sentiment

__all__ = [
    "Bar",
    "Book",
    "Pair",
    "Ticker",
    "book_metrics",
    "binance",
    "defillama",
    "marketcap",
    "sentiment",
]

"""DefiLlama: protocol revenue, category and TVL.

This is the most important source for the Sharia screen, because it supplies a
**business-activity classification that is not my opinion**. DefiLlama labels a
protocol ``Lending`` or ``Prediction Market`` or ``Basis Trading``; those labels
map onto fiqh concerns (riba, maysir, gharar) far more defensibly than me
guessing from a coin's marketing copy.

It also labels a handful of protocols ``Ponzi``, which is its own kind of
useful.

Payloads here are large (``/protocols`` is ~9 MB), so they are cached for hours
and pulled with gzip.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

BASE = "https://api.llama.fi"
STABLE_BASE = "https://stablecoins.llama.fi"

TTL_PROTOCOLS = 21_600
TTL_FEES = 21_600
TTL_STABLES = 21_600


@dataclass
class Protocol:
    slug: str
    name: str
    symbol: str | None
    categories: list[str] = field(default_factory=list)
    tvl: float | None = None
    mcap: float | None = None
    chains: list[str] = field(default_factory=list)
    revenue_24h: float | None = None
    revenue_7d: float | None = None
    revenue_30d: float | None = None
    revenue_annualized: float | None = None
    revenue_change_7d: float | None = None
    methodology: str | None = None

    @property
    def price_to_fees(self) -> float | None:
        """Market cap divided by annualised revenue. Lower looks cheaper.

        Only meaningful for protocols that actually capture fees. A protocol
        with near-zero revenue produces a meaningless ratio, so it is skipped.
        """
        if not self.mcap or not self.revenue_annualized:
            return None
        if self.revenue_annualized <= 0:
            return None
        return self.mcap / self.revenue_annualized


def _f(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def protocol_list(fetcher: Any) -> list[dict[str, Any]]:
    """Raw ``/protocols`` payload: TVL, category, chains, symbol."""
    return fetcher.get_json(
        f"{BASE}/protocols",
        provider="defillama",
        ttl=TTL_PROTOCOLS,
        cache_key="defillama:protocols",
    )


def fees_overview(fetcher: Any) -> list[dict[str, Any]]:
    """Raw ``/overview/fees`` payload: 24h/7d/30d revenue and category."""
    data = fetcher.get_json(
        f"{BASE}/overview/fees"
        "?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true",
        provider="defillama",
        ttl=TTL_FEES,
        cache_key="defillama:fees_overview",
    )
    return data.get("protocols", []) if isinstance(data, dict) else (data or [])


def _split_symbols(raw: Any) -> list[str]:
    if not raw or not isinstance(raw, str):
        return []
    parts = [p.strip().upper() for p in raw.replace("/", ",").split(",")]
    return [p for p in parts if p and p != "-" and p.isalnum() and 1 <= len(p) <= 12]


def build_index(fetcher: Any, *, include_tvl: bool = True) -> dict[str, list[Protocol]]:
    """Merge TVL and revenue data into ``{SYMBOL: [Protocol, ...]}``.

    Several protocols can share a ticker (forks, v1/v2/v3 deployments), so the
    value is a list and callers choose by revenue or TVL. Joining is done on
    slug, falling back to normalised name, because DefiLlama uses different
    identifier fields across the two endpoints.
    """
    merged: dict[str, Protocol] = {}

    def key_for(rec: dict[str, Any]) -> str:
        return str(rec.get("slug") or rec.get("defillamaId") or rec.get("id") or "").strip().lower()

    def name_key(rec: dict[str, Any]) -> str:
        return str(rec.get("name") or "").strip().lower()

    by_name: dict[str, str] = {}

    if include_tvl:
        try:
            for rec in protocol_list(fetcher) or []:
                k = key_for(rec)
                if not k:
                    continue
                proto = merged.setdefault(k, Protocol(slug=k, name=rec.get("name") or k, symbol=None))
                proto.name = rec.get("name") or proto.name
                cat = rec.get("category")
                if cat and cat not in proto.categories:
                    proto.categories.append(cat)
                proto.tvl = _f(rec.get("tvl"))
                proto.mcap = _f(rec.get("mcap")) or proto.mcap
                chains = rec.get("chains") or []
                if isinstance(chains, list):
                    proto.chains = [str(c) for c in chains][:12]
                syms = _split_symbols(rec.get("symbol"))
                if syms:
                    proto.symbol = syms[0]
                by_name[name_key(rec)] = k
        except Exception:
            # TVL is a nice-to-have; revenue and category matter more.
            pass

    try:
        for rec in fees_overview(fetcher) or []:
            k = key_for(rec)
            if not k or k not in merged:
                k2 = by_name.get(name_key(rec))
                if k2:
                    k = k2
            if not k:
                continue
            proto = merged.setdefault(k, Protocol(slug=k, name=rec.get("name") or k, symbol=None))
            proto.name = rec.get("name") or proto.name
            cat = rec.get("category")
            if cat and cat not in proto.categories:
                proto.categories.append(cat)
            proto.revenue_24h = _f(rec.get("total24h"))
            proto.revenue_7d = _f(rec.get("total7d"))
            proto.revenue_30d = _f(rec.get("total30d"))
            proto.revenue_annualized = _f(rec.get("annualized1y"))
            proto.revenue_change_7d = _f(rec.get("change_7dover7d"))
            if rec.get("methodology"):
                proto.methodology = str(rec["methodology"])[:400]
            if proto.mcap is None:
                proto.mcap = _f(rec.get("mcap"))
            syms = _split_symbols(rec.get("symbol"))
            if syms and not proto.symbol:
                proto.symbol = syms[0]
    except Exception:
        pass

    index: dict[str, list[Protocol]] = {}
    for proto in merged.values():
        symbols: list[str] = []
        if proto.symbol:
            symbols.append(proto.symbol)
        # Fall back to the leading word of the protocol name, which often is the
        # ticker (e.g. "Aave V3" -> "AAVE" is already covered by symbol, but
        # "Curve DEX" -> "CURVE" is not, so this stays conservative).
        for sym in symbols:
            index.setdefault(sym, []).append(proto)
    return index


def stablecoins(fetcher: Any) -> dict[str, dict[str, Any]]:
    """Pegged assets keyed by uppercase symbol.

    Used to keep stablecoins out of the *investment* ranking while still
    reporting them in the Sharia section, where they are genuinely interesting:
    a token backed by interest-bearing treasuries raises a riba question that a
    purely algorithmic one does not.
    """
    data = fetcher.get_json(
        f"{STABLE_BASE}/stablecoins?includePrices=false",
        provider="defillama",
        ttl=TTL_STABLES,
        cache_key="defillama:stablecoins",
    )
    out: dict[str, dict[str, Any]] = {}
    for asset in (data or {}).get("peggedAssets", []):
        symbol = (asset.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        circulating = (asset.get("circulating") or {}).get("peggedUSD")
        entry = {
            "symbol": symbol,
            "name": asset.get("name"),
            "peg_type": asset.get("pegType"),
            "peg_mechanism": asset.get("pegMechanism"),
            "circulating_usd": _f(circulating),
            "chains": asset.get("chains") or [],
        }
        existing = out.get(symbol)
        if existing is None or (entry["circulating_usd"] or 0) > (existing["circulating_usd"] or 0):
            out[symbol] = entry
    return out


def stablecoin_supply_trend(fetcher: Any, days: int = 30) -> dict[str, Any]:
    """Total stablecoin supply and its change over ``days``.

    Rising stablecoin supply is a reasonable proxy for idle capital sitting on
    the sidelines, which is why it feeds the regime filter rather than the
    per-coin ranking.
    """
    try:
        rows = fetcher.get_json(
            f"{STABLE_BASE}/stablecoincharts/all",
            provider="defillama",
            ttl=TTL_STABLES,
            cache_key="defillama:stablecoincharts_all",
        )
    except Exception:
        return {"available": False}
    if not rows:
        return {"available": False}
    series: list[tuple[int, float]] = []
    for row in rows:
        ts = row.get("date")
        total = (row.get("totalCirculatingUSD") or {}).get("peggedUSD")
        if ts is None or total is None:
            continue
        series.append((int(ts), float(total)))
    if not series:
        return {"available": False}
    series.sort(key=lambda x: x[0])
    latest = series[-1][1]
    if len(series) > days:
        prior = series[-days - 1][1]
    else:
        prior = series[0][1]
    change = (latest - prior) / prior if prior else None
    return {
        "available": True,
        "latest_usd": latest,
        "change_pct": change,
        "days": days,
        "as_of": series[-1][0],
    }

"""Sentiment and network inputs for the regime filter.

These do not rank individual coins. They set the recommended total exposure,
which is the honest place to put a market-timing view: it is far easier to say
"conditions are euphoric, hold less" than to say "this coin will outperform".

Fear & Greed is a sentiment survey composite. It is contrarian at extremes and
close to noise in the middle, so it is used as a scaling factor with hard
thresholds rather than as a continuous signal.
"""

from __future__ import annotations

from typing import Any

FNG_URL = "https://api.alternative.me/fng/"
MEMPOOL_URL = "https://mempool.space/api/v1/fees/recommended"

TTL_FNG = 3_600
TTL_NETWORK = 1_800


def fear_greed(fetcher: Any, limit: int = 30) -> dict[str, Any]:
    """Current Fear & Greed value plus a short history.

    The API returns values as strings and timestamps as epoch seconds.
    """
    try:
        data = fetcher.get_json(
            f"{FNG_URL}?limit={limit}",
            provider="alternative.me",
            ttl=TTL_FNG,
            cache_key=f"fng:{limit}",
        )
    except Exception:
        return {"available": False}

    rows = (data or {}).get("data") or []
    parsed: list[dict[str, Any]] = []
    for row in rows:
        try:
            parsed.append(
                {
                    "value": int(row["value"]),
                    "classification": row.get("value_classification", ""),
                    "timestamp": int(row["timestamp"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    if not parsed:
        return {"available": False}

    parsed.sort(key=lambda r: r["timestamp"], reverse=True)
    values = [r["value"] for r in parsed]
    return {
        "available": True,
        "value": values[0],
        "classification": parsed[0]["classification"],
        "previous": values[1] if len(values) > 1 else None,
        "avg_30d": sum(values) / len(values),
        "min_30d": min(values),
        "max_30d": max(values),
        "history": list(reversed(parsed)),
    }


def btc_network_fees(fetcher: Any) -> dict[str, Any]:
    """Bitcoin mempool fee estimates, in sat/vB.

    Purely informational. Sustained fee spikes indicate real settlement demand
    rather than speculative trading, which is a mildly useful confirmation
    signal for the "is this chain actually used" question.
    """
    try:
        data = fetcher.get_json(
            MEMPOOL_URL,
            provider="mempool.space",
            ttl=TTL_NETWORK,
            cache_key="mempool:fees",
        )
    except Exception:
        return {"available": False}
    if not isinstance(data, dict):
        return {"available": False}
    return {
        "available": True,
        "fastest": data.get("fastestFee"),
        "half_hour": data.get("halfHourFee"),
        "hour": data.get("hourFee"),
        "economy": data.get("economyFee"),
        "minimum": data.get("minimumFee"),
    }

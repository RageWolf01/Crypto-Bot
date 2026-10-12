"""HTTP layer: throttling, retries, gzip, and a tolerant cache.

Public crypto APIs are hostile to naive clients:

* **CoinGecko's free tier** throttles aggressively (my own probe got a hard 429
  after roughly eight rapid calls) and its limits are not documented precisely.
* **DefiLlama** returns multi-megabyte JSON payloads, so gzip matters.
* Transient 5xx and socket resets are routine.

So every request goes through this module, which:

1. enforces a per-provider minimum interval between calls,
2. retries with exponential backoff and jitter, honouring ``Retry-After``,
3. requests gzip and transparently decompresses,
4. serves from a TTL cache, and
5. on total failure falls back to a *stale* cache entry rather than aborting the
   run, recording a warning so the report can say the data was old.

Standard library only: ``urllib`` and ``gzip``.
"""

from __future__ import annotations

import gzip
import io
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .store import Store, utcnow

USER_AGENT = (
    "crypto-advisor/0.1 (personal research tool; "
    "https://github.com/  kontakt: local)"
)

# Providers, and the config key holding their minimum call interval.
PROVIDER_INTERVAL_KEYS = {
    "binance": "binance_min_interval_ms",
    "coingecko": "coingecko_min_interval_ms",
    "defillama": "defillama_min_interval_ms",
}

# HTTP statuses worth retrying.
RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504, 522, 524}


class DataUnavailable(Exception):
    """Raised when a resource cannot be served from network or cache."""


class FetchStats:
    def __init__(self) -> None:
        self.network = 0
        self.cache_hit = 0
        self.stale = 0
        self.retries = 0
        self.failures = 0
        self.bytes_in = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "network_calls": self.network,
            "cache_hits": self.cache_hit,
            "stale_fallbacks": self.stale,
            "retries": self.retries,
            "failures": self.failures,
            "bytes_in": self.bytes_in,
        }

    def line(self) -> str:
        return (
            f"{self.network} network / {self.cache_hit} cached / "
            f"{self.stale} stale / {self.retries} retries / "
            f"{self.failures} failed / {self.bytes_in / 1024:.0f} KiB in"
        )


class Fetcher:
    """Cached, throttled, retrying JSON client."""

    def __init__(self, store: Store, cfg: Any, *, verbose: bool = False) -> None:
        self.store = store
        self.cfg = cfg
        self.verbose = verbose
        self.stats = FetchStats()
        self.warnings: list[str] = []
        self._last_call: dict[str, float] = {}

    # -- public API -----------------------------------------------------------

    def get_json(
        self,
        url: str,
        *,
        provider: str,
        ttl: int,
        cache_key: str | None = None,
        allow_stale: bool | None = None,
        max_age_if_stale: int | None = None,
    ) -> Any:
        """Fetch JSON with caching. Returns parsed data or raises DataUnavailable."""
        key = cache_key or f"{provider}:{url}"
        entry = self.store.get_cache(key)

        if entry is not None and entry.is_fresh():
            self.stats.cache_hit += 1
            self._log(provider, url, "cache_hit", entry.status, 0, f"age={entry.age_s:.0f}s")
            try:
                return entry.json()
            except json.JSONDecodeError:
                # Corrupt cache row; fall through and refetch.
                self._log(provider, url, "cache_corrupt", entry.status, 0, None)

        if allow_stale is None:
            allow_stale = bool(self.cfg.fetch.allow_stale_fallback)
        if max_age_if_stale is None:
            max_age_if_stale = int(self.cfg.fetch.max_stale_age_s)

        try:
            body, status, elapsed_ms = self._request_with_retries(url, provider)
        except DataUnavailable as exc:
            self.stats.failures += 1
            if entry is not None and allow_stale and entry.age_s <= max_age_if_stale:
                self.stats.stale += 1
                msg = (
                    f"{provider}: live fetch failed ({exc}); using cached data "
                    f"{self._human_age(entry.age_s)} old"
                )
                self._warn(msg)
                self._log(provider, url, "stale_fallback", entry.status, 0, str(exc))
                try:
                    return entry.json()
                except json.JSONDecodeError as decode_exc:
                    raise DataUnavailable(
                        f"{url}: cached body is corrupt and refetch failed: {decode_exc}"
                    ) from decode_exc
            raise

        self.stats.network += 1
        self.stats.bytes_in += len(body)
        self.store.put_cache(key, provider, url, status, body, ttl)
        self._log(provider, url, "network", status, elapsed_ms, None)

        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise DataUnavailable(f"{url}: response was not valid JSON ({exc})") from exc

    def get_raw(
        self, url: str, *, provider: str, ttl: int = 0, **kwargs: Any
    ) -> bytes:
        """Like :meth:`get_json` but returns bytes, for non-JSON endpoints."""
        return self._request_with_retries(url, provider)[0].encode("utf-8")

    # -- internals ------------------------------------------------------------

    def _warn(self, message: str) -> None:
        if message not in self.warnings:
            self.warnings.append(message)
        if self.verbose:
            print(f"    ! {message}")

    def _log(
        self,
        provider: str,
        url: str,
        outcome: str,
        status: int | None,
        ms: int | None,
        detail: str | None,
    ) -> None:
        try:
            self.store.log_fetch(provider, url, outcome, status, ms, detail)
        except Exception:
            pass  # logging must never break a run
        if self.verbose and outcome not in ("cache_hit",):
            print(f"    [{provider}] {outcome} {status or ''} {ms or 0}ms {url[:96]}")

    def _throttle(self, provider: str) -> None:
        interval_key = PROVIDER_INTERVAL_KEYS.get(provider)
        if not interval_key:
            return
        interval_s = float(self.cfg.fetch.get(interval_key, 0)) / 1000.0
        if interval_s <= 0:
            return
        last = self._last_call.get(provider)
        if last is not None:
            wait = interval_s - (time.monotonic() - last)
            if wait > 0:
                if self.verbose:
                    print(f"    [{provider}] throttling {wait:.1f}s")
                time.sleep(wait)
        self._last_call[provider] = time.monotonic()

    def _request_with_retries(self, url: str, provider: str) -> tuple[str, int, int]:
        cfg = self.cfg.fetch
        timeout = float(cfg.http_timeout_s)
        attempts = max(1, int(cfg.max_retries))
        last_error: str = "unknown error"

        for attempt in range(1, attempts + 1):
            self._throttle(provider)
            started = time.monotonic()
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "application/json, */*",
                        "Accept-Encoding": "gzip",
                        "Connection": "close",
                    },
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                    status = resp.status
                    encoding = (resp.headers.get("Content-Encoding") or "").lower()
                elapsed_ms = int((time.monotonic() - started) * 1000)

                if "gzip" in encoding:
                    raw = gzip.decompress(raw)
                text = raw.decode("utf-8", "replace")
                if not text.strip():
                    raise DataUnavailable(f"empty body from {url}")
                return text, status, elapsed_ms

            except urllib.error.HTTPError as exc:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                last_error = f"HTTP {exc.code} {exc.reason}"
                retry_after = self._retry_after(exc)
                if exc.code in RETRYABLE_STATUS and attempt < attempts:
                    self.stats.retries += 1
                    self._log(provider, url, "retry", exc.code, elapsed_ms, last_error)
                    delay = retry_after if retry_after is not None else self._backoff(attempt)
                    if self.verbose:
                        print(f"    [{provider}] {last_error}; retry {attempt}/{attempts - 1} in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                self._log(provider, url, "http_error", exc.code, elapsed_ms, last_error)
                raise DataUnavailable(f"{url}: {last_error}") from exc

            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                elapsed_ms = int((time.monotonic() - started) * 1000)
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < attempts:
                    self.stats.retries += 1
                    self._log(provider, url, "retry", None, elapsed_ms, last_error)
                    delay = self._backoff(attempt)
                    if self.verbose:
                        print(f"    [{provider}] {last_error[:70]}; retry {attempt}/{attempts - 1} in {delay:.1f}s")
                    time.sleep(delay)
                    continue
                self._log(provider, url, "network_error", None, elapsed_ms, last_error)
                raise DataUnavailable(f"{url}: {last_error}") from exc

            except DataUnavailable:
                raise
            except Exception as exc:  # pragma: no cover - defensive
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < attempts:
                    time.sleep(self._backoff(attempt))
                    continue
                raise DataUnavailable(f"{url}: {last_error}") from exc

        raise DataUnavailable(f"{url}: exhausted {attempts} attempts ({last_error})")

    @staticmethod
    def _backoff(attempt: int, base: float = 1.4, cap: float = 45.0) -> float:
        """Exponential backoff with jitter, so parallel runs do not sync up."""
        raw = base * (2 ** (attempt - 1))
        return min(cap, raw) * (0.75 + random.random() * 0.5)

    @staticmethod
    def _retry_after(exc: urllib.error.HTTPError) -> float | None:
        value = exc.headers.get("Retry-After") if exc.headers else None
        if not value:
            return None
        try:
            return min(120.0, float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _human_age(seconds: float) -> str:
        if seconds < 90:
            return f"{seconds:.0f}s"
        if seconds < 5400:
            return f"{seconds / 60:.0f}m"
        if seconds < 172800:
            return f"{seconds / 3600:.1f}h"
        return f"{seconds / 86400:.1f}d"


def build_url(base: str, params: dict[str, Any] | None = None) -> str:
    """Join a base URL with query parameters, skipping ``None`` values."""
    if not params:
        return base
    clean = {k: v for k, v in params.items() if v is not None}
    if not clean:
        return base
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{urllib.parse.urlencode(clean)}"


def head(url: str, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch just headers. Used by ``--selftest`` to check reachability."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(2048)
            return {
                "ok": True,
                "status": resp.status,
                "ms": int((time.monotonic() - started) * 1000),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status": exc.code,
            "ms": int((time.monotonic() - started) * 1000),
            "error": f"{exc.code} {exc.reason}",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": None,
            "ms": int((time.monotonic() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}",
        }

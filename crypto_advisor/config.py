"""Configuration loading and validation.

The config is a single TOML file (see ``config.toml`` at the project root).
It is parsed with the standard library ``tomllib``, so there are no
dependencies and it stays readable and comment-friendly for hand editing.
"""

from __future__ import annotations

import time
import tomllib
from datetime import timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.toml"


class ConfigError(Exception):
    """Raised when the config file is missing, malformed, or nonsensical."""


def tz_database_available() -> bool:
    """Whether the IANA time zone database can actually be read."""
    try:
        from zoneinfo import available_timezones

        return bool(available_timezones())
    except Exception:
        return False


def resolve_timezone(name: Any) -> tuple[tzinfo, str | None]:
    """Resolve a time zone name to a tzinfo, degrading instead of failing.

    Returns ``(tzinfo, warning)``. A stock Windows Python ships no IANA database,
    so an ordinary name like ``Europe/London`` raises ZoneInfoNotFoundError. In
    that case we fall back to the machine's current UTC offset, which is correct
    for the rest of the day and only wrong across a DST boundary.
    """
    key = str(name or "UTC").strip()

    if key.upper() in {"UTC", "GMT", "Z", "ETC/UTC"}:
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(key), None
        except Exception:
            return timezone.utc, None

    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(key), None
    except Exception:
        pass

    offset = -time.timezone
    if time.localtime().tm_isdst > 0 and time.daylight:
        offset = -time.altzone
    sign = "+" if offset >= 0 else "-"
    magnitude = abs(offset)
    rendered = f"UTC{sign}{magnitude // 3600:02d}:{(magnitude % 3600) // 60:02d}"

    label = ""
    if time.tzname:
        try:
            label = time.tzname[1 if time.localtime().tm_isdst > 0 else 0]
        except IndexError:
            label = time.tzname[0]
    suffix = f" ({label})" if label else ""

    if tz_database_available():
        # The database exists, so the name itself is the problem.
        return timezone(timedelta(seconds=offset)), (
            f"general.timezone {key!r} is not a recognised IANA name, so the system "
            f"offset {rendered}{suffix} is being used instead. Try 'UTC' or a name "
            f"like 'Asia/Kuala_Lumpur'."
        )

    return timezone(timedelta(seconds=offset)), (
        f"no IANA time zone database is installed for this Python, so general.timezone "
        f"{key!r} could not be loaded and the fixed system offset {rendered}{suffix} is "
        f"being used instead. Timestamps are unaffected (they are all UTC); only the "
        f"'local time' rendering in reports may be off by an hour across a daylight "
        f"saving change. Installing the 'tzdata' package fixes this."
    )


class Section:
    """A dict-like config node allowing attribute access.

    ``cfg.quant.weights.liquidity`` reads the same value as
    ``cfg["quant"]["weights"]["liquidity"]``.
    """

    def __init__(self, data: dict[str, Any], path: str = "") -> None:
        self._data = data
        self._path = path

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            value = self._data[name]
        except KeyError:
            where = self._path or "config"
            raise ConfigError(f"missing required setting: {where}.{name}") from None
        if isinstance(value, dict):
            return Section(value, f"{self._path}.{name}".lstrip("."))
        return value

    def get(self, name: str, default: Any = None) -> Any:
        value = self._data.get(name, default)
        if isinstance(value, dict):
            return Section(value, f"{self._path}.{name}".lstrip("."))
        return value

    def __contains__(self, name: str) -> bool:
        return name in self._data

    def __getitem__(self, name: str) -> Any:
        return getattr(self, name)

    def keys(self):
        return self._data.keys()

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __repr__(self) -> str:
        return f"Section({self._path or 'root'}, keys={list(self._data)})"


class Config(Section):
    """Root config object. Also carries the source path and project root."""

    def __init__(self, data: dict[str, Any], path: Path) -> None:
        super().__init__(data, "")
        self.path = path
        self.root = path.parent
        self.warnings: list[str] = []

        # Named time zones need the IANA database, which a stock Windows Python
        # does not ship. Resolve it once here and record how it went, rather than
        # letting a missing database abort the whole tool.
        self._tz, tz_warning = resolve_timezone(self.general.timezone)
        if tz_warning:
            self.warnings.append(tz_warning)

    # -- time -----------------------------------------------------------------

    @property
    def tz(self) -> tzinfo:
        """The resolved timezone, falling back to a fixed offset if need be."""
        return self._tz

    # -- path helpers ---------------------------------------------------------

    def dir_for(self, key: str) -> Path:
        """Resolve a configured directory relative to the project root and create it."""
        rel = getattr(self.general, key)
        target = (self.root / rel).resolve()
        target.mkdir(parents=True, exist_ok=True)
        return target

    @property
    def data_dir(self) -> Path:
        return self.dir_for("data_dir")

    @property
    def report_dir(self) -> Path:
        return self.dir_for("report_dir")

    @property
    def db_path(self) -> Path:
        return self.data_dir / "cache.sqlite3"

    @property
    def snapshot_dir(self) -> Path:
        d = self.data_dir / "snapshots"
        d.mkdir(parents=True, exist_ok=True)
        return d


def load(path: str | Path | None = None) -> Config:
    """Load and validate the config file."""
    cfg_path = Path(path).resolve() if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise ConfigError(f"config file not found: {cfg_path}")
    try:
        with cfg_path.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{cfg_path} is not valid TOML: {exc}") from exc

    cfg = Config(data, cfg_path)
    problems = validate(cfg)
    if problems:
        joined = "\n  - ".join(problems)
        raise ConfigError(f"config problems in {cfg_path}:\n  - {joined}")
    return cfg


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

# Settings that must exist, expressed as dotted paths.
REQUIRED = [
    "general.universe_size",
    "general.quote_asset",
    "general.report_dir",
    "general.data_dir",
    "general.timezone",
    "quant.weights.liquidity",
    "quant.weights.momentum",
    "quant.weights.tokenomics",
    "quant.weights.traction",
    "quant.weights.valuation",
    "quant.disqualifiers.min_daily_volume_usd",
    "quant.disqualifiers.min_listing_age_days",
    "quant.disqualifiers.min_book_depth_usd",
    "quant.disqualifiers.max_spread_bps",
    "quant.depth.band_pct",
    "quant.depth.levels",
    "quant.momentum.windows",
    "quant.regime.use_btc_200dma",
    "fetch.http_timeout_s",
    "report.top_n",
]


def _dig(data: dict[str, Any], dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


_MISSING = object()


def validate(cfg: Config) -> list[str]:
    """Return a list of human-readable problems. Empty list means valid."""
    problems: list[str] = []
    data = cfg.as_dict()

    for dotted in REQUIRED:
        if _dig(data, dotted) is _MISSING:
            problems.append(f"missing required setting: {dotted}")
    if problems:
        return problems

    # -- general --------------------------------------------------------------
    if not 1 <= cfg.general.universe_size <= 2000:
        problems.append("general.universe_size must be between 1 and 2000")
    if not str(cfg.general.quote_asset).isupper():
        problems.append("general.quote_asset should be an uppercase ticker, e.g. USDT")

    if tz_database_available():
        try:
            from zoneinfo import ZoneInfo

            ZoneInfo(str(cfg.general.timezone))
        except Exception:
            problems.append(
                f"general.timezone {cfg.general.timezone!r} is not a valid IANA name "
                "(e.g. UTC, Europe/London, Asia/Kuala_Lumpur)"
            )
    # When the database is missing entirely there is nothing to validate against;
    # resolve_timezone() falls back to the system offset and says so in cfg.warnings.

    # -- weights --------------------------------------------------------------
    weights = cfg.quant.weights.as_dict()
    for name, value in weights.items():
        if not isinstance(value, (int, float)):
            problems.append(f"quant.weights.{name} must be a number")
        elif value < 0:
            problems.append(f"quant.weights.{name} must not be negative")
    if sum(v for v in weights.values() if isinstance(v, (int, float))) <= 0:
        problems.append("quant.weights must not all be zero")

    # -- disqualifiers --------------------------------------------------------
    dq = cfg.quant.disqualifiers
    if dq.min_daily_volume_usd < 0:
        problems.append("quant.disqualifiers.min_daily_volume_usd must not be negative")
    if dq.min_listing_age_days < 0:
        problems.append("quant.disqualifiers.min_listing_age_days must not be negative")
    if not 0 <= dq.max_spread_bps <= 10_000:
        problems.append("quant.disqualifiers.max_spread_bps must be between 0 and 10000")

    # -- momentum -------------------------------------------------------------
    windows = cfg.quant.momentum.windows
    if not isinstance(windows, list) or not windows:
        problems.append("quant.momentum.windows must be a non-empty list of day counts")
    else:
        for w in windows:
            if not isinstance(w, int) or w < 7:
                problems.append(f"quant.momentum.windows entry {w!r} must be an integer >= 7")
            elif w > 400:
                problems.append(
                    f"quant.momentum.windows entry {w} exceeds 400 days; "
                    "Binance daily history is capped at ~400 bars here"
                )

    # -- fetch ----------------------------------------------------------------
    if cfg.fetch.http_timeout_s < 5:
        problems.append("fetch.http_timeout_s must be at least 5")
    if cfg.fetch.coingecko_min_interval_ms < 1500:
        problems.append(
            "fetch.coingecko_min_interval_ms must be at least 1500; "
            "the free tier throttles hard below that"
        )

    # -- report ---------------------------------------------------------------
    if cfg.report.top_n < 1:
        problems.append("report.top_n must be at least 1")

    return problems


def describe(cfg: Config) -> str:
    """A short human-readable summary of the effective configuration."""
    w = cfg.quant.weights.as_dict()
    total = sum(v for v in w.values() if isinstance(v, (int, float))) or 1.0
    lines = [
        f"config        : {cfg.path}",
        f"universe      : top {cfg.general.universe_size} by market cap, "
        f"{cfg.general.quote_asset} pairs",
        f"data dir      : {cfg.data_dir}",
        f"report dir    : {cfg.report_dir}",
        f"timezone      : {cfg.general.timezone}",
        "weights       : "
        + ", ".join(f"{k}={v / total:.0%}" for k, v in sorted(w.items())),
        f"min volume    : ${cfg.quant.disqualifiers.min_daily_volume_usd:,.0f}/24h",
        f"min depth     : ${cfg.quant.disqualifiers.min_book_depth_usd:,.0f} within "
        f"{cfg.quant.depth.band_pct:.1%} of mid",
        f"max spread    : {cfg.quant.disqualifiers.max_spread_bps:.0f} bps",
        f"min age       : {cfg.quant.disqualifiers.min_listing_age_days:.0f} days listed",
        f"report top_n  : {cfg.report.top_n}",
    ]
    if getattr(cfg, "warnings", None):
        lines.append("")
        lines.extend(f"warning       : {w}" for w in cfg.warnings)
    return "\n".join(lines)

"""Command line interface.

    python -m crypto_advisor run          # full pass, writes the digest
    python -m crypto_advisor run --limit 20 --verbose
    python -m crypto_advisor show         # the latest digest
    python -m crypto_advisor doctor       # config + connectivity check
    python -m crypto_advisor rules        # the Sharia rule table
    python -m crypto_advisor sources      # data sources and cache state
    python -m crypto_advisor task --install --time 07:00
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from . import __version__, config as config_mod
from . import pipeline
from .sharia import knowledge as sharia_knowledge
from .sharia import rules as sharia_rules

TASK_NAME = "CryptoAdvisorDailyDigest"
LAUNCHER_NAME = "daily_digest.py"

LAUNCHER_TEMPLATE = '''"""Launcher for the scheduled digest.

Windows Task Scheduler does not set a working directory, so this file puts the
project root on the import path before starting the CLI. Point the scheduled task
at this script rather than at ``-m crypto_advisor``.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from crypto_advisor.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["run", "--quiet"]))
'''


def _load(args: argparse.Namespace):
    cfg = config_mod.load(getattr(args, "config", None))
    problems = config_mod.validate(cfg)
    if problems:
        print("Configuration problems:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        raise SystemExit(2)
    return cfg


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_run(args: argparse.Namespace) -> int:
    cfg = _load(args)
    result = pipeline.run(
        cfg,
        limit=args.limit,
        verbose=args.verbose and not args.quiet,
        write=not args.no_write,
    )

    if not args.quiet:
        print()
        print(f"Run {result.run_id} finished in "
              f"{(result.finished - result.started).total_seconds():.1f}s")
        counts = result.counts
        print(f"  analysed           {counts.get('analysed', 0)}")
        print(f"  passed gates       {counts.get('passed_gates', 0)}")
        print(f"  disqualified       {counts.get('disqualified', 0)}")
        print(f"  protocol matches   {counts.get('protocol_matches', 0)} "
              f"({counts.get('high_confidence_matches', 0)} high confidence)")
        sharia_counts = counts.get("sharia", {})
        if sharia_counts:
            rendered = ", ".join(f"{k}={v}" for k, v in sorted(sharia_counts.items()))
            print(f"  sharia verdicts    {rendered}")

        top = result.shortlist[:5]
        if top:
            print()
            print("  Top of the shortlist:")
            for position, card in enumerate(top, start=1):
                assessment = result.assessments.get(card.symbol)
                verdict = assessment.verdict.value if assessment else "n/a"
                print(f"    {position}. {card.symbol:<8} {card.total:5.1f}  "
                      f"{card.confidence:<8} sharia={verdict}")

        for warning in result.warnings:
            print(f"  warning: {warning}", file=sys.stderr)

        if result.report_path:
            print()
            print(f"Report: {result.report_path}")
            print(f"Data:   {result.json_path}")
    else:
        if result.report_path:
            print(result.report_path)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    cfg = _load(args)
    if args.json:
        path = pipeline.latest_json(cfg)
        if not path:
            print("No digest has been generated yet. Run: python -m crypto_advisor run",
                  file=sys.stderr)
            return 1
        payload = pipeline.load_json(path)
        if args.section:
            payload = payload.get(args.section, {})
        print(json.dumps(payload, indent=2, default=str))
        return 0

    path = pipeline.latest_report(cfg)
    if not path:
        print("No digest has been generated yet. Run: python -m crypto_advisor run",
              file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    print(f"# {path}\n")
    print(text)
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    print(f"crypto_advisor {__version__}")
    print(f"python          {sys.version.split()[0]} at {sys.executable}")
    print()

    config_path = Path(args.config) if args.config else config_mod.DEFAULT_CONFIG_PATH
    print(f"config          {config_path} "
          f"({'found' if config_path.exists() else 'MISSING'})")

    try:
        cfg = config_mod.load(args.config)
    except config_mod.ConfigError as exc:
        print(f"  error: {exc}", file=sys.stderr)
        return 2

    problems = config_mod.validate(cfg)
    if problems:
        print("  configuration problems:")
        for problem in problems:
            print(f"    - {problem}")
    else:
        print("  configuration is valid")

    print(f"database        {cfg.db_path}")
    print(f"reports         {cfg.report_dir}")
    print(f"timezone        {cfg.general.timezone} -> {cfg.tz} "
          f"(tz database {'present' if config_mod.tz_database_available() else 'MISSING'})")
    for warning in getattr(cfg, "warnings", []):
        print(f"  warning: {warning}")
    print()

    print("Connectivity:")
    from .http import head
    from . import sources  # noqa: F401

    probes = [
        ("CoinPaprika (market caps)",
         "https://api.coinpaprika.com/v1/global"),
        ("Binance (exchange status)",
         "https://api.binance.com/api/v3/ping"),
        ("DefiLlama (protocol data)",
         "https://api.llama.fi/protocols"),
        ("alternative.me (sentiment)",
         "https://api.alternative.me/fng/?limit=1"),
    ]
    failures = 0
    for label, url in probes:
        try:
            result = head(url, timeout=20)
            status = result.get("status")
            print(f"  OK    {label:<30} HTTP {status}")
        except Exception as exc:
            failures += 1
            print(f"  FAIL  {label:<30} {type(exc).__name__}: {exc}")

    print()
    if failures == 0:
        print("All sources reachable.")
    else:
        print(f"{failures} source(s) unreachable. The tool falls back to cached data "
              "where it can, but a full first run needs all of them.")
    return 0 if failures < len(probes) else 1


def cmd_rules(args: argparse.Namespace) -> int:
    print("Sharia rule engine")
    print("=" * 78)
    print()
    for rule in sharia_rules.RULES:
        categories = ", ".join(sorted(rule.categories)) or "-"
        symbols = ", ".join(sorted(rule.symbols)) or "-"
        print(f"{rule.id}  {rule.label}")
        print(f"  concern   {rule.concern}")
        print(f"  severity  {rule.severity}    position: {rule.position}")
        print(f"  triggers  categories: {categories}")
        print(f"            symbols:    {symbols}")
        print()
    print("Usage rules (apply to how any asset is used, not to the asset)")
    print("-" * 78)
    for rule in sharia_rules.USAGE_RULES:
        print(f"{rule.id}  {rule.label}  ({rule.concern}, {rule.severity})")
    print()
    coverage = sharia_knowledge.describe_coverage()
    print("Curated knowledge base")
    print("-" * 78)
    print(f"  asset classes: {', '.join(coverage['class_entries'])}")
    print(f"  symbols:       {', '.join(coverage['symbol_entries'])}")
    print(f"  {coverage['verification_note']}")
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    cfg = _load(args)
    from .store import Store

    print("Data sources")
    print("=" * 78)
    print("  CoinPaprika   market caps, ranks, prices (whole market, one call)")
    print("  Binance       OHLCV history, order books, 24h tickers, listing dates")
    print("  DefiLlama     protocol revenue, TVL, categories, stablecoins")
    print("  alternative.me  Fear & Greed index")
    print("  mempool.space   Bitcoin network fees (context only)")
    print()
    print("Cache and history")
    print("-" * 78)
    if not Path(cfg.db_path).exists():
        print("  No database yet. Run: python -m crypto_advisor run")
        return 0
    with Store(cfg.db_path) as store:
        stats = store.stats()
        for key, value in stats.items():
            if key == "cache_bytes":
                print(f"  {key:<18} {value / 1e6:,.2f} MB")
            else:
                print(f"  {key:<18} {value:,}")
        if args.purge:
            removed = store.purge_cache(args.provider)
            print(f"\n  purged {removed} cache entries")
        print()
        rows = store.cache_stats()
        if rows:
            print("  by provider:")
            for row in rows:
                print(f"    {row['provider']:<12} {row['entries']:>5} entries  "
                      f"{row['bytes'] / 1e6:>8.2f} MB")
    return 0


def cmd_task(args: argparse.Namespace) -> int:
    cfg = _load(args)
    root = Path(cfg.root)
    launcher = root / LAUNCHER_NAME
    python = Path(sys.executable)

    if args.remove:
        command = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
        print(" ".join(command))
        completed = subprocess.run(command, capture_output=True, text=True)
        sys.stdout.write(completed.stdout)
        sys.stderr.write(completed.stderr)
        return completed.returncode

    if not args.install:
        print("Nothing to do. Use --install to register the daily digest, or "
              "--remove to delete it.")
        print(f"\nThe task would run: {python} {launcher}")
        return 0

    if not launcher.exists():
        launcher.write_text(LAUNCHER_TEMPLATE, encoding="utf-8")
        print(f"Created launcher {launcher}")

    command = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{python}" "{launcher}"',
        "/SC", "DAILY",
        "/ST", args.time,
        "/F",
    ]
    print("Registering the daily digest:")
    print("  " + " ".join(command))
    completed = subprocess.run(command, capture_output=True, text=True)
    sys.stdout.write(completed.stdout)
    sys.stderr.write(completed.stderr)

    if completed.returncode == 0:
        print()
        print(f"Scheduled task '{TASK_NAME}' will run daily at {args.time}.")
        print("Reports land in:")
        print(f"  {cfg.report_dir}")
        print()
        print("To change the time later, re-run this command with a new --time.")
    else:
        print()
        print("Registration failed. Task Scheduler is not reachable from this "
              "process, which usually means it needs a normal (non-restricted) "
              "PowerShell window. Open PowerShell yourself and run the command "
              "printed above, or run the digest by hand with:")
        print(f'  "{python}" "{launcher}"')
        print()
        print(f"The launcher at {launcher} is ready either way.")
    return completed.returncode


def cmd_config(args: argparse.Namespace) -> int:
    cfg = _load(args)
    print(config_mod.describe(cfg))
    return 0


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crypto_advisor",
        description=(
            "Research and screening tool for crypto assets, with a separate "
            "Sharia screen that reports published scholarly positions. "
            "Not investment advice and not a fatwa."
        ),
    )
    parser.add_argument("--version", action="version", version=f"crypto_advisor {__version__}")
    parser.add_argument("-c", "--config", help="path to config.toml", default=None)
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="run a full research pass and write the digest")
    run.add_argument("--limit", type=int, default=None,
                     help="cap the number of assets analysed (useful for a first test)")
    run.add_argument("--verbose", action="store_true", help="progress output")
    run.add_argument("--quiet", action="store_true",
                     help="print only the report path (used by the scheduled task)")
    run.add_argument("--no-write", action="store_true",
                     help="skip writing the report files and the database snapshot")
    run.set_defaults(func=cmd_run)

    show = sub.add_parser("show", help="print the most recent digest")
    show.add_argument("--json", action="store_true", help="print the JSON instead")
    show.add_argument("--section", default=None,
                      help="with --json, print only this top-level section")
    show.set_defaults(func=cmd_show)

    doctor = sub.add_parser("doctor", help="check configuration and connectivity")
    doctor.set_defaults(func=cmd_doctor)

    rules = sub.add_parser("rules", help="list the Sharia rules and knowledge coverage")
    rules.set_defaults(func=cmd_rules)

    sources = sub.add_parser("sources", help="show data sources and cache state")
    sources.add_argument("--purge", action="store_true", help="clear the cache")
    sources.add_argument("--provider", default=None,
                         help="with --purge, restrict to one provider")
    sources.set_defaults(func=cmd_sources)

    task = sub.add_parser("task", help="register the daily digest as a Windows task")
    task.add_argument("--install", action="store_true", help="create the scheduled task")
    task.add_argument("--remove", action="store_true", help="delete the scheduled task")
    task.add_argument("--time", default="07:00", help="24h local time, e.g. 07:00")
    task.set_defaults(func=cmd_task)

    config_cmd = sub.add_parser("config", help="show the effective configuration")
    config_cmd.set_defaults(func=cmd_config)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not getattr(args, "command", None):
        # Bare invocation behaves like `run`, which is what people expect.
        return cmd_run(parser.parse_args(["run"]))

    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except config_mod.ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

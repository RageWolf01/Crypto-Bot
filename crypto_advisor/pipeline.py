"""Orchestration: fetch, score, screen, report, persist.

This is the only module that knows the order of operations. Everything it calls is
independently testable, which matters because the interesting failures in a tool
like this are not crashes -- they are a run that quietly analyses nine assets
because an API started refusing requests.

So the pipeline treats thin data as a first-class outcome: it counts what it could
not measure, carries those counts into the report, and marks the run's status
accordingly rather than printing a confident table over an empty dataset.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from . import report as report_mod
from . import universe
from .http import Fetcher
from .model import Asset, ScoreCard
from .quant import regime as regime_mod
from .quant import score as score_mod
from .sharia import screen as sharia_screen
from .sharia.types import ShariaAssessment
from .sources import binance
from .store import Store, utcnow


@dataclass
class RunResult:
    run_id: int
    started: datetime
    finished: datetime
    report_path: Path | None = None
    json_path: Path | None = None
    assets: list[Asset] = field(default_factory=list)
    cards: list[ScoreCard] = field(default_factory=list)
    assessments: dict[str, ShariaAssessment] = field(default_factory=dict)
    regime: Any = None
    selection: Any = None
    warnings: list[str] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)

    @property
    def shortlist(self) -> list[ScoreCard]:
        return [c for c in self.cards if not c.disqualified]

    @property
    def disqualified(self) -> list[ScoreCard]:
        return [c for c in self.cards if c.disqualified]


def _btc_bars(assets: list[Asset], fetcher: Fetcher) -> list[binance.Bar]:
    """Regime needs BTC history; reuse it if BTC is in the universe, else fetch."""
    for asset in assets:
        if asset.symbol.upper() == "BTC" and asset.bars:
            return asset.bars
    try:
        return binance.klines_daily(fetcher, "BTCUSDT", 1000)
    except Exception:
        return []


def _snapshot_records(assets: list[Asset]) -> list[dict[str, Any]]:
    return [
        {
            "symbol": a.symbol,
            "name": a.name,
            "rank": a.rank,
            "price_usd": a.price,
            "market_cap": a.market_cap,
            "volume_24h": a.median_volume_30d or a.quote_volume_24h,
        }
        for a in assets
    ]


def _score_records(cards: list[ScoreCard], assessments: dict[str, ShariaAssessment]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for card in cards:
        assessment = assessments.get(card.symbol)
        records.append(
            {
                "symbol": card.symbol,
                "composite": card.total,
                "grade": card.confidence,
                "disqualified": card.disqualified,
                "reasons": card.disqualifications,
                "flags": card.flags,
                "sharia_verdict": assessment.verdict.value if assessment else None,
                "sharia_class": assessment.asset_class if assessment else None,
            }
        )
    return records


def _json_payload(
    *,
    result: RunResult,
    cfg: Any,
    fetcher: Fetcher,
) -> dict[str, Any]:
    by_symbol = {a.symbol.upper(): a for a in result.assets}
    active = result.shortlist
    top_n = int(getattr(cfg.report, "top_n", 12))

    def asset_row(card: ScoreCard) -> dict[str, Any]:
        asset = by_symbol.get(card.symbol)
        assessment = result.assessments.get(card.symbol)
        row: dict[str, Any] = {
            "symbol": card.symbol,
            "name": card.name,
            "rank": card.rank,
            "composite": round(card.total, 2),
            "confidence": card.confidence,
            "coverage": round(card.coverage, 3),
            "disqualified": card.disqualified,
            "disqualifications": card.disqualifications,
            "flags": card.flags,
            "factors": {
                f.name: {
                    "score": round(f.score, 3),
                    "weight": f.weight,
                    "coverage": round(f.coverage, 3),
                    "metrics": f.metrics,
                }
                for f in card.factors
            },
        }
        if asset is not None:
            row["market"] = {
                "price": asset.price,
                "market_cap": asset.market_cap,
                "fdv": asset.fdv,
                "fdv_to_mcap": asset.fdv_to_mcap,
                "turnover": asset.turnover,
                "pct_change_30d": asset.pct_change_30d,
                "pct_change_1y": asset.pct_change_1y,
                "pct_from_ath": asset.pct_from_ath,
                "median_volume_30d": asset.median_volume_30d,
                "age_days": asset.age_days,
                "revenue_annualized": asset.revenue_annualized,
                "tvl": asset.tvl,
                "chains": asset.chains,
            }
            if asset.book is not None:
                row["book"] = {
                    "bid_depth_usd": asset.book.bid_depth_usd,
                    "ask_depth_usd": asset.book.ask_depth_usd,
                    "spread_bps": asset.book.spread_bps,
                    "imbalance": asset.book.imbalance,
                }
            row["data_warnings"] = asset.data_warnings
        if assessment is not None:
            row["sharia"] = {
                "verdict": assessment.verdict.value,
                "confidence": assessment.confidence,
                "asset_class": assessment.asset_class,
                "concerns": assessment.concerns,
                "rules": [
                    {
                        "id": h.rule_id,
                        "label": h.label,
                        "concern": h.concern,
                        "severity": h.severity,
                    }
                    for h in assessment.rule_hits
                ],
                "open_questions": assessment.open_questions,
                "positions": [
                    {
                        "who": p.who,
                        "stance": p.stance.value,
                        "summary": p.summary,
                        "sources": list(p.sources),
                    }
                    for p in assessment.positions
                ],
                "sources": [s.url for s in assessment.sources],
                "source_details": [
                    {
                        "title": s.title,
                        "publisher": s.publisher,
                        "url": s.url,
                        "note": s.note,
                    }
                    for s in assessment.sources
                ],
            }
        return row

    return {
        "generated": result.finished.isoformat(),
        "run_id": result.run_id,
        "counts": result.counts,
        "warnings": result.warnings,
        "regime": result.regime.as_dict() if result.regime else None,
        "shortlist": [asset_row(c) for c in active[:top_n]],
        "disqualified": [asset_row(c) for c in result.disqualified],
        "sharia": {
            "summary": sharia_screen.summarise(result.assessments),
            "landscape": sharia_screen.landscape(),
            "usage_rules": sharia_screen.usage_rules(),
            "standards": sharia_screen.standards_note(),
        },
        "quality": universe.summarise(result.assets),
        "fetch": fetcher.stats.as_dict(),
    }


def run(
    cfg: Any,
    *,
    limit: int | None = None,
    verbose: bool = False,
    write: bool = True,
    on_progress: Callable[[str], None] | None = None,
) -> RunResult:
    """Execute a full research pass and write the digest."""
    started = utcnow()
    warnings: list[str] = list(getattr(cfg, "warnings", []))

    def say(message: str) -> None:
        if verbose:
            print(message)
        if on_progress is not None:
            on_progress(message)

    report_dir = Path(cfg.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    with Store(cfg.db_path) as store:
        run_id = store.start_run()
        fetcher = Fetcher(store, cfg, verbose=verbose)

        try:
            say("Building universe ...")
            selection = universe.build(
                cfg, fetcher, limit=limit, verbose=verbose, on_progress=on_progress
            )
            assets = selection.assets

            if not assets:
                raise RuntimeError(
                    "No assets could be assembled. Check connectivity and the "
                    "minimum market-cap setting."
                )

            say(f"Assessing market regime over {len(assets)} assets ...")
            regime = regime_mod.assess(fetcher, cfg, _btc_bars(assets, fetcher))

            say("Scoring ...")
            cards = score_mod.score_universe(assets, cfg)

            say("Running the Sharia screen ...")
            assessments = sharia_screen.assess_many(assets, cfg)

            result = RunResult(
                run_id=run_id,
                started=started,
                finished=utcnow(),
                assets=assets,
                cards=cards,
                assessments=assessments,
                regime=regime,
                selection=selection,
                warnings=warnings,
            )

            active = result.shortlist
            sharia_summary = sharia_screen.summarise(assessments)
            result.counts = {
                "considered": selection.considered,
                "analysed": len(assets),
                "passed_gates": len(active),
                "disqualified": len(result.disqualified),
                "protocol_matches": selection.matched_protocols,
                "high_confidence_matches": selection.high_confidence_matches,
                "sharia": sharia_summary.get("by_verdict", {}),
            }

            # Thin data is a finding, not a footnote.
            if len(assets) < max(5, int(cfg.general.universe_size) // 2):
                warnings.append(
                    f"Only {len(assets)} assets were analysed against a target of "
                    f"{cfg.general.universe_size}. Treat the ranking as provisional."
                )
            if not active:
                warnings.append(
                    "Every asset failed the hard gates. This usually means a data "
                    "problem rather than a market with nothing investable in it."
                )
            if sharia_summary.get("unknown_classification", 0) > len(assessments) * 0.5:
                warnings.append(
                    "More than half the universe had no independent business-activity "
                    "classification, so the Sharia sector screen was largely blind."
                )

            if write:
                stamp = result.finished.strftime("%Y-%m-%d")
                report_path = report_dir / f"digest-{stamp}.md"
                json_path = Path(cfg.report_dir) / f"digest-{stamp}.json"

                report_path.write_text(
                    report_mod.build(
                        cfg,
                        assets=assets,
                        cards=cards,
                        assessments=assessments,
                        regime=regime,
                        selection=selection,
                        fetcher=fetcher,
                        run_id=f"run-{run_id}",
                        generated=result.finished,
                    ),
                    encoding="utf-8",
                )
                json_path.write_text(
                    json.dumps(_json_payload(result=result, cfg=cfg, fetcher=fetcher),
                               indent=2, default=str),
                    encoding="utf-8",
                )
                result.report_path = report_path
                result.json_path = json_path

                store.save_snapshot(stamp, _snapshot_records(assets))
                store.save_scores(run_id, _score_records(cards, assessments))

            summary = (
                f"{len(assets)} analysed, {len(active)} passed gates, "
                f"{len(result.disqualified)} disqualified"
            )
            store.finish_run(run_id, "ok", warnings + fetcher.warnings, summary)
            return result

        except Exception as exc:
            store.finish_run(run_id, "failed", warnings + [f"{type(exc).__name__}: {exc}"])
            raise


def load_json(path: str | Path) -> dict[str, Any]:
    """Read a digest JSON file, for the ``show`` command and ad-hoc querying."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def latest_json(cfg: Any) -> Path | None:
    report_dir = Path(cfg.report_dir)
    if not report_dir.exists():
        return None
    files = sorted(report_dir.glob("digest-*.json"))
    return files[-1] if files else None


def latest_report(cfg: Any) -> Path | None:
    report_dir = Path(cfg.report_dir)
    if not report_dir.exists():
        return None
    files = sorted(report_dir.glob("digest-*.md"))
    return files[-1] if files else None

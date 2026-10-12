"""The Sharia screen: combine transparent rules with cited scholarly positions.

Design principle, stated plainly because it drives everything: **the rules and the
curated positions are shown separately and never silently merged into one
authoritative voice.** A reader can see which part is a mechanical mapping from an
independent classification (DefiLlama's category) and which part is a summary of
what a named scholar published.

The verdict is then resolved by a deliberately asymmetric rule:

* A **fatal** rule hit always produces ``NON_COMPLIANT``. No curated position can
  talk the screen out of a Ponzi classification or an outright prohibition.
* A curated position, where one exists, sets the verdict -- but it can only be
  *escalated* toward caution by the rules, never softened. If the curated entry
  says permissible and a major concern fires, the result is ``DISPUTED``.
* With no curated position and no major concern, the result is ``UNCLASSIFIED``,
  never ``COMPLIANT``.

That last point is the whole reason this module exists in this shape. A screener
that returns "permissible" because it failed to find anything is worse than
useless: it converts an absence of evidence into a religious verdict.
"""

from __future__ import annotations

from typing import Any

from ..model import Asset
from . import knowledge, rules
from .types import Position, RuleHit, ShariaAssessment, Source, Verdict

#: Concerns that, when they fire, mean the sector screen could not be trusted
#: to have caught the asset's actual activity.
_BLIND_SPOT_WARNING = (
    "No independent business-activity classification was available for this "
    "asset, so the sector screen could not run. This is a blind spot, not a "
    "clean bill of health."
)


def _collect_sources(
    entry: knowledge.Entry | None,
    hits: list[RuleHit],
    extras: list[knowledge.Entry] | None = None,
) -> list[Source]:
    """Every source this assessment rests on.

    Three places cite things, and all three have to be gathered or the report
    prints an assertion with nothing behind it: the entry's own `sources`, the
    `sources` attached to each individual scholarly position, and the URLs a
    fired rule names.
    """
    found: dict[str, Source] = {}
    for record in ([entry] if entry else []) + list(extras or []):
        for src in record.sources:
            found.setdefault(src.url, src)
        for position in record.positions:
            for url in position.sources:
                found.setdefault(url, knowledge.source_for(url))
    known = {s.url: s for s in knowledge.all_sources()}
    for hit in hits:
        for url in hit.sources:
            if url in found:
                continue
            found[url] = known.get(url, Source(title="Cited source", url=url))
    # Swap in the richer known record wherever we have one.
    return [known.get(url, src) for url, src in found.items()]


def _resolve(
    entry: knowledge.Entry | None, hits: list[RuleHit]
) -> tuple[Verdict, str, list[str]]:
    """Decide the verdict, and record *why* in the rationale."""
    fatal = [h for h in hits if h.is_fatal]
    major = [h for h in hits if h.is_major]
    rationale: list[str] = []

    if fatal:
        labels = ", ".join(h.label for h in fatal)
        rationale.append(
            f"A disqualifying concern applies ({labels}). This is treated as "
            "impermissible regardless of the other positions, because the "
            "objection is to the activity itself rather than a matter of "
            "scholarly disagreement."
        )
        return Verdict.NON_COMPLIANT, "high", rationale

    if entry is not None:
        verdict = entry.verdict
        if verdict is Verdict.COMPLIANT and major:
            verdict = Verdict.DISPUTED
            rationale.append(
                "Although a permitting position exists for this class, a live "
                "concern also fires, so the result is reported as disputed rather "
                "than permissible."
            )
        return verdict, entry.confidence, rationale

    if major:
        rationale.append(
            "No curated scholarly position covers this asset, but one or more "
            "recognised concerns apply, so it is reported as disputed."
        )
        return Verdict.DISPUTED, "low", rationale

    rationale.append(
        "This asset matched no curated position and triggered no rule. It is "
        "reported as unclassified rather than permissible: the absence of a "
        "finding is not a finding of absence, and this tool has no basis to rule "
        "on it."
    )
    return Verdict.UNCLASSIFIED, "very low", rationale


def assess(asset: Asset, cfg: Any = None) -> ShariaAssessment:
    """Screen one asset."""
    symbol = asset.symbol.upper()
    asset_class = rules.classify(asset)
    hits = rules.evaluate(asset)
    entry = knowledge.lookup(asset_class, symbol)

    verdict, confidence, rationale = _resolve(entry, hits)

    # The sector screen is only as good as the classification behind it. Say so
    # rather than letting an uninformative category look like a clean result.
    if not asset.defillama_categories and not asset.is_stablecoin:
        rationale.append(_BLIND_SPOT_WARNING)
        if confidence in ("high", "medium"):
            confidence = "low"

    if entry is not None:
        rationale.insert(0, entry.summary)
        rationale.extend(entry.rationale)

    for hit in hits:
        rationale.append(f"{hit.label} ({hit.concern}, {hit.severity}): {hit.detail}")

    open_questions = list(entry.open_questions) if entry else []
    if entry is None:
        open_questions.extend(knowledge.CORE_QUESTIONS[:3])
    if asset.is_stablecoin:
        peg = asset.stablecoin or {}
        mechanism = str(peg.get("peg_mechanism") or "").lower()
        if "algorithmic" in mechanism or not peg.get("circulating_usd"):
            open_questions.append(
                "What actually backs this peg, and can it be independently verified?"
            )

    # A symbol entry adds specificity but does not replace the general positions:
    # a scholar writing about "smart-contract platform assets" is plainly
    # addressing ETH, so dropping those positions because a more specific entry
    # exists would hide relevant disagreement.
    positions: list[Position] = []
    seen_positions: set[tuple[str, str]] = set()
    candidates: list[knowledge.Entry] = []
    if entry is not None:
        candidates.append(entry)
    for class_entry in knowledge.entries_for_class(asset_class):
        if class_entry is not entry:
            candidates.append(class_entry)
    for candidate in candidates:
        for position in candidate.positions:
            marker = (position.who.strip().lower(), position.stance.value)
            if marker not in seen_positions:
                seen_positions.add(marker)
                positions.append(position)

    if entry is not None and not entry.positions and positions:
        rationale.append(
            "The positions below are stated for this asset class rather than for "
            "this token specifically."
        )

    return ShariaAssessment(
        symbol=symbol,
        name=asset.name,
        asset_class=asset_class,
        verdict=verdict,
        confidence=confidence,
        rule_hits=hits,
        positions=positions,
        sources=_collect_sources(entry, hits, [c for c in candidates if c is not entry]),
        rationale=rationale,
        open_questions=open_questions,
        purification_note=entry.purification_note if entry else None,
    )


def assess_many(assets: list[Asset], cfg: Any = None) -> dict[str, ShariaAssessment]:
    return {asset.symbol.upper(): assess(asset, cfg) for asset in assets}


def usage_rules() -> list[dict[str, Any]]:
    """The prohibitions that apply to how *any* asset is used, not to the asset.

    Reported once per digest rather than repeated on every row, because these are
    the findings that matter most and repetition is how they stop being read.
    """
    return [
        {
            "id": rule.id,
            "label": rule.label,
            "concern": rule.concern,
            "severity": rule.severity,
            "position": rule.position,
            "detail": rule.detail,
            "sources": list(rule.sources),
        }
        for rule in rules.USAGE_RULES
    ]


def landscape() -> dict[str, Any]:
    """The state of scholarly disagreement, for the digest header."""
    return knowledge.LANDSCAPE.as_dict()


def standards_note() -> dict[str, Any]:
    """What standard exists, and what does not. Prevents mistaken citation."""
    return {
        "aaoifi_crypto_standard": None,
        "note": (
            "AAOIFI has not issued a final Shariah standard on cryptocurrency. "
            "Its Shari'a Standard No. 21 quantitative screens were written for "
            "equities, and any application to tokens is an analogy rather than a "
            "standard."
        ),
        "equity_analogy_thresholds": {
            "interest_bearing_debt_pct_of_market_cap": 30.0,
            "interest_bearing_securities_pct_of_market_cap": 30.0,
            "non_permissible_income_pct_of_revenue": 5.0,
            "source": knowledge.SRC_AAOIFI_SS21.url,
        },
        "verification_note": knowledge.VERIFICATION_NOTE,
    }


def summarise(assessments: dict[str, ShariaAssessment]) -> dict[str, Any]:
    counts: dict[str, int] = {v.value: 0 for v in Verdict}
    for assessment in assessments.values():
        counts[assessment.verdict.value] += 1
    disputed = [
        s.symbol for s in assessments.values() if s.verdict is Verdict.DISPUTED
    ]
    unclassified = [
        s.symbol for s in assessments.values() if s.verdict is Verdict.UNCLASSIFIED
    ]
    return {
        "total": len(assessments),
        "by_verdict": counts,
        "disputed": disputed[:25],
        "unclassified": unclassified[:25],
        "unknown_classification": sum(
            1 for s in assessments.values() if s.asset_class == "unclassified"
        ),
    }

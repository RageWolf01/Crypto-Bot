"""Sharia screening: transparent rules plus curated, cited scholarly positions.

Read :mod:`crypto_advisor.sharia.screen` for why the verdict resolution is
deliberately asymmetric, and :mod:`crypto_advisor.sharia.knowledge` for the
positions themselves and the caveats attached to each source.
"""

from .knowledge import LANDSCAPE, Entry, all_sources, describe_coverage, lookup
from .rules import RULES, USAGE_RULES, classify, describe_rules, evaluate
from .screen import (
    assess,
    assess_many,
    landscape,
    standards_note,
    summarise,
    usage_rules,
)
from .types import Position, RuleHit, ShariaAssessment, Source, Stance, Verdict

__all__ = [
    "LANDSCAPE",
    "RULES",
    "USAGE_RULES",
    "Entry",
    "Position",
    "RuleHit",
    "ShariaAssessment",
    "Source",
    "Stance",
    "Verdict",
    "all_sources",
    "assess",
    "assess_many",
    "classify",
    "describe_coverage",
    "describe_rules",
    "evaluate",
    "landscape",
    "lookup",
    "standards_note",
    "summarise",
    "usage_rules",
]

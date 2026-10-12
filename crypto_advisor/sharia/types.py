"""Data shapes for the Sharia screen.

The most important thing in this file is the ``Verdict`` enum, and specifically
that ``COMPLIANT`` is **never** produced by the absence of a problem.

Classical screening (AAOIFI, Dow Jones Islamic Market, FTSE, MSCI) has settled
thresholds for equities. Cryptocurrency has no equivalent: there is no agreed
standard, and the scholarly positions genuinely conflict. So this tool reports
positions rather than issuing rulings, and its default for anything it cannot
place is ``UNCLASSIFIED``.

An unknown token must never drift into looking permissible by omission.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    """The overall stance. Deliberately not a boolean."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    DISPUTED = "disputed"
    UNCLASSIFIED = "unclassified"

    @property
    def label(self) -> str:
        return {
            "compliant": "Permissible per cited positions",
            "non_compliant": "Impermissible per cited positions",
            "disputed": "Disputed among scholars",
            "unclassified": "Unclassified - no reliable basis",
        }[self.value]


class Stance(str, Enum):
    """What a particular scholar or body concludes."""

    PERMISSIBLE = "permissible"
    IMPERMISSIBLE = "impermissible"
    CONDITIONAL = "conditional"
    CONTEXT_DEPENDENT = "context_dependent"


#: How badly a single rule hit damages the case.
#: ``fatal``     -- makes the asset impermissible under essentially every view.
#: ``major``     -- a genuine, live disagreement between schools.
#: ``minor``     -- a caveat that a scholar would want to address.
#: ``info``      -- context, not a problem.
SEVERITIES = ("fatal", "major", "minor", "info")


@dataclass(frozen=True)
class Source:
    """A citable source. No assertion in this tool should be unciteable."""

    title: str
    url: str
    publisher: str = ""
    note: str = ""

    def as_markdown(self) -> str:
        label = self.title
        if self.publisher:
            label = f"{self.title} - {self.publisher}"
        return f"[{label}]({self.url})"


@dataclass(frozen=True)
class Position:
    """One school's or body's stance, stated in its own terms."""

    who: str                       # e.g. "Mufti Faraz Adam (Amanah Advisors)"
    stance: Stance
    summary: str
    sources: tuple[str, ...] = ()  # URLs


@dataclass(frozen=True)
class RuleHit:
    """A single classical concern triggered by this asset."""

    rule_id: str
    label: str
    concern: str                   # riba | gharar | maysir | batil | haram_asset
    severity: str
    position: str                  # "non_compliant" | "disputed" | "compliant"
    detail: str
    sources: tuple[str, ...] = ()

    @property
    def is_fatal(self) -> bool:
        return self.severity == "fatal"

    @property
    def is_major(self) -> bool:
        return self.severity == "major"


@dataclass
class ShariaAssessment:
    """The full Sharia report for one asset."""

    symbol: str
    name: str
    asset_class: str
    verdict: Verdict
    confidence: str = "low"
    rule_hits: list[RuleHit] = field(default_factory=list)
    positions: list[Position] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    purification_note: str | None = None

    @property
    def fatal_hits(self) -> list[RuleHit]:
        return [h for h in self.rule_hits if h.is_fatal]

    @property
    def major_hits(self) -> list[RuleHit]:
        return [h for h in self.rule_hits if h.is_major]

    @property
    def concerns(self) -> list[str]:
        seen: list[str] = []
        for hit in self.rule_hits:
            if hit.concern not in seen:
                seen.append(hit.concern)
        return seen

    @property
    def disclaimer(self) -> str:
        return (
            "This is a research aid, not a fatwa. It reports what published "
            "scholars and standards bodies have said and applies transparent "
            "rules. It is not a substitute for asking a qualified scholar about "
            "your own situation."
        )

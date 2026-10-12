"""Quantitative layer: factors, hard disqualifiers, cross-sectional scoring, regime.

Nothing in here knows about Sharia rulings, and nothing in here renders output.
The separation is intentional -- see ``crypto_advisor/DECISIONS.md``.
"""

from .disqualifiers import check
from .factors import liquidity, momentum_raw, tokenomics, traction, valuation
from .regime import Regime, assess as assess_regime
from .score import ScoreCard, excluded, ranked, score_universe

__all__ = [
    "Regime",
    "ScoreCard",
    "assess_regime",
    "check",
    "excluded",
    "liquidity",
    "momentum_raw",
    "ranked",
    "score_universe",
    "tokenomics",
    "traction",
    "valuation",
]

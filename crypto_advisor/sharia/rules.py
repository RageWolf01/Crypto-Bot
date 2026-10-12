"""The rule engine: map a coin's actual business activity onto classical concerns.

The premise of this module is that **a coin's Sharia status is mostly determined
by what its protocol actually does**, and that the reliable way to learn what a
protocol does is to read an independent classification rather than a project's
own marketing.

That independent classification is DefiLlama's ``category`` field. It says
``Lending`` or ``Prediction Market`` or ``Basis Trading``, and those map onto
fiqh concerns far more defensibly than guessing:

* **riba**   -- interest. Lending markets, CDP stability fees, staked-asset
  yield, yield aggregators, basis/carry trades. The return is compensation for
  lending money or for assuming none of the risk.
* **gharar** -- excessive uncertainty. Derivatives, options, perps, leveraged
  farming, algorithmic pegs, tokenised claims whose backing is unverifiable.
* **maysir** -- gambling. Prediction markets, lotteries, and memecoins, whose
  value rests entirely on whether someone else will pay more later.
* **batil**  -- invalid/fraudulent. Protocols DefiLlama itself labels a Ponzi.

Two honest caveats are baked into the design.

First, **using a protocol and holding its token are different questions.** Using
a lending market is clearly an interest transaction. Holding the governance
token is an ownership stake in a business whose revenue comes from interest --
which is the same structure as holding shares in a conventional bank, a question
classical scholars *have* addressed at length. The rules below flag the concern
and record the distinction rather than collapsing it.

Second, **some concerns attach to how you use the asset, not to the asset.** A
Bitcoin spot holding is a different question from Bitcoin perpetual futures.
Those usage rules are in :data:`USAGE_RULES`, because they apply to every asset
in the report equally and repeating them per coin would be noise.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..model import Asset
from .types import RuleHit


@dataclass(frozen=True)
class Rule:
    id: str
    label: str
    concern: str
    severity: str          # fatal | major | minor | info
    position: str          # non_compliant | disputed | compliant
    detail: str
    categories: frozenset[str] = frozenset()
    symbols: frozenset[str] = frozenset()
    sources: tuple[str, ...] = ()
    #: True when the concern attaches to *using* the protocol, not to holding it.
    usage_only: bool = False


# ---------------------------------------------------------------------------
# Asset classification
# ---------------------------------------------------------------------------

#: DefiLlama category -> our coarse asset class. Only the first match is used.
CATEGORY_TO_CLASS = {
    "chain": "layer 1 / layer 2 network",
    "lending": "lending protocol",
    "cdp": "collateralised debt protocol",
    "liquid staking": "liquid staking derivative",
    "yield": "yield aggregator",
    "yield aggregator": "yield aggregator",
    "dexes": "decentralised exchange",
    "dex": "decentralised exchange",
    "dexs": "decentralised exchange",
    "oracles": "oracle / data infrastructure",
    "oracle": "oracle / data infrastructure",
    "bridge": "bridge infrastructure",
    "canonical bridge": "bridge infrastructure",
    "rwa": "real-world-asset token",
    "stablecoin issuer": "stablecoin issuer",
    "cex": "centralised exchange token",
    "meme": "meme coin",
    "prediction market": "prediction market",
    "derivatives": "derivatives venue",
    "options": "options venue",
    "basis trading": "basis trading / carry strategy",
    "leveraged farming": "leveraged yield strategy",
    "liquid restaking": "restaking derivative",
    "restaking": "restaking",
    "insurance": "insurance protocol",
    "services": "infrastructure service",
    "launchpad": "token launch platform",
    "nft marketplace": "NFT marketplace",
    "gaming": "gaming / metaverse",
    "indexes": "index product",
    "farm": "yield farming",
    "algo-stables": "algorithmic stablecoin",
    "cross chain": "cross-chain infrastructure",
    "privacy": "privacy infrastructure",
    "payments": "payments network",
}

#: Curated overrides for assets that have no DefiLlama protocol entry, because
#: their chain or protocol is not measured there. Kept small and explicit on
#: purpose: a long hard-coded list would rot, and it is better to fall back to
#: "unclassified" than to guess.
SYMBOL_ASSET_CLASS = {
    "BTC": "monetary / store-of-value asset",
    "LTC": "monetary / store-of-value asset",
    "BCH": "monetary / store-of-value asset",
    "XMR": "privacy-focused monetary asset",
    "ZEC": "privacy-focused monetary asset",
    "ETH": "smart-contract platform asset",
    "AVAX": "smart-contract platform asset",
    "ARB": "smart-contract platform asset",
    "OP": "smart-contract platform asset",
    "POL": "smart-contract platform asset",
    "MATIC": "smart-contract platform asset",
    "DOT": "smart-contract platform asset",
    "ATOM": "smart-contract platform asset",
    "NEAR": "smart-contract platform asset",
    "APT": "smart-contract platform asset",
    "SUI": "smart-contract platform asset",
    "TON": "smart-contract platform asset",
    "TIA": "smart-contract platform asset",
    "SEI": "smart-contract platform asset",
    "INJ": "smart-contract platform asset",
    "ALGO": "smart-contract platform asset",
    "ETC": "smart-contract platform asset",
    "FIL": "smart-contract platform asset",
    "STX": "smart-contract platform asset",
    "ICP": "smart-contract platform asset",
    "HBAR": "smart-contract platform asset",
    "VET": "smart-contract platform asset",
    "KAS": "smart-contract platform asset",
    "EGLD": "smart-contract platform asset",
    "FTM": "smart-contract platform asset",
    "S": "smart-contract platform asset",
    "BNB": "centralised exchange token",
    "XRP": "payments network asset",
    "ADA": "smart-contract platform asset",
    "SOL": "smart-contract platform asset",
    "TRX": "smart-contract platform asset",
    "DOGE": "meme coin",
    "SHIB": "meme coin",
    "PEPE": "meme coin",
    "WIF": "meme coin",
    "BONK": "meme coin",
    "FLOKI": "meme coin",
    "USDT": "stablecoin",
    "USDC": "stablecoin",
    "DAI": "stablecoin",
    "FDUSD": "stablecoin",
    "TUSD": "stablecoin",
    "USDE": "stablecoin",
    "PYUSD": "stablecoin",
}


def classify(asset: Asset) -> str:
    """Best-effort asset class. Falls back to the last DefiLlama category."""
    for category in asset.defillama_categories:
        mapped = CATEGORY_TO_CLASS.get(category.strip().lower())
        if mapped:
            return mapped
    if asset.is_stablecoin:
        return "stablecoin"
    if asset.symbol in SYMBOL_ASSET_CLASS:
        return SYMBOL_ASSET_CLASS[asset.symbol]
    if asset.defillama_categories:
        return asset.defillama_categories[0].lower()
    return "unclassified"


# ---------------------------------------------------------------------------
# Per-asset rules
# ---------------------------------------------------------------------------

S_AAOIFI = "https://aaoifi.com/shariaa-standards/"
S_FARAZ = "https://amanahadvisors.com/"
S_SRB = "https://www.srbh.org/"
S_ALLAM = "https://www.dar-alifta.org/"
S_DIYANET = "https://www.diyanet.gov.tr/"
S_MUFTI_TAQI = "https://muftitaqiusmani.com/"

RULES: tuple[Rule, ...] = (
    Rule(
        id="RQ-001",
        label="Revenue derived from interest (riba)",
        concern="riba",
        severity="major",
        position="disputed",
        categories=frozenset({"lending", "cdp", "yield", "yield aggregator", "farm",
                              "leveraged farming", "liquid staking", "restaking",
                              "liquid restaking", "basis trading"}),
        detail=(
            "This protocol's revenue comes from interest and similar compensation "
            "for lending capital. **Using** it is an interest-bearing transaction. "
            "**Holding its governance token** is an ownership stake in a business "
            "whose income is interest -- structurally the same question classical "
            "scholars have addressed for conventional banks, where the majority "
            "position permits holding shares subject to screening and purification "
            "of the interest-derived proportion of earnings."
        ),
        sources=(S_AAOIFI, S_FARAZ),
    ),
    Rule(
        id="RQ-002",
        label="Betting on outcomes (maysir)",
        concern="maysir",
        severity="major",
        position="disputed",
        categories=frozenset({"prediction market", "gambling", "lottery", "casino"}),
        detail=(
            "Outcome-based wagering. Classical maysir requires that the "
            "consideration be contingent on an uncertain event with no productive "
            "economic activity, which this plainly is."
        ),
        sources=(S_AAOIFI,),
    ),
    Rule(
        id="RQ-003",
        label="Derivatives and excessive uncertainty (gharar)",
        concern="gharar",
        severity="major",
        position="non_compliant",
        categories=frozenset({"derivatives", "options", "perpetuals", "synthetics",
                              "leveraged farming"}),
        detail=(
            "Derivative and leveraged structures are the clearest negative in this "
            "asset class, because the objection is to the contract form itself "
            "rather than to the underlying."
        ),
        sources=(S_AAOIFI, S_MUFTI_TAQI),
    ),
    Rule(
        id="RQ-004",
        label="Token is backed by interest-bearing instruments",
        concern="riba",
        severity="major",
        position="disputed",
        categories=frozenset({"stablecoin issuer", "algo-stables"}),
        symbols=frozenset({"USDC", "PYUSD", "TUSD", "FDUSD", "DAI", "USDE",
                           "USDT", "USDP", "GUSD"}),
        detail=(
            "Fiat-backed stablecoins are typically backed by short-term government "
            "debt and similar instruments, which yield interest to the issuer. "
            "Scholars differ on whether the holder's position is then tainted: some "
            "hold that the holder receives no interest themselves and that the "
            "token is merely a payment claim, others that the backing itself must "
            "be permissible."
        ),
        sources=(S_FARAZ,),
    ),
    Rule(
        id="RQ-005",
        label="No productive use case (maysir)",
        concern="maysir",
        severity="major",
        position="disputed",
        categories=frozenset({"meme"}),
        symbols=frozenset({"DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI"}),
        detail=(
            "This asset has no cash flow and no productive use. Its return depends "
            "entirely on reselling it to someone at a higher price, which is the "
            "structure of a zero-sum wager rather than a productive holding."
        ),
        sources=(S_ALLAM, S_MUFTI_TAQI),
    ),
    Rule(
        id="RQ-006",
        label="Independent classification is 'Ponzi'",
        concern="batil",
        severity="fatal",
        position="non_compliant",
        categories=frozenset({"ponzi"}),
        detail=(
            "DefiLlama, an independent data provider with no stake in the outcome, "
            "classifies this protocol as a Ponzi scheme. Fraudulent loss of "
            "property is impermissible regardless of the asset class."
        ),
        sources=(),
    ),
    Rule(
        id="RQ-007",
        label="Algorithmic or uncollateralised peg",
        concern="gharar",
        severity="major",
        position="disputed",
        categories=frozenset({"algo-stables"}),
        detail=(
            "A peg maintained by algorithm and market incentives rather than by "
            "collateral held in reserve. The holder cannot verify what stands "
            "behind the claim, which is the core of the gharar objection."
        ),
        sources=(S_AAOIFI,),
    ),
    Rule(
        id="RQ-008",
        label="Centralised exchange token",
        concern="riba",
        severity="minor",
        position="disputed",
        categories=frozenset({"cex"}),
        symbols=frozenset({"BNB", "OKB", "CRO", "KCS", "HT", "GT"}),
        detail=(
            "A claim on an off-chain business rather than a bearer asset. The "
            "issuer's revenue includes margin trading, futures and interest-earning "
            "products, so the token's value accrues partly from transactions the "
            "holder is not performing but does profit from."
        ),
        sources=(),
    ),
    Rule(
        id="RQ-009",
        label="Real-world-asset claim whose backing needs verification",
        concern="gharar",
        severity="minor",
        position="disputed",
        categories=frozenset({"rwa"}),
        detail=(
            "A tokenised claim on an off-chain asset. Whether it is permissible "
            "depends entirely on what is held, who custodies it, and whether the "
            "claim is legally enforceable -- none of which is visible from on-chain "
            "data. This needs case-by-case documentation, not a screener."
        ),
        sources=(S_AAOIFI,),
    ),
    Rule(
        id="RQ-010",
        label="Insurance and risk-transfer structure",
        concern="gharar",
        severity="minor",
        position="disputed",
        categories=frozenset({"insurance"}),
        detail=(
            "Conventional insurance contracts attract a gharar objection; the "
            "cooperative (takaful) model exists precisely to avoid it. Whether a "
            "given on-chain structure is takaful-like or conventional is a "
            "case-by-case question."
        ),
        sources=(S_AAOIFI,),
    ),
)


#: Concerns that apply to *how any asset in this report is used*, regardless of
#: which asset it is. These are stated once, globally, because repeating them on
#: every row would bury the per-asset findings.
USAGE_RULES: tuple[Rule, ...] = (
    Rule(
        id="UN-001",
        label="Leverage, margin and futures",
        concern="gharar",
        severity="fatal",
        position="non_compliant",
        detail=(
            "The prohibition here is essentially universal across schools and "
            "applies regardless of which coin is involved. You cannot sell what "
            "you do not own, and a contract whose settlement depends on a future "
            "price is gharar."
        ),
        sources=(S_AAOIFI, S_MUFTI_TAQI, S_ALLAM),
        usage_only=True,
    ),
    Rule(
        id="UN-002",
        label="Guaranteed or fixed 'earn' yield",
        concern="riba",
        severity="fatal",
        position="non_compliant",
        detail=(
            "Any product advertising a fixed or guaranteed return on a deposit is "
            "the definition of riba al-fadl / riba al-nasi'ah, whatever the asset "
            "it is denominated in."
        ),
        sources=(S_AAOIFI,),
        usage_only=True,
    ),
    Rule(
        id="UN-003",
        label="Day-trading on noise with no productive intent",
        concern="maysir",
        severity="minor",
        position="disputed",
        detail=(
            "Repeated short-horizon speculation is treated by many scholars as "
            "closer to gambling than investing, even when the underlying asset is "
            "permissible. Intent and holding period matter."
        ),
        sources=(S_ALLAM,),
        usage_only=True,
    ),
)


def evaluate(asset: Asset) -> list[RuleHit]:
    """Fire every per-asset rule whose category or symbol matches."""
    categories = {c.strip().lower() for c in asset.defillama_categories}
    hits: list[RuleHit] = []
    for rule in RULES:
        if rule.usage_only:
            continue
        matched = False
        if rule.categories and categories & rule.categories:
            matched = True
        if not matched and rule.symbols and asset.symbol.upper() in rule.symbols:
            matched = True
        if not matched:
            continue
        # Categories present on both sides, for a precise explanation.
        overlap = sorted(categories & rule.categories) if rule.categories else []
        detail = rule.detail
        if overlap:
            detail = f"{detail}\n\n(Triggered by DefiLlama category: {', '.join(overlap)}.)"
        hits.append(
            RuleHit(
                rule_id=rule.id,
                label=rule.label,
                concern=rule.concern,
                severity=rule.severity,
                position=rule.position,
                detail=detail,
                sources=rule.sources,
            )
        )
    return hits


def rule_index() -> dict[str, Rule]:
    return {rule.id: rule for rule in RULES}


def describe_rules() -> list[dict[str, Any]]:
    return [
        {
            "id": r.id,
            "label": r.label,
            "concern": r.concern,
            "severity": r.severity,
            "position": r.position,
        }
        for r in RULES
    ]

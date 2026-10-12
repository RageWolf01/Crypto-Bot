"""Curated, cited scholarly positions -- the part of the tool that must not invent.

Everything in this file is a *summary of a published position*, attached to a URL.
Where a position is known to me only through a secondary summary rather than the
primary fatwa text, the :class:`~crypto_advisor.sharia.types.Source` carries a
``note`` saying so, and the report prints that note. That distinction matters:
a screener that launders "some blog said" into "AAOIFI ruled" is worse than no
screener at all.

THE SINGLE MOST IMPORTANT FACT IN THIS FILE
-------------------------------------------
**AAOIFI has not issued a final Shariah standard on cryptocurrency.** Claims in
either direction -- that AAOIFI declared crypto halal, or that it declared it
haram -- are not accurate. AAOIFI has discussed digital assets, and its
accounting standards are referenced by some regional digital-asset regulations,
but no dedicated binding standard exists.

In the absence of a standard, the positions below genuinely conflict, and they
conflict on *principles*, not on details. So the tool reports the disagreement
rather than resolving it.

A NOTE ON THE EQUITIES PRECEDENT
--------------------------------
For shares, the industry has settled quantitative screens -- AAOIFI Shari'a
Standard No. 21 screens out companies whose interest-bearing debt exceeds 30% of
market capitalisation, whose interest-bearing securities exceed 30%, or whose
non-permissible income exceeds 5% of revenue. There is no agreed analogue for
tokens, and the differences are not cosmetic: a share is a claim on a going
concern with audited revenue, whereas a token may be a currency, a commodity, a
governance right, a fee claim, or nothing at all. Applying the equity thresholds
to tokens would be false precision, so this tool does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import Position, Source, Stance, Verdict

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

#: The caveat attached to any position I have not read in its primary form.
SECONDARY = "Summary of a secondary source; consult the primary text before relying on it."

SRC_AAOIFI_STANDARDS = Source(
    title="AAOIFI Shari'a Standards",
    url="https://aaoifi.com/shariaa-standards/",
    publisher="Accounting and Auditing Organization for Islamic Financial Institutions",
    note="No dedicated cryptocurrency standard has been issued as of 2026.",
)
SRC_AAOIFI_SS21 = Source(
    title="AAOIFI Shari'a Standard No. 21: Financial Papers (Shares and Bonds)",
    url="https://aaoifi.com/ss-21-financial-papers-shares-and-bonds/?lang=en",
    publisher="AAOIFI",
    note="Written for equities and bonds, not tokens. Quote it as an analogy only.",
)
SRC_IIFA_RES237 = Source(
    title="IIFA Resolution 237 (24/8) on electronic currencies, 24th session",
    url="https://iifa-aifi.org/en/resolutions",
    publisher="International Islamic Fiqh Academy (OIC), Dubai, November 2019",
    note=(
        "The Academy's operative resolution on electronic currencies. It called for "
        "further research rather than closing the question."
    ),
)
SRC_IIFA_2021 = Source(
    title="Closing Statement of the Digital Crypto-Currencies Symposium, Jeddah",
    url="https://iifa-aifi.org/en/28253.html",
    publisher="International Islamic Fiqh Academy (OIC), 8 November 2021",
    note=(
        "Fifteen papers were presented; the Secretariat postponed announcing "
        "recommendations pending revision, so this is not a resolving ruling."
    ),
)
SRC_USMANI = Source(
    title="Position of Mufti Muhammad Taqi Usmani on cryptocurrency",
    url="https://halalscreener.app/en/answers/aaoifi-cryptocurrency-ruling",
    publisher="secondary summary",
    note=(
        SECONDARY + " He is reported to consider trading impermissible in its "
        "current form because it is dominated by speculation rather than genuine "
        "use as a medium of exchange, while indicating the ruling could be "
        "revisited if crypto becomes tied to real economic activity."
    ),
)
SRC_DAR_ALIFTA = Source(
    title="Dar al-Ifta al-Misriyyah fatwa on Bitcoin (2017)",
    url="https://www.dar-alifta.org/",
    publisher="Egyptian Dar al-Ifta, Grand Mufti Shawki Allam",
    note=(
        SECONDARY + " Prohibits dealing in Bitcoin citing excessive uncertainty "
        "(gharar), extreme volatility, and the absence of a recognised issuing authority."
    ),
)
SRC_SISTANI = Source(
    title="Guidance on digital currencies",
    url="https://www.sistani.org/",
    publisher="Office of Grand Ayatollah Sayyid Ali al-Sistani",
    note=(
        SECONDARY + " Withholds a ruling on buying and selling virtual currencies "
        "and directs followers to the next most learned jurist; also stresses that "
        "local law regulating crypto must be respected."
    ),
)
SRC_FARAZ = Source(
    title="Mufti Faraz Adam, 'Bitcoin: Shariah Compliant?'",
    url="https://amanahadvisors.com/",
    publisher="Amanah Advisors",
    note=(
        "Research paper arguing Bitcoin satisfies the conditions of mal (wealth) "
        "and is acceptable as a medium of exchange. Amanah Advisors has also issued "
        "Shariah certifications for digital assets, so it is an interested party as "
        "well as a scholarly one."
    ),
)
SRC_SRB = Source(
    title="Shariah Review Bureau",
    url="https://www.srbh.org/",
    publisher="Shariah Review Bureau, Bahrain",
    note="Bahrain-based Shariah advisory firm that has taken a permitting stance on crypto assets.",
)
SRC_DIYANET = Source(
    title="Diyanet position on cryptocurrency",
    url="https://www.diyanet.gov.tr/",
    publisher="Presidency of Religious Affairs, Türkiye",
    note=SECONDARY + " Reported to hold cryptocurrency trading impermissible.",
)
SRC_AMJA = Source(
    title="Cryptocurrency: A Fiqh Analysis (AMJA 2022)",
    url=(
        "https://www.amjaonline.org/wp-content/uploads/2022/09/"
        "Topic-3-Cryptocurrency-A-Fiqh-Analysis-AMJA-2022-Zarabozo.pdf"
    ),
    publisher="Assembly of Muslim Jurists of America",
    note="A cautious, principle-by-principle fiqh analysis rather than a single verdict.",
)
SRC_SEEKERS_POS = Source(
    title="Is earning money via crypto proof-of-stake coins halal?",
    url=(
        "https://seekersguidance.org/answers/halal-and-haram/"
        "is-earning-money-via-crypto-proof-of-stake-coins-halal/"
    ),
    publisher="SeekersGuidance",
    note="Answers the staking-reward question specifically; full text was not retrievable.",
)
SRC_SEEKERS_BLOCKCHAIN = Source(
    title="If a blockchain uses proof of stake, does this make it impermissible for use?",
    url=(
        "https://seekersguidance.org/answers/transactions/"
        "if-a-blockchain-uses-a-proof-of-stake-mechanism-does-this-make-the-"
        "blockchain-impermissible-for-use/"
    ),
    publisher="SeekersGuidance",
    note="Distinguishes the mechanism from the user's own act -- the key distinction for staking.",
)
SRC_HALALSCREENER = Source(
    title="HalalScreener crypto screening methodology",
    url="https://halalscreener.app/en/methodology",
    publisher="HalalScreener",
    note=(
        "Applies AAOIFI Standard 21 to coins by analogy and screens each coin on "
        "function, the project behind it, and prohibited-use exposure. A commercial "
        "screener, so treated as one opinion among several."
    ),
)
SRC_XAUT = Source(
    title="Tether Gold (XAU₮) receives Shariah certification from Amanah Advisors",
    url=(
        "https://www.kucoin.com/es/news/flash/"
        "tether-gold-xaut-receives-shariah-certification-from-amanah-advisors"
    ),
    publisher="KuCoin news flash",
    note="Evidence that per-asset certification exists in practice, and who issues it.",
)

#: Every citable source, keyed by URL. Positions and rules store bare URLs, so
#: without this registry the report would print an assertion next to a link with
#: no title or publisher behind it.
SOURCE_REGISTRY = {
    src.url: src
    for src in (
        SRC_AAOIFI_STANDARDS,
        SRC_AAOIFI_SS21,
        SRC_IIFA_RES237,
        SRC_IIFA_2021,
        SRC_USMANI,
        SRC_DAR_ALIFTA,
        SRC_SISTANI,
        SRC_FARAZ,
        SRC_SRB,
        SRC_DIYANET,
        SRC_AMJA,
        SRC_SEEKERS_POS,
        SRC_SEEKERS_BLOCKCHAIN,
        SRC_HALALSCREENER,
        SRC_XAUT,
    )
}


def source_for(url: str) -> Source:
    """The titled source for a URL, or an honest placeholder if it is unknown."""
    found = SOURCE_REGISTRY.get(url)
    if found is not None:
        return found
    host = url.split("//", 1)[-1].split("/", 1)[0] if url else "unknown"
    return Source(title=f"Source at {host}", url=url)


# ---------------------------------------------------------------------------
# The general landscape: what is asked of every asset
# ---------------------------------------------------------------------------

VERIFICATION_NOTE = (
    "Positions below are summaries of published views with links, not rulings. "
    "Where a position is recorded from a secondary source, the link says so. "
    "Verify against the primary text before acting."
)

#: The questions a scholar has to answer for a token, in the order they matter.
CORE_QUESTIONS: tuple[str, ...] = (
    "Is the token mal (property) at all? Some scholars hold that a purely digital "
    "entry cannot be possessed and therefore cannot be sold.",
    "Is it thaman (currency) or sil'ah (a commodity)? The answer changes which "
    "rules on riba al-fadl and possession (qabd) apply.",
    "Is the gharar in its price tolerable? Every currency is volatile; the question "
    "is where volatility becomes disqualifying uncertainty.",
    "Does the holder receive anything riba-like? Validator or staking rewards, "
    "lending interest, and 'earn' products are three different questions that are "
    "frequently conflated.",
    "What does the network's economic activity consist of, and does the token's "
    "value accrue from prohibited activity?",
    "Is there an identifiable issuer or counterparty, and does the holder bear "
    "risk they cannot see?",
)

#: Categories of activity that are treated as prohibited with little or no
#: scholarly disagreement, and which therefore override any per-asset analysis.
NEAR_UNIVERSAL_PROHIBITIONS: tuple[str, ...] = (
    "Leveraged, margin and futures trading. The objection is to the contract, not "
    "the coin, and it is essentially unanimous.",
    "Fixed or guaranteed returns on deposited crypto ('earn' products). The "
    "definition of riba, whatever asset it is denominated in.",
    "memecoins and tokens with no use beyond resale. Widely treated as maysir.",
    "Financing or facilitating the above, even without doing them yourself.",
)


@dataclass(frozen=True)
class Landscape:
    """The disagreement, stated once, so every memo can reference it."""

    headline: str
    bodies: tuple[Position, ...]
    counts: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "headline": self.headline,
            "positions": [
                {
                    "who": p.who,
                    "stance": p.stance.value,
                    "summary": p.summary,
                    "sources": list(p.sources),
                }
                for p in self.bodies
            ],
        }


LANDSCAPE = Landscape(
    headline=(
        "There is no scholarly consensus on whether cryptocurrency is permissible, "
        "and AAOIFI has issued no final standard on it. Three broad positions are "
        "held by serious authorities."
    ),
    bodies=(
        Position(
            who="Mufti Faraz Adam (Amanah Advisors); Shariah Review Bureau (Bahrain)",
            stance=Stance.PERMISSIBLE,
            summary=(
                "Crypto assets can satisfy the conditions of mal and are acceptable "
                "as a medium of exchange, so spot ownership is permissible subject to "
                "the ordinary prohibitions on riba, gharar and maysir."
            ),
            sources=(SRC_FARAZ.url, SRC_SRB.url),
        ),
        Position(
            who="Dar al-Ifta al-Misriyyah (Grand Mufti Shawki Allam); Diyanet (Türkiye)",
            stance=Stance.IMPERMISSIBLE,
            summary=(
                "Dealing in Bitcoin is prohibited: the gharar is excessive, there is "
                "no recognised issuing authority standing behind the value, and the "
                "asset facilitates speculation and illicit use."
            ),
            sources=(SRC_DAR_ALIFTA.url, SRC_DIYANET.url),
        ),
        Position(
            who="Mufti Muhammad Taqi Usmani; International Islamic Fiqh Academy (OIC)",
            stance=Stance.CONDITIONAL,
            summary=(
                "Cautious. Mufti Taqi Usmani is reported to consider trading "
                "impermissible in its current speculative form but to leave the "
                "ruling open to revision if crypto becomes tied to real economic "
                "activity. The IIFA's 2019 resolution (237) called for further "
                "research and its 2021 symposium deferred its recommendations, so "
                "the Academy has not closed the question."
            ),
            sources=(SRC_USMANI.url, SRC_IIFA_RES237.url, SRC_IIFA_2021.url),
        ),
        Position(
            who="Office of Grand Ayatollah Sayyid Ali al-Sistani",
            stance=Stance.CONTEXT_DEPENDENT,
            summary=(
                "Withholds a ruling on buying and selling virtual currencies and "
                "directs followers to the next most learned jurist. Also holds that "
                "local law regulating crypto must be respected."
            ),
            sources=(SRC_SISTANI.url,),
        ),
        Position(
            who="AAOIFI (as an institution)",
            stance=Stance.CONDITIONAL,
            summary=(
                "Has not issued a final Shariah standard on cryptocurrency. Its "
                "Standard No. 21 quantitative screens (interest-bearing debt and "
                "securities under 30% of market cap; non-permissible income under 5% "
                "of revenue) are designed for equities and are applied to coins only "
                "by analogy."
            ),
            sources=(SRC_AAOIFI_STANDARDS.url, SRC_AAOIFI_SS21.url),
        ),
    ),
)


# ---------------------------------------------------------------------------
# Per-asset-class entries
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """A curated position for one asset class or one symbol."""

    key: str
    kind: str                                  # "class" | "symbol"
    verdict: Verdict
    confidence: str
    summary: str
    positions: tuple[Position, ...] = ()
    sources: tuple[Source, ...] = ()
    rationale: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    purification_note: str | None = None


_CLASS_ENTRIES: tuple[Entry, ...] = (
    Entry(
        key="monetary / store-of-value asset",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "A bearer asset with no issuer, no cash flow and no counterparty. Its "
            "value rests on scarcity, network effect and monetary demand."
        ),
        positions=(
            Position(
                who="Mufti Faraz Adam (Amanah Advisors)",
                stance=Stance.PERMISSIBLE,
                summary=(
                    "Bitcoin meets the conditions of mal, is scarce and divisible, "
                    "and is acceptable as a medium of exchange. Spot ownership is "
                    "permissible."
                ),
                sources=(SRC_FARAZ.url,),
            ),
            Position(
                who="Dar al-Ifta al-Misriyyah",
                stance=Stance.IMPERMISSIBLE,
                summary="Prohibited: excessive gharar, no issuing authority, speculation.",
                sources=(SRC_DAR_ALIFTA.url,),
            ),
            Position(
                who="Assembly of Muslim Jurists of America (AMJA, 2022)",
                stance=Stance.CONDITIONAL,
                summary=(
                    "A principle-by-principle analysis that treats the asset class as "
                    "carrying serious risks rather than issuing a flat verdict."
                ),
                sources=(SRC_AMJA.url,),
            ),
        ),
        sources=(SRC_FARAZ, SRC_DAR_ALIFTA, SRC_AMJA, SRC_USMANI),
        rationale=(
            "The debate turns on two classical questions. First, whether a digital "
            "entry qualifies as mal that can be possessed and transferred -- the "
            "objection being that it has no physical existence and depends on a "
            "network continuing to exist.",
            "Second, whether it is thaman (currency) or sil'ah (commodity). If it is "
            "currency, the strict rules on riba al-fadl and simultaneous possession "
            "apply to every trade, which is why some scholars find constant trading "
            "problematic even where holding is not.",
            "There is no interest paid to the holder and no counterparty owing "
            "anything, so the riba objection that dominates lending and staking does "
            "not arise here. The live objections are gharar and maysir.",
        ),
        open_questions=(
            "Does extreme price volatility amount to disqualifying gharar, or is it "
            "the ordinary volatility of any traded commodity?",
            "If the asset is currency, does trade-by-trade settlement on an exchange "
            "satisfy the requirement of simultaneous possession (qabd)?",
        ),
    ),
    Entry(
        key="smart-contract platform asset",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "A token that pays for computation, secures a network, and often carries "
            "a claim on future fee revenue. Its status depends on what the network "
            "actually does and on what the holder's return represents."
        ),
        positions=(
            Position(
                who="Contemporary Shariah boards taking the conditional view",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Permissible where the asset has a real use case, the transaction "
                    "is immediate spot rather than leveraged or interest-bearing, and "
                    "the coin is not designed for prohibited activity. This is the "
                    "approach most 'halal crypto' lists follow."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
            Position(
                who="SeekersGuidance",
                stance=Stance.CONTEXT_DEPENDENT,
                summary=(
                    "Addresses proof of stake directly and separates the network's "
                    "consensus mechanism from the individual's own act: a mechanism "
                    "being impermissible for use does not by itself make holding the "
                    "asset impermissible."
                ),
                sources=(SRC_SEEKERS_POS.url, SRC_SEEKERS_BLOCKCHAIN.url),
            ),
        ),
        sources=(SRC_HALALSCREENER, SRC_SEEKERS_POS, SRC_SEEKERS_BLOCKCHAIN, SRC_AAOIFI_SS21),
        rationale=(
            "The decisive question is what the token's value accrues from. Fee "
            "revenue from spot trading, computation and data availability is "
            "compensation for a real service. Revenue from lending interest, "
            "perpetual futures or prediction markets is a different matter, and "
            "holding a token that accrues it raises the same question as holding a "
            "bank share.",
            "Validator and staking rewards need to be separated from lending "
            "interest. A reward for securing a network and validating transactions "
            "is arguably compensation for work, which is permissible; a product that "
            "promises a fixed percentage return on deposited coins is riba, however "
            "the network underneath operates.",
            "Issuance of new supply to secure a network is not the same as a "
            "borrower paying interest on a loan, and treating the two as identical "
            "is the most common error in crypto fatwa material.",
        ),
        open_questions=(
            "Is a validator reward compensation for work (permissible) or for "
            "locked capital (riba)?",
            "If a network's fee revenue includes lending interest, what proportion "
            "must be purified, and on what basis?",
            "Does holding a governance token in a protocol whose revenue is interest "
            "fall under the conventional treatment of bank shares?",
        ),
        purification_note=(
            "Where part of a protocol's revenue derives from interest or other "
            "prohibited activity, the conventional equity approach is to give away "
            "that proportion of any income received. AAOIFI Standard 21 draws the "
            "line at 5% of revenue for equities; no equivalent agreed threshold "
            "exists for tokens, so any figure here is an analogy, not a standard."
        ),
    ),
    Entry(
        key="stablecoin",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "A token designed to hold a fixed value, usually one US dollar. The "
            "question is not the token's function but what stands behind it."
        ),
        positions=(
            Position(
                who="Mufti Faraz Adam (Amanah Advisors)",
                stance=Stance.CONDITIONAL,
                summary=(
                    "The holder receives no interest, so the token can function as a "
                    "payment claim; but where the reserves themselves are "
                    "interest-bearing instruments, some scholars hold the backing "
                    "must be permissible too."
                ),
                sources=(SRC_FARAZ.url,),
            ),
            Position(
                who="Commercial screeners applying AAOIFI principles",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Some rate the largest stablecoins as doubtful precisely because "
                    "the reserve assets generate interest, and because disclosure of "
                    "reserves is incomplete."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
        ),
        sources=(SRC_FARAZ, SRC_HALALSCREENER, SRC_XAUT),
        rationale=(
            "Fiat-backed stablecoins are normally backed by short-term government "
            "debt, treasury money-market funds and similar instruments, all of which "
            "yield interest to the issuer. The holder receives none of it, which is "
            "the basis for permitting them as payment claims.",
            "The opposing argument is that the token is a claim on a pool of "
            "interest-bearing assets, so what the holder owns is itself an "
            "interest-bearing instrument in substance if not in form.",
            "A separate concern attaches to reserve transparency. A claim whose "
            "backing cannot be verified is closer to gharar than a claim on audited "
            "reserves, and the two should not be scored alike.",
            "Algorithmic and uncollateralised stablecoins raise the gharar objection "
            "much more sharply, because there is no reserve at all -- only a "
            "mechanism, which can fail.",
        ),
        open_questions=(
            "Is a stablecoin permissible as a payment token when its reserves earn "
            "interest the holder never receives?",
            "Is a fully audited, fully collateralised coin treated differently from "
            "an opaque one?",
        ),
    ),
    Entry(
        key="meme coin",
        kind="class",
        verdict=Verdict.NON_COMPLIANT,
        confidence="medium",
        summary=(
            "A token with no cash flow, no productive use and no claim on anything, "
            "whose price depends on a future buyer paying more."
        ),
        positions=(
            Position(
                who="Weight of contemporary positions",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "A zero-sum wager on resale rather than a productive holding, "
                    "which is the structure of maysir. Some scholars additionally "
                    "treat deliberate promotion of such tokens as a form of deception."
                ),
                sources=(SRC_DAR_ALIFTA.url, SRC_USMANI.url),
            ),
        ),
        sources=(SRC_DAR_ALIFTA, SRC_USMANI),
        rationale=(
            "The objection is not to volatility, which every asset has, but to the "
            "absence of any underlying economic activity. Nothing is produced, "
            "nothing is sold, and no service is rendered; the only way one holder "
            "profits is by another losing.",
            "This is the rare area where the positions largely agree, which is why "
            "the screen treats it as non-compliant rather than disputed.",
        ),
        open_questions=(),
    ),
    Entry(
        key="decentralised exchange",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "A protocol matching buyers and sellers. Spot trading is a form of "
            "sale, which is generally permissible; the question is what else the "
            "venue offers and what the token captures."
        ),
        positions=(
            Position(
                who="Contemporary Shariah boards taking the conditional view",
                stance=Stance.PERMISSIBLE,
                summary=(
                    "A spot exchange is a marketplace, and the fee it earns is "
                    "compensation for a service. Holding its token is a claim on that "
                    "fee revenue."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
        ),
        sources=(SRC_HALALSCREENER, SRC_AAOIFI_SS21),
        rationale=(
            "Where a venue is spot-only, its revenue comes from matching trades, "
            "which resembles a brokerage fee. Where it also runs perpetual futures, "
            "margin products or interest-bearing vaults, part of that same revenue "
            "is tainted, and the tainted proportion needs purification.",
            "This is a case where the answer genuinely varies between two protocols "
            "in the same category, so the DefiLlama category alone is not decisive.",
        ),
        open_questions=(
            "What share of this venue's revenue comes from perpetuals, margin or "
            "interest-earning products rather than spot fees?",
        ),
        purification_note=(
            "If a share of protocol revenue derives from derivatives or interest, "
            "the equity analogy is to purify the corresponding share of any income."
        ),
    ),
    Entry(
        key="lending protocol",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "A pool from which borrowers draw funds and pay interest to depositors. "
            "Using it is an interest transaction."
        ),
        positions=(
            Position(
                who="The mainstream position on interest",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Borrowing or lending at interest is riba, which is prohibited "
                    "without scholarly disagreement. **Using** such a protocol "
                    "therefore falls on the prohibited side."
                ),
                sources=(SRC_AAOIFI_STANDARDS.url,),
            ),
            Position(
                who="Analogy to conventional bank shares",
                stance=Stance.CONDITIONAL,
                summary=(
                    "**Holding the governance token** is a different question. "
                    "Classical scholars have long addressed holding shares in a "
                    "conventional bank, where the majority position permits it "
                    "subject to screening and purification of the interest-derived "
                    "part of earnings."
                ),
                sources=(SRC_AAOIFI_SS21.url,),
            ),
        ),
        sources=(SRC_AAOIFI_STANDARDS, SRC_AAOIFI_SS21),
        rationale=(
            "The sharp distinction is between using a protocol and owning a stake "
            "in it. Using a lending market means receiving or paying interest, which "
            "is prohibited. Holding its governance token is an equity-like claim on "
            "a business whose income is interest, which the classical bank-share "
            "discussion addresses directly.",
            "Collapsing those two into one verdict either forbids legitimate equity "
            "structures or permits straightforward riba, so the screen reports the "
            "distinction rather than picking a side.",
        ),
        open_questions=(
            "Does the bank-share analogy hold for a governance token, given that a "
            "share confers legal ownership of a company and a token may not?",
        ),
        purification_note=(
            "Under the equity analogy, the interest-derived share of any income "
            "received would be purified."
        ),
    ),
    Entry(
        key="centralised exchange token",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A claim on an off-chain exchange business rather than a bearer asset, "
            "issued by a company whose revenue includes margin, futures and "
            "interest-earning products."
        ),
        sources=(SRC_AAOIFI_SS21,),
        positions=(
            Position(
                who="AAOIFI Shari'a Standard No. 21, applied by analogy",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Screened as a share rather than as a currency: permissible only "
                    "if interest-bearing debt stays under 30% of market "
                    "capitalisation and non-permissible income under 5% of revenue. "
                    "The test is arithmetic, which is both its appeal and its limit -- "
                    "the Standard was written for equities, not tokens."
                ),
                sources=(SRC_AAOIFI_SS21.url,),
            ),
            Position(
                who="HalalScreener",
                stance=Stance.CONTEXT_DEPENDENT,
                summary=(
                    "Applies the equity revenue screens to large-cap tokens and "
                    "publishes per-asset results, treating an exchange token as "
                    "pass-or-fail on its business mix rather than as a category that "
                    "is prohibited in itself."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
        ),
        rationale=(
            "This is closest to a conventional equity holding of any token class, "
            "which makes the classical screening framework the most natural fit -- "
            "and that framework will usually flag it, because a crypto exchange's "
            "revenue is substantially derived from leveraged and interest-bearing "
            "products.",
            "The centralisation also means the holder depends on an issuer's "
            "solvency and honesty, which introduces counterparty risk that the "
            "asset's marketing usually does not disclose.",
        ),
        open_questions=(
            "What proportion of the issuer's revenue comes from spot trading fees "
            "versus margin, futures and earn products?",
        ),
    ),
    Entry(
        key="payments network asset",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A token used to settle cross-border payments, with an identifiable "
            "issuer and a defined operational purpose."
        ),
        sources=(SRC_FARAZ, SRC_USMANI),
        positions=(
            Position(
                who="Mufti Faraz Adam (Amanah Advisors)",
                stance=Stance.PERMISSIBLE,
                summary=(
                    "Holding a token with a genuine settlement function and an "
                    "identifiable issuer satisfies the conditions he sets for "
                    "permissibility: recognised issuing authority, real use case, and "
                    "no interest-bearing mechanism inside the token itself."
                ),
                sources=(SRC_FARAZ.url,),
            ),
            Position(
                who="Mufti Muhammad Taqi Usmani",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Reported to leave the ruling open to revision where a token "
                    "becomes tied to real economic activity -- which is precisely the "
                    "argument a settlement token makes for itself. The report of his "
                    "position should be verified against a primary source before being "
                    "relied on."
                ),
                sources=(SRC_USMANI.url,),
            ),
        ),
        rationale=(
            "Having an issuer and a genuine settlement function removes the 'no "
            "recognised issuing authority' objection that drives the prohibiting "
            "position, while the settlement function gives the real-use-case answer "
            "that the conditional position requires.",
            "The countervailing concern is that a large share of the supply is "
            "held by the issuer, so the holder's exposure depends on a single "
            "party's conduct.",
        ),
        open_questions=(
            "Is the dispute over the token a commercial matter rather than a Sharia one?",
        ),
    ),
    Entry(
        key="oracle / data infrastructure",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "A protocol that supplies data to other applications for a fee. The "
            "activity itself is a service."
        ),
        sources=(SRC_HALALSCREENER,),
        positions=(
            Position(
                who="Contemporary Shariah boards taking the conditional view",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Providing data for a fee is ordinary commerce, so the activity is "
                    "permissible; the token is permissible where the holder's return "
                    "comes from that service revenue rather than from interest, "
                    "leverage or a guaranteed yield."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
            Position(
                who="Prohibiting view (Dar al-Ifta al-Misriyyah and others)",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "The general prohibition of cryptocurrency trading applies "
                    "regardless of the underlying protocol's usefulness, because the "
                    "objection is to the token as a tradable object rather than to the "
                    "service the network performs."
                ),
                sources=(SRC_DAR_ALIFTA.url,),
            ),
        ),
        rationale=(
            "Providing data for a fee is ordinary commerce. The gharar objection "
            "attaches to the quality and verifiability of what is supplied rather "
            "than to the concept, which is the same reputational concern any data "
            "vendor faces.",
            "The token-holder question remains: whether the token is a claim on the "
            "service revenue or a pure speculation on the network's usage.",
        ),
    ),
)

_SYMBOL_ENTRIES: tuple[Entry, ...] = (
    Entry(
        key="BTC",
        kind="symbol",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "Bitcoin: the most-studied case, and the one on which the most "
            "authorities have stated a position."
        ),
        positions=(
            Position(
                who="Mufti Faraz Adam (Amanah Advisors)",
                stance=Stance.PERMISSIBLE,
                summary=(
                    "Bitcoin satisfies the conditions of mal, is scarce and "
                    "divisible, and is acceptable as a medium of exchange. Spot "
                    "ownership is permissible."
                ),
                sources=(SRC_FARAZ.url,),
            ),
            Position(
                who="Dar al-Ifta al-Misriyyah (Grand Mufti Shawki Allam, 2017)",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Prohibited, citing excessive uncertainty (gharar), extreme "
                    "volatility, and the absence of a recognised issuing authority."
                ),
                sources=(SRC_DAR_ALIFTA.url,),
            ),
            Position(
                who="Mufti Muhammad Taqi Usmani",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Reported to consider trading impermissible in its current "
                    "speculative form, with the ruling open to revision if crypto "
                    "becomes tied to real economic activity."
                ),
                sources=(SRC_USMANI.url,),
            ),
        ),
        sources=(SRC_FARAZ, SRC_DAR_ALIFTA, SRC_USMANI, SRC_AMJA, SRC_SRB),
        rationale=(
            "Bitcoin has no issuer, pays no interest, and has no counterparty who "
            "owes the holder anything. The riba objection that dominates lending "
            "and staking products simply does not arise. The live objections are "
            "gharar and maysir.",
            "Mining rewards are compensation for work -- expended energy and "
            "computation -- which is a substantially stronger position than a "
            "reward for merely locking capital.",
        ),
        open_questions=(
            "Is the volatility of Bitcoin disqualifying gharar, or the ordinary "
            "volatility of a traded commodity?",
            "Does an exchange trade satisfy simultaneous possession (qabd) if the "
            "buyer holds no keys?",
        ),
    ),
    Entry(
        key="ETH",
        kind="symbol",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "Ethereum: an asset with a genuine use case, a staking mechanism, and "
            "an economy on top of it that includes interest-bearing protocols."
        ),
        sources=(SRC_HALALSCREENER, SRC_SEEKERS_POS, SRC_SEEKERS_BLOCKCHAIN),
        rationale=(
            "The use-case objection is weak here: the network performs computation "
            "that people pay for, so the conditional position is satisfied on that "
            "ground.",
            "Staking is the harder question. Proof-of-stake rewards exist to secure "
            "the network, which is arguably compensation for work, but the reward "
            "scales with capital locked rather than effort expended, which "
            "resembles the structure of riba.",
            "Separately, much of the activity on the network is lending and "
            "derivatives, so any claim that the network's economy is clean is "
            "difficult to sustain. That does not settle the token's own status, but "
            "it is the reason this is reported as disputed rather than permitted.",
        ),
        open_questions=(
            "Is a proof-of-stake validator reward compensation for work or for "
            "capital?",
            "Does the presence of interest-based protocols on the network taint the "
            "base asset?",
        ),
        purification_note=(
            "If staking rewards are treated as permissible income, no purification "
            "arises. If they are treated as riba, the conventional remedy is to "
            "relinquish the reward rather than the principal."
        ),
    ),
    Entry(
        key="USDT",
        kind="symbol",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "Tether: the largest stablecoin, and the most frequently questioned on "
            "reserve transparency as well as on the interest-bearing nature of its "
            "backing."
        ),
        positions=(
            Position(
                who="Commercial screeners applying AAOIFI principles",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Rated doubtful, on the grounds that reserves are "
                    "interest-bearing and disclosure of what actually backs the "
                    "token has historically been incomplete."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
            Position(
                who="The payment-claim view",
                stance=Stance.CONDITIONAL,
                summary=(
                    "The holder receives no interest, so the token functions as a "
                    "payment claim; the reserves are the issuer's affair."
                ),
                sources=(SRC_FARAZ.url,),
            ),
        ),
        sources=(SRC_HALALSCREENER, SRC_FARAZ, SRC_AAOIFI_STANDARDS),
        rationale=(
            "Two separate objections are often run together here and should not be. "
            "One is that the reserves earn interest. The other is that the reserves "
            "are not fully verifiable. The second is the more serious of the two, "
            "because a claim whose backing cannot be checked is closer to gharar "
            "than a claim on audited assets.",
            "A stablecoin used purely as a settlement medium between two purchases "
            "is a different question from a stablecoin held as an investment.",
        ),
        open_questions=(
            "Are the reserves interest-bearing, and does that taint the holder?",
            "Can the reserves be independently verified today?",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Second tranche of class entries.
#
# These exist because sharia.rules.classify() speaks a finer-grained vocabulary
# than the entries above: a DefiLlama category like "liquid staking" or
# "restaking" names a specific mechanism, whereas the Sharia question it raises
# is shared with several neighbouring mechanisms. Grouping them under one entry
# keeps one question in one place instead of six near-duplicate answers, and
# CLASS_ALIASES below routes the classifier's names here.
# ---------------------------------------------------------------------------

_EXTRA_CLASS_ENTRIES: tuple[Entry, ...] = (
    Entry(
        key="interest-bearing staking or yield product",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="medium",
        summary=(
            "The holder's return comes from lending out, staking, or otherwise "
            "putting the underlying asset to work. This is the most contested "
            "structure in the whole space, because it looks like a deposit."
        ),
        positions=(
            Position(
                who="SeekersGuidance (conditional position)",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Distinguishes between the mechanism and the return: the "
                    "blockchain's consensus design is not itself the objection, but a "
                    "yield that is contractually promised and fixed is riba. The "
                    "question to put to the token is where the money paid to the "
                    "holder actually comes from."
                ),
                sources=(SRC_SEEKERS_POS.url, SRC_SEEKERS_BLOCKCHAIN.url),
            ),
            Position(
                who="Mufti Faraz Adam (Amanah Advisors)",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Treats the underlying token and any yield derived from it as "
                    "separate questions, so a permissible token can still carry an "
                    "impermissible yield product."
                ),
                sources=(SRC_FARAZ.url,),
            ),
            Position(
                who="AAOIFI Shari'a Standard No. 21, applied by analogy",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Where the return is a function of an interest-bearing loan rather "
                    "than of shared profit and loss, the classical prohibition of "
                    "riba applies without further argument."
                ),
                sources=(SRC_AAOIFI_SS21.url,),
            ),
        ),
        rationale=(
            "The determining question is the source of the return, not the label on "
            "it. A validator's fee income is payment for work; a fixed percentage "
            "paid for locking tokens is closer to a loan. Many products marketed as "
            "'staking' are the second kind wearing the first kind's vocabulary.",
            "Loss of custody matters too: handing the asset to a protocol to earn a "
            "return introduces a counterparty the holder no longer controls.",
        ),
        open_questions=(
            "Is the return a share of variable fee income, or a fixed rate promised "
            "in advance?",
            "Does the holder retain ownership of the underlying, or a claim on a "
            "pool?",
        ),
        purification_note=(
            "Where income mixes permissible and impermissible sources, scholars "
            "commonly advise giving away the estimated impermissible share."
        ),
    ),
    Entry(
        key="derivatives venue",
        kind="class",
        verdict=Verdict.NON_COMPLIANT,
        confidence="medium",
        summary=(
            "A protocol whose business is options, futures, perpetuals or synthetic "
            "exposure. The contract's subject matter is a risk, not an asset."
        ),
        positions=(
            Position(
                who="Classical position on gharar and maysir",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Selling what one does not own and trading on an outcome one does "
                    "not control combines gharar (excessive uncertainty) with maysir "
                    "(wagering). The prohibition attaches to the contract itself "
                    "rather than to the token that intermediates it."
                ),
                sources=(SRC_AAOIFI_STANDARDS.url,),
            ),
            Position(
                who="Mufti Muhammad Taqi Usmani",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Derivative contracts in their conventional form are not "
                    "permissible, because the underlying asset is not actually "
                    "exchanged at settlement."
                ),
                sources=(SRC_USMANI.url,),
            ),
        ),
        rationale=(
            "Synthetic exposure decouples the trade from ownership. Even where the "
            "reference asset is permissible, the instrument is not, because the "
            "delivery and possession conditions of a sale are absent.",
            "This is one of the few areas where the scholarly disagreement is small: "
            "the dispute is about conventional derivatives generally, not about "
            "crypto specifically.",
        ),
        open_questions=(
            "Does holding a governance token of a derivatives venue differ from "
            "using the venue?",
        ),
    ),
    Entry(
        key="real-world-asset token",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A token representing a claim on an off-chain asset, most often a "
            "commodity, treasury bill or private credit."
        ),
        positions=(
            Position(
                who="Amanah Advisors (XAU(T) certification)",
                stance=Stance.PERMISSIBLE,
                summary=(
                    "Certified a gold-backed token as permissible where the token "
                    "represents allocated physical metal and the redemption mechanics "
                    "are sound -- evidence that this class can be made compliant when "
                    "the underlying is halal and genuinely held."
                ),
                sources=(SRC_XAUT.url, SRC_FARAZ.url),
            ),
            Position(
                who="AAOIFI Shari'a Standard No. 21, applied by analogy",
                stance=Stance.CONDITIONAL,
                summary=(
                    "The claim is screened like a security: permissible if the "
                    "underlying business is halal and the leverage tests pass. A "
                    "token that tokenises interest-bearing debt fails at the "
                    "underlying, however clean the wrapper."
                ),
                sources=(SRC_AAOIFI_SS21.url,),
            ),
        ),
        rationale=(
            "The token is only ever as permissible as what it represents, and the "
            "representation is a legal claim enforced by an off-chain custodian. Both "
            "halves need checking, and neither is verifiable from market data alone.",
        ),
        open_questions=(
            "Is the off-chain asset actually held, and does the holder have a "
            "legally enforceable claim to it?",
        ),
        purification_note=(
            "Where the underlying generates interest income, the holder's share of "
            "it is normally purified by disposal."
        ),
    ),
    Entry(
        key="bridge / cross-chain infrastructure",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A protocol that moves value between chains and charges a fee for the "
            "service. The activity is a transfer service."
        ),
        positions=(
            Position(
                who="Contemporary Shariah boards taking the conditional view",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Moving assets for a fee is a permissible service (ujrah). The "
                    "concern is custodial: most bridges take temporary control of the "
                    "asset and carry a solvency risk the holder is not compensated "
                    "for."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
            Position(
                who="Prohibiting view",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Falls under the general objection to the tokens being "
                    "transferred, and additionally involves receiving a fungible "
                    "wrapped claim whose issuer is a single point of failure."
                ),
                sources=(SRC_DAR_ALIFTA.url,),
            ),
        ),
        rationale=(
            "A service fee is the easiest thing in this space to justify. What makes "
            "the class disputed is not the fee but the custody: a bridge holds pooled "
            "assets, so the holder's exposure is to an operator's balance sheet.",
        ),
    ),
    Entry(
        key="privacy-enhancing asset",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A token whose primary function is to obscure transaction details. "
            "Concealment is the product."
        ),
        positions=(
            Position(
                who="Contemporary analyses reviewing privacy coins",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Financial concealment is not a permissible objective in itself, "
                    "and a tool whose principal use is to hide the movement of value "
                    "from legitimate oversight attracts the prohibition regardless of "
                    "the holder's intent."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
            Position(
                who="Qualified permissibility position",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Financial privacy has legitimate purposes and is recognised in "
                    "classical contract (concealing one's affairs is not itself lying), "
                    "so the objection is to predominant misuse rather than to the "
                    "capability."
                ),
                sources=(SRC_SEEKERS_BLOCKCHAIN.url,),
            ),
        ),
        rationale=(
            "This is a case where the tool should be explicit that the assessment "
            "turns on judgement about predominant use, not on a computable test. The "
            "data available here cannot settle it.",
        ),
        open_questions=(
            "Does the token have a non-concealment use case at all?",
        ),
    ),
    Entry(
        key="gaming and virtual-world asset",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A token used inside a game or virtual economy, or a marketplace that "
            "trades such items."
        ),
        positions=(
            Position(
                who="Contemporary Shariah boards taking the conditional view",
                stance=Stance.CONDITIONAL,
                summary=(
                    "The asset is permissible if it is genuinely earned or purchased "
                    "for a real service and usable in the game; it becomes maysir when "
                    "the purchase is a wager on a random outcome or purely a "
                    "speculative position on the token price."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
            Position(
                who="Prohibiting view on loot-box style mechanics",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Randomised rewards sold for money are the modern form of the "
                    "lottery, and games built on them are prohibited irrespective of "
                    "the token's technical design."
                ),
                sources=(SRC_AMJA.url,),
            ),
        ),
        rationale=(
            "The distinguisher is not the game but the mechanism of acquisition. "
            "The same token can be a purchase in one game and a lottery ticket in "
            "another.",
        ),
    ),
    Entry(
        key="prediction market",
        kind="class",
        verdict=Verdict.NON_COMPLIANT,
        confidence="medium",
        summary=(
            "A market where participants stake value on the outcome of an event. The "
            "payoff is a transfer from the loser to the winner."
        ),
        positions=(
            Position(
                who="Classical position on maysir",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Staking value on an uncertain outcome where one party's gain is "
                    "another's loss is the definition of wagering, which the Qur'an "
                    "prohibits outright. That the wager concerns an election or a "
                    "sports result rather than dice does not change its structure."
                ),
                sources=(SRC_AAOIFI_STANDARDS.url,),
            ),
            Position(
                who="Conditional view on risk-hedging",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Where a participant holds a genuine, pre-existing exposure and "
                    "the contract transfers that real risk, the transaction is closer "
                    "to insurance than to betting -- but that argument requires an "
                    "exposure the participant already had, which most users do not "
                    "have."
                ),
                sources=(SRC_AAOIFI_SS21.url,),
            ),
        ),
        rationale=(
            "This is one of the clearest prohibitions in the knowledge base, and it "
            "rests on the structure of the contract rather than on the token: a "
            "permissible token used to place a wager is still a wager.",
        ),
    ),
    Entry(
        key="token launch platform",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A platform that sells newly issued tokens to the public, earning a fee "
            "on each sale."
        ),
        positions=(
            Position(
                who="Contemporary Shariah boards taking the conditional view",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Charging a fee to arrange a sale is permissible brokerage. The "
                    "objection attaches to what is sold: a sale of an asset whose "
                    "specification is not yet determined carries gharar, and a sale of "
                    "a claim on future work is closer to ju'alah, which requires the "
                    "work and the reward to be defined."
                ),
                sources=(SRC_FARAZ.url,),
            ),
            Position(
                who="Prohibiting view on public token sales",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Selling a token before it exists, at a price set by the seller, "
                    "concentrates gharar and gives the buyer no possessable object at "
                    "the moment of contract."
                ),
                sources=(SRC_DAR_ALIFTA.url,),
            ),
        ),
        rationale=(
            "The class covers a wide range from transparent auctions to "
            "undisclosed-presale arrangements, and the Sharia assessment depends "
            "almost entirely on which of those a given platform operates.",
        ),
    ),
    Entry(
        key="insurance protocol",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A protocol that pools contributions to pay out on specified losses."
        ),
        positions=(
            Position(
                who="AAOIFI Shari'a Standards on takaful",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Cooperative risk-sharing is permissible where the pool is mutual, "
                    "surplus is returned to participants, and the operator earns a "
                    "fee for administration rather than a spread on the risk."
                ),
                sources=(SRC_AAOIFI_STANDARDS.url,),
            ),
            Position(
                who="Classical position on conventional insurance",
                stance=Stance.IMPERMISSIBLE,
                summary=(
                    "Where the structure transfers risk to a company for a premium, "
                    "and the company invests the pool in interest-bearing assets, both "
                    "gharar and riba are present."
                ),
                sources=(SRC_AAOIFI_STANDARDS.url,),
            ),
        ),
        rationale=(
            "Whether a given protocol behaves like takaful or like a conventional "
            "insurer is a question about its payout and surplus rules, which market "
            "data cannot answer. The report should say so rather than guess.",
        ),
    ),
    Entry(
        key="NFT marketplace",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A venue that matches buyers and sellers of non-fungible tokens and takes "
            "a commission."
        ),
        positions=(
            Position(
                who="Contemporary Shariah boards taking the conditional view",
                stance=Stance.CONDITIONAL,
                summary=(
                    "Brokerage for a fee is permissible, and a defined digital item is "
                    "a possessable object. The assessment turns on the items traded: a "
                    "marketplace that principally lists randomised mints or prohibited "
                    "content inherits the prohibition of what it facilitates."
                ),
                sources=(SRC_HALALSCREENER.url,),
            ),
        ),
        rationale=(
            "This is a case where the token-holder's position and the platform's "
            "activity are different questions, and the answer depends on the "
            "marketplace's listing policy rather than on its technology.",
        ),
    ),
    Entry(
        key="index product",
        kind="class",
        verdict=Verdict.DISPUTED,
        confidence="low",
        summary=(
            "A token whose value tracks a basket of other assets, bought and sold as "
            "a single unit."
        ),
        positions=(
            Position(
                who="AAOIFI Shari'a Standard No. 21, applied by analogy",
                stance=Stance.CONDITIONAL,
                summary=(
                    "A basket is screened like a fund: permissible only if every "
                    "constituent passes, or if the non-compliant share is small enough "
                    "to be purified. A single prohibited constituent is not laundered "
                    "by being bundled with compliant ones."
                ),
                sources=(SRC_AAOIFI_SS21.url,),
            ),
        ),
        rationale=(
            "The bundling is the whole risk. Diversification across a basket that "
            "includes leveraged or interest-bearing positions does not dilute the "
            "prohibition, it embeds it.",
        ),
    ),
)

_CLASS_ENTRIES = _CLASS_ENTRIES + _EXTRA_CLASS_ENTRIES


#: Routes the finer-grained class names produced by sharia.rules.classify() onto
#: the curated entries above. Anything absent is deliberately left unmapped: an
#: unrecognised class must surface as UNCLASSIFIED rather than be quietly folded
#: into a neighbouring ruling.
CLASS_ALIASES = {
    "layer 1 / layer 2 network": "smart-contract platform asset",
    "payments network": "payments network asset",
    "algorithmic stablecoin": "stablecoin",
    "stablecoin issuer": "stablecoin",
    "privacy-focused monetary asset": "privacy-enhancing asset",
    "privacy infrastructure": "privacy-enhancing asset",
    "liquid staking derivative": "interest-bearing staking or yield product",
    "restaking": "interest-bearing staking or yield product",
    "restaking derivative": "interest-bearing staking or yield product",
    "yield aggregator": "interest-bearing staking or yield product",
    "yield farming": "interest-bearing staking or yield product",
    "leveraged yield strategy": "interest-bearing staking or yield product",
    "collateralised debt protocol": "interest-bearing staking or yield product",
    "basis trading / carry strategy": "interest-bearing staking or yield product",
    "options venue": "derivatives venue",
    "bridge infrastructure": "bridge / cross-chain infrastructure",
    "cross-chain infrastructure": "bridge / cross-chain infrastructure",
    "infrastructure service": "bridge / cross-chain infrastructure",
    "gaming / metaverse": "gaming and virtual-world asset",
}


def canonical_class(asset_class: str) -> str:
    """Resolve a classifier class name onto a curated entry key, if one exists."""
    lowered = (asset_class or "").strip().lower()
    return CLASS_ALIASES.get(lowered, lowered)


ALL_ENTRIES: tuple[Entry, ...] = _CLASS_ENTRIES + _SYMBOL_ENTRIES


def lookup(asset_class: str, symbol: str) -> Entry | None:
    """A symbol-specific entry wins over the class entry; else the class entry."""
    upper = (symbol or "").upper()
    for entry in _SYMBOL_ENTRIES:
        if entry.key.upper() == upper:
            return entry
    return entry_for_class(asset_class)


def entry_for_class(asset_class: str) -> Entry | None:
    """The curated entry for a class name, following CLASS_ALIASES."""
    if not asset_class:
        return None
    wanted = canonical_class(asset_class)
    if wanted in ("", "unclassified"):
        return None
    for entry in _CLASS_ENTRIES:
        if entry.key.lower() == wanted:
            return entry
    return None


def entries_for_class(asset_class: str) -> list[Entry]:
    entry = entry_for_class(asset_class)
    return [entry] if entry else []


def all_sources() -> list[Source]:
    """Every source cited anywhere in this knowledge base, de-duplicated by URL.

    This deliberately walks into `positions` as well as each entry's own
    `sources`, because a position that cites nothing is an assertion with no
    evidence behind it, and that is exactly what the report must never print.
    """
    seen: dict[str, Source] = {}
    for entry in ALL_ENTRIES:
        for src in entry.sources:
            seen.setdefault(src.url, src)
        for position in entry.positions:
            for url in position.sources:
                seen.setdefault(url, source_for(url))
    return list(seen.values())


def describe_coverage() -> dict[str, object]:
    """What this knowledge base does and does not cover, stated plainly."""
    keys = {e.key.lower() for e in _CLASS_ENTRIES}
    return {
        "class_entries": [e.key for e in _CLASS_ENTRIES],
        "symbol_entries": [e.key for e in _SYMBOL_ENTRIES],
        "class_aliases": dict(CLASS_ALIASES),
        "landscape_positions": len(LANDSCAPE.bodies),
        "core_questions": len(CORE_QUESTIONS),
        "near_universal_prohibitions": len(NEAR_UNIVERSAL_PROHIBITIONS),
        "verification_note": VERIFICATION_NOTE,
    }


def total_positions() -> int:
    """How many distinct scholarly positions this knowledge base carries."""
    seen: set[tuple[str, str]] = set()
    for entry in ALL_ENTRIES:
        for position in entry.positions:
            seen.add((position.who.strip().lower(), position.stance.value))
    return len(seen)

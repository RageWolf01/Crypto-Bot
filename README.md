# Crypto Advisor

A research tool that studies the crypto market and writes you a daily digest: a
ranked shortlist with the reasoning shown, the risk flags, and a **separate**
Sharia screen that reports what published scholars have actually said about each
kind of asset, with citations.

## What this is, and what it is not

**It is not a machine that tells you which coin will go up.** No such machine
exists, and any tool claiming to be one is either lying or overfitting to the
past. If you take one thing from this project, take that.

What it actually does:

- **Screens** ~150 assets through hard disqualifiers, so most of the market is
  removed for concrete, checkable reasons (thin liquidity, no order book,
  imminent dilution, too young).
- **Scores** what survives on five transparent factors, each of which reports how
  much data it actually had.
- **Flags** the things that hurt you: wash-trading-looking turnover, dilution,
  a 97% drawdown that may be a broken asset rather than a discount.
- **Describes the market regime** and translates it into a maximum exposure
  number — not a ranking change.

**It is not a fatwa, and it is not investment advice.** The Sharia section
reports *published positions with links*. Where scholars disagree, it shows the
disagreement rather than picking a winner for you. See
[`crypto_advisor/DECISIONS.md`](crypto_advisor/DECISIONS.md) for the reasoning
behind that choice.

The one rule the whole design rests on: **the investment score and the Sharia
verdict are completely independent.** A coin can be perfectly halal and a
terrible investment. A coin can be an excellent trade and clearly haram. The tool
never blurs the two, and no combined "halal score" exists anywhere in the code.

## Quick start

Requires Python 3.11+ (built and tested on 3.14). **No dependencies** — standard
library only, deliberately, so you can read and change it without fighting an
environment.

```powershell
cd "C:\Users\USERNAME\Documents\Crypto Bot"   # or wherever you cloned it

# 1. Check config and connectivity
python -m crypto_advisor doctor

# 2. Look at the Sharia rules and how much of the knowledge base is filled in
python -m crypto_advisor rules

# 3. Take a fast look at 10 coins before committing to a full run
python -m crypto_advisor run --limit 10

# 4. The real thing: full universe, ~6 minutes cold, seconds warm
python -m crypto_advisor run
```

Reports are written to `reports/digest-<date>.md` (for reading) and
`reports/digest-<date>.json` (for scripting).

## Commands

| Command | What it does |
|---|---|
| `run` | Full research pass; writes the digest. `--limit N` caps the universe, `--verbose` narrates as it fetches |
| `show` | Prints the most recent digest |
| `doctor` | Config sanity plus four live connectivity probes |
| `rules` | Lists the Sharia rules, class coverage and the scholarly landscape |
| `sources` | Shows the data sources and the HTTP cache state |
| `task` | Registers the daily digest as a Windows scheduled task |
| `config` | Prints the effective configuration |

All commands accept `-c <path>` to point at a different `config.toml`.

## How the digest is put together

```
CoinPaprika ──┐
              ├─► universe.build()  ──► Asset ──┬─► quant.score_universe() ──┐
Binance ──────┤   (joins + honest              │                            │
              │    data-gap warnings)          └─► sharia.screen.assess() ──┤
DefiLlama ────┘                                                             │
                                                                            ▼
                                                             report.build() ──► .md + .json
```

| File | Responsibility |
|---|---|
| `crypto_advisor/config.py` | Loads and validates `config.toml` |
| `crypto_advisor/http.py` | Caching, throttling, retries; falls back to stale data with a warning rather than crashing |
| `crypto_advisor/store.py` | SQLite: HTTP cache, daily snapshots, run history, scores |
| `crypto_advisor/sources/` | One module per provider, each returning typed records |
| `crypto_advisor/universe.py` | The messy join layer, concentrated in one place on purpose |
| `crypto_advisor/model.py` | The shared `Asset` / `FactorScore` / `ScoreCard` vocabulary |
| `crypto_advisor/quant/` | `stats` → `factors` → `disqualifiers` → `regime` → `score` |
| `crypto_advisor/sharia/` | `types` → `rules` → `knowledge` → `screen` |
| `crypto_advisor/report.py` | The Markdown digest — the actual deliverable |
| `crypto_advisor/pipeline.py` | Wires the stages together and records provenance |

## The five factors, and how to tune them

Weights live in `config.toml` under `[quant.weights]` and must sum to roughly 1:

```toml
[quant.weights]
liquidity  = 0.25   # can you actually get in and out without moving the price
momentum   = 0.20   # risk-adjusted, cross-sectional, drawdown-penalised
tokenomics = 0.20   # dilution and supply structure
traction   = 0.20   # is anything actually using this and paying for it
valuation  = 0.15   # what you pay for the earnings that exist
```

Two design rules govern every factor, and both exist to stop the tool from
sounding more certain than it is:

1. **A group only counts as far as it has data.** Each factor reports a
   `coverage` fraction, and its score is shrunk toward neutral by that fraction.
   Missing data costs confidence; it never lets one available metric ace a group.
2. **Liquidity uses absolute thresholds, momentum uses relative ones.** A dollar
   of volume is a dollar of volume, so it is measured against fixed numbers. A
   return only means something by comparison, so momentum is standardised across
   the universe.

Momentum is deliberately *not* annualised: annualising a 30-day return produces
absurd magnitudes that destroy the ordering. It is also winsorised to the
2nd/98th percentile before standardisation, because one parabolic return would
otherwise dominate both the mean and the standard deviation.

### Hard disqualifiers

Set in `[quant.disqualifiers]`. These are the gate, and they run before scoring:

- median daily volume below `min_daily_volume_usd` ($5M)
- market cap below `min_market_cap_usd` ($100M)
- no live Binance spot pair (you cannot check the order book, so you cannot
  verify the volume)
- listed for less than `min_listing_age_days` (365)
- order-book depth below `min_book_depth_usd` ($250K) within 2% of mid
- spread wider than `max_spread_bps` (25)
- stablecoins, when `exclude_stablecoins = true`
- any protocol DefiLlama itself classifies as `Ponzi`

Not all problems are disqualifying. Softer concerns — turnover above 1.0
(possible wash trading), `fdv_to_mcap` above 5.0 (dilution), a 95% drawdown, a
matched protocol reporting no fee revenue — become **flags** shown next to the
score.

### Market regime

`[quant.regime]` is the only place a market-timing view is expressed, and it
**changes total exposure, never the ranking**. It reads BTC against its 200-day
moving average, uses Fear & Greed *only at extremes* (≥75 or ≤25 — the middle
band carries little information and is explicitly ignored), and nudges exposure
by the 30-day stablecoin supply trend. Exposure is capped at 0.90; the tool never
suggests going all in.

## The Sharia screen

The screen is a **disagreement engine, not a verdict engine.** That was your
explicit choice, and it is also the honest one: there is no scholarly consensus
on crypto, unlike equities where AAOIFI and several index providers publish
screening methodologies.

Three layers:

1. **`rules.py`** maps DefiLlama's independent `category` field onto classical
   concerns — riba (lending, CDPs, liquid staking, yield aggregators, basis
   trades), gharar (derivatives, options, leveraged farming, algorithmic pegs),
   maysir (prediction markets, memecoins), batil (`Ponzi`). It also carries three
   rules that apply to *how you use* any asset, stated once: **leverage/margin/
   futures** (fatal), **guaranteed "earn" yield** (fatal, riba), and day-trading
   on noise (minor).

2. **`knowledge.py`** holds 20 curated asset-class entries and 3 per-symbol
   entries (BTC, ETH, USDT), carrying 31 distinct scholarly positions with 11
   cited sources — the four Sunni schools' reasoning, AAOIFI Standard 21, the OIC
   Fiqh Academy resolutions, the Egyptian Dar al-Ifta, Mufti Taqi Usmani, Mufti
   Faraz Adam, Shariah Review Bureau, Diyanet, AMJA, and SeekersGuidance.

3. **`screen.py`** combines them. Two rules are load-bearing:
   - `COMPLIANT` is **never** produced by the absence of a problem. Anything
     unplaceable is `UNCLASSIFIED`, so an unknown token cannot drift into looking
     permissible by omission.
   - A symbol entry **adds** specificity but does not replace the class
     positions. A scholar writing about smart-contract platforms is plainly
     addressing ETH, so dropping those positions would hide relevant
     disagreement.

Every position carries a link. If a position cites nothing, the report says so
rather than asserting it.

### Adding your own position

That is the point of the knowledge base being a plain Python file. Open
`crypto_advisor/sharia/knowledge.py`, find the entry, add a `Position`:

```python
Position(
    who="Mufti X (Institution)",
    stance=Stance.CONDITIONAL,
    summary="What they actually said, in their own terms.",
    sources=(SRC_FARAZ.url,),   # a URL that appears in SOURCE_REGISTRY
),
```

Then run `python -m crypto_advisor rules` to confirm coverage, and cite the
primary source rather than a summary of it where you can.

## Daily digest

```powershell
python -m crypto_advisor task --install --time 08:00
python -m crypto_advisor task --remove
```

This registers a Windows scheduled task (`CryptoAdvisorDailyDigest`). Task
Scheduler sets no working directory, so the task points at a generated launcher
(`daily_digest.py`) that puts the project root on `sys.path` before running the
CLI. You can read, edit, or run that launcher yourself.

## Tests

```powershell
python tests.py
```

50 offline tests, no network, standard library `unittest`. They exist to pin the
rules that make the report silently *wrong* when they break rather than merely
ugly: missing data must not read as a good score, unknown must not read as
permissible, a bridge's revenue must not be attributed to the chain it serves,
and every classifier class must have a curated entry. Run them after editing
anything in `quant/` or `sharia/`.

## Project layout note

`_probe/` holds the throwaway scripts used to check which APIs were reachable and
what shape they return. They are history, not part of the tool — `doctor` covers
connectivity now, and the findings are written up in
[`crypto_advisor/DECISIONS.md`](crypto_advisor/DECISIONS.md).

## Known limitations, stated up front

- **Survivorship bias.** Aggregators hide dead coins. A screen built today cannot
  see the projects that already went to zero, so historical validation is
  optimistic by construction.
- **Wash trading.** Reported volume can be faked. The tool uses the *median*
  daily volume rather than the mean, and flags suspiciously high turnover, but it
  cannot prove manipulation.
- **TVL is gameable and double-counted.** It is shown for context, never used as
  a hard gate.
- **Tokenomics is the weakest factor.** Free APIs expose no emission schedule or
  unlock calendar, so it reduces to FDV/market-cap and whether supply is capped.
  The notes in the report say so.
- **No on-chain fundamentals.** NVT-style valuation would need on-chain volume;
  using exchange volume as a substitute would be a category error, so it is not
  done.
- **Overfitting.** Factor weights are judgement calls, not fitted parameters.
  Treat any tuning as a hypothesis, not an optimisation.
- **Stale data is possible.** When a provider fails, the tool serves cached data
  and says so in the report's warnings rather than silently proceeding.

## The traps this was designed around

Recorded here so a future change does not quietly reintroduce them:

| Trap | How it is handled |
|---|---|
| CoinGecko rate limits (HTTP 429 after ~8 calls) | Demoted to optional; CoinPaprika and Binance carry the load |
| Aggregator returning a literal `0` for 30d/1y change | Computed from Binance closes instead, and a too-short window is refused |
| `change_7dover7d` is an unbounded ratio | Guarded; a collapsed prior week is reported as text, not "-2382%" |
| A bridge's revenue attributed to the chain it serves | Wrapper-identity check: `Avalanche` is not `Avalanche Core Bridge` |
| Missing data read as a good score | Coverage shrinkage toward neutral at every level |
| Unknown classified as permissible | `UNCLASSIFIED` by default; `COMPLIANT` must be earned |

## Disclaimer

This digest is research output from a program you run yourself. It is not
investment advice, and it is not a fatwa. The Sharia section reports published
positions with citations and applies transparent rules; it does not issue a
religious ruling, and reasonable scholars disagree with parts of it. Ask a
qualified scholar about your own situation.

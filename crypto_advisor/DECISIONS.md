# Project decisions and constraints

Living record. Kept in the repo on purpose: a design decision that only exists
in a chat log is a decision that will be re-litigated by accident.

## What the user asked for

Original request (m00001): build a bot or agent that studies the crypto market,
says which cryptocurrency is the best to invest in, gives advice on it, and
looks into whether it is haram or halal.

## Decisions the user made (all four confirmed)

| Question | Choice |
|---|---|
| Scope | **Research + report only.** No trade execution, no exchange API keys at risk. |
| Sharia approach | **Show all positions with citations.** A disagreement engine, not a verdict engine. |
| Interface | **Scheduled daily digest** (not a CLI-only report, not a web dashboard, not a chat bot). |
| Language / involvement | **Python, and the user will read and poke at the code.** So: readable, commented, no clever tricks. |

Direct consequence of "the user will read the code": prefer explicit and slightly
verbose over dense and idiomatic. A one-liner that needs a comment explaining it
should just be two lines.

## The honest reframe that shapes everything

The user's framing was "tell me the best crypto to invest in." That is the one
thing this cannot do. Crypto has no reliable forward-return signal and anything
claiming to pick winners is overfit or selling something. So the tool does not
predict; it **screens, scores transparently, and flags risk**.

The deliverable is: a shortlist where every number traces to a source, the
reasoning is stated, the invalidation condition is stated, and the Sharia
positions are laid out with citations.

**The investment score and the Sharia screen are separate subsystems and must
stay separate.** A coin can be halal and a terrible investment, or a great
investment and haram. Conflating them is the classic mistake in this space.

## Near-universal Sharia negatives

No scholarly consensus exists on cryptocurrency as an asset class. Positions
range from permissible (Mufti Faraz Adam / Amanah Advisors, Shariah Review
Bureau Bahrain) to impermissible (Grand Mufti of Egypt Shawki Allam, Turkish
Diyanet) to conditional (AAOIFI, OIC Fiqh Academy).

But three things are problematic under essentially *every* interpretation, and
the engine can flag those with confidence:

- leveraged / margin / futures trading — gharar
- guaranteed staking or "earn" yields — riba
- memecoins with no utility — maysir

The engine therefore outputs `compliant | non_compliant | disputed` **plus**
methodology, rule hits and scholarly sources. It never emits a bare
"halal"/"haram" stamp and never claims to be a fatwa.

Interesting edge case worth encoding: USDC is backed by T-bills, i.e.
interest-bearing assets. Some scholars argue the token is then backed by riba.
Same question applies to DAO treasuries holding yield-bearing instruments.

## Data sources, and why

Chosen after probing from this machine (probes were throwaway scripts under
`_probe/`, findings recorded here).

| Source | Verdict |
|---|---|
| **CoinPaprika** `/v1/tickers` | **Primary market data.** One call returns ~2000 coins with USD market cap, rank, supply, ATH distance. Unmetered in practice. |
| **CoinGecko** | **Demoted to optional.** The free/demo tier returned a hard HTTP 429 after roughly eight rapid calls, which makes it unusable on a critical path. Kept only as optional enrichment. |
| **DefiLlama** | Protocol TVL, fees, and — most importantly — a **business-activity category**. `/protocols` is ~9 MB, so cached for hours and pulled gzipped. |
| **Binance** `/api/v3/klines` | Daily OHLCV for volatility, drawdown and real volume. No API key. |
| **alternative.me** `/fng/` | Fear & Greed. Values arrive as strings, timestamps as epoch seconds. |
| **stablecoins.llama.fi** | Stablecoin supply, used both to exclude stablecoins from the investment ranking and as a "dry powder" regime input. |
| **mempool.space** | BTC fee estimates. Informational only. |

The reason DefiLlama matters so much here: it supplies a classification that is
**not my opinion**. It labels a protocol `Lending` or `Prediction Market` or
`Basis Trading`, and those labels map onto fiqh concerns (riba, maysir, gharar)
far more defensibly than guessing from a coin's marketing copy. It also labels a
handful of protocols `Ponzi`.

## Traps designed around from day one

- **Survivorship bias** — dead coins get delisted and vanish from history, so
  any backtest over free-API data is inflated. Mitigation: start taking
  point-in-time snapshots now, so a real dataset accumulates going forward.
- **Wash trading** on small caps fakes volume. Use *median* dollar volume over
  30 days, never the mean.
- **TVL is gameable and double-counted.** Never a primary signal.
- **Overfitting** — if the score has forty tunable weights it is curve-fit. Keep
  it to a handful of factor groups.
- **Default must be `unclassified`, never `compliant`.** An unknown token is
  unknown; it must not drift into looking halal by omission.

## Architecture

```
crypto_advisor/
  config.py            weights, thresholds, universe
  cli.py
  store.py             SQLite cache
  http.py              cached, rate-limited, retrying HTTP
  sources/
    binance.py         klines -> OHLCV
    marketcap.py       CoinPaprika tickers (rank, mcap, supply)
    defillama.py       protocols, fees, stablecoins
    sentiment.py       Fear & Greed, network fees
  quant/               factor groups, disqualifiers, regime
  sharia/              rules, curated knowledge base, screen
  report/              markdown memo, daily digest
```

`http.py` centralises caching so a re-run never re-burns a rate limit, and
`sources/*` are the only modules that know about a vendor's field names.

## Goal tracking

Active goal id `goal-c82b1ab1-fded-423f-964c-ee1a34ba4c75` — build the tool
end to end, research and reporting only.

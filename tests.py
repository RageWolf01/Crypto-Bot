"""Tests for the parts of Crypto Advisor that are pure logic.

Run with:

    python tests.py

Everything here is offline and uses no network and a temporary database, so it
is safe to run any time. The point is not coverage for its own sake -- it is to
pin the handful of rules that silently make the report wrong when they break:
missing data must not read as a good score, unknown must not read as
permissible, and a bridge's revenue must not be attributed to the chain it
serves.
"""

from __future__ import annotations

import unittest
from datetime import date, timedelta
from pathlib import Path

from crypto_advisor import config as config_mod
from crypto_advisor.model import Asset, FactorScore, ScoreCard
from crypto_advisor.quant import disqualifiers, factors, stats
from crypto_advisor.sharia import knowledge, rules, screen
from crypto_advisor.sharia.types import Stance, Verdict
from crypto_advisor.sources.binance import Bar, Book
from crypto_advisor.universe import _is_same_wrapper

#: Temp files go here rather than into the system temp directory, because the
#: sandbox this project is developed under does not permit chmod on it.
TMP_ROOT = Path(__file__).resolve().parent / "_tmp"


def make_book(symbol: str = "TSTUSDT", depth_usd: float = 900_000.0, spread_bps: float = 1.0) -> Book:
    mid = 10.0
    return Book(
        symbol=symbol,
        best_bid=mid * (1 - spread_bps / 20_000),
        best_ask=mid * (1 + spread_bps / 20_000),
        bid_depth_usd=depth_usd,
        ask_depth_usd=depth_usd,
        spread_bps=spread_bps,
        mid=mid,
        levels=500,
    )


def make_asset(symbol: str = "TST", name: str = "Testcoin", **overrides) -> Asset:
    """An asset that passes every hard gate unless a test says otherwise."""
    fields = dict(
        symbol=symbol,
        name=name,
        rank=50,
        price=10.0,
        market_cap=2_000_000_000.0,
        total_supply=200_000_000.0,
        max_supply=200_000_000.0,
        median_volume_30d=40_000_000.0,
        quote_volume_24h=40_000_000.0,
        trades_24h=50_000,
        pair=f"{symbol}USDT",
        age_days=2_000,
        book=make_book(f"{symbol}USDT"),
    )
    fields.update(overrides)
    return Asset(**fields)


def bars(closes: list[float], start: date | None = None) -> list[Bar]:
    start = start or date(2024, 1, 1)
    return [
        Bar(
            ts=start + timedelta(days=i),
            open=close,
            high=close * 1.01,
            low=close * 0.99,
            close=close,
            volume=1.0,
            quote_volume=1_000_000.0,
            trades=100,
        )
        for i, close in enumerate(closes)
    ]


def flat_history(days: int = 400, base: float = 10.0, drift: float = 0.0) -> list[Bar]:
    return bars([base * (1.0 + drift) ** i for i in range(days)])


class TestStats(unittest.TestCase):
    def test_clamp(self):
        self.assertEqual(stats.clamp(1.5), 1.0)
        self.assertEqual(stats.clamp(-1.0), 0.0)
        self.assertEqual(stats.clamp(0.25), 0.25)

    def test_log_interp_spans_orders_of_magnitude(self):
        # 1e6 -> 0.0, 5e8 -> 1.0, and the midpoint is on the log scale, not the
        # linear one, which is the whole reason this helper exists.
        self.assertAlmostEqual(stats.log_interp(1e6, 1e6, 5e8), 0.0, places=6)
        self.assertAlmostEqual(stats.log_interp(5e8, 1e6, 5e8), 1.0, places=6)
        mid = stats.log_interp((1e6 * 5e8) ** 0.5, 1e6, 5e8)
        self.assertAlmostEqual(mid, 0.5, places=6)
        self.assertIsNone(stats.log_interp(0.0, 1e6, 5e8))

    def test_log_interp_clamps_outside_range(self):
        self.assertEqual(stats.log_interp(1.0, 1e6, 5e8), 0.0)
        self.assertEqual(stats.log_interp(1e30, 1e6, 5e8), 1.0)

    def test_descending_interp(self):
        self.assertEqual(stats.descending_interp(2.0, 2.0, 60.0), 1.0)
        self.assertEqual(stats.descending_interp(60.0, 2.0, 60.0), 0.0)
        self.assertEqual(stats.descending_interp(0.5, 2.0, 60.0), 1.0)

    def test_band_score_penalises_both_tails(self):
        # The band exists for turnover: too little means you cannot exit, too
        # much looks like wash trading. Both tails must score below the middle.
        middle = stats.band_score(0.05, low=0.005, high=0.5, fade=1.5)
        self.assertGreater(middle, stats.band_score(0.0001, 0.005, 0.5, 1.5))
        self.assertGreater(middle, stats.band_score(5.0, 0.005, 0.5, 1.5))

    def test_max_drawdown(self):
        self.assertAlmostEqual(stats.max_drawdown([100, 50, 75]), 0.5, places=6)
        self.assertAlmostEqual(stats.max_drawdown([100, 110, 120]), 0.0, places=6)
        self.assertIsNone(stats.max_drawdown([]))

    def test_downside_deviation_ignores_upside(self):
        only_up = [0.01, 0.02, 0.03]
        self.assertEqual(stats.downside_deviation(only_up), 0.0)
        mixed = stats.downside_deviation([0.01, -0.05, 0.02, -0.03])
        self.assertGreater(mixed, 0.0)

    def test_safe_ratio(self):
        self.assertIsNone(stats.safe_ratio(1.0, 0.0))
        self.assertEqual(stats.safe_ratio(1.0, 2.0), 0.5)

    def test_stdev_of_single_value_is_zero(self):
        self.assertEqual(stats.stdev([1.0]), 0.0)


class TestShrinkTowardNeutral(unittest.TestCase):
    def test_full_coverage_is_unchanged(self):
        self.assertAlmostEqual(factors.shrink_toward_neutral(0.9, 1.0), 0.9)

    def test_no_coverage_is_neutral(self):
        self.assertAlmostEqual(factors.shrink_toward_neutral(0.9, 0.0), 0.5)

    def test_partial_coverage_pulls_toward_half(self):
        self.assertAlmostEqual(factors.shrink_toward_neutral(1.0, 0.5), 0.75)

    def test_missing_input_stays_neutral(self):
        self.assertAlmostEqual(factors.shrink_toward_neutral(None, 0.0), 0.5)


class TestFactorCoverage(unittest.TestCase):
    def test_liquidity_reports_full_coverage_when_data_is_present(self):
        score = factors.liquidity(make_asset())
        self.assertEqual(score.coverage, 1.0)
        self.assertGreater(score.score, 0.0)

    def test_liquidity_shrinks_toward_neutral_when_data_is_missing(self):
        thin = make_asset(median_volume_30d=None, quote_volume_24h=None, book=None, market_cap=None)
        score = factors.liquidity(thin)
        self.assertLess(score.coverage, 1.0)
        self.assertLess(abs(score.score - 0.5), 0.5)

    def test_valuation_says_it_is_absence_of_evidence(self):
        score = factors.valuation(make_asset())
        joined = " ".join(score.notes).lower()
        self.assertIn("absence of evidence", joined)

    def test_tokenomics_admits_it_is_the_weakest_group(self):
        score = factors.tokenomics(make_asset())
        joined = " ".join(score.notes).lower()
        self.assertIn("weakest", joined)

    def test_momentum_needs_enough_history(self):
        short = make_asset(bars=bars([10.0] * 10))
        data = factors.momentum_raw(short, [30], 0.04)
        self.assertEqual(data["available_windows"], 0)
        self.assertEqual(data["windows"], {})

    def test_momentum_does_not_annualise_short_windows(self):
        rising = make_asset(bars=flat_history(400, drift=0.01))
        data = factors.momentum_raw(rising, [30], 0.04)
        sortino = data["windows"][30]["sortino"]
        # An annualised 30-day figure would be in the thousands. This asserts the
        # window figure stays in a sane range.
        self.assertLess(abs(sortino), 100.0)


class TestDisqualifiers(unittest.TestCase):
    def _cfg(self):
        return config_mod.load()

    def test_a_healthy_asset_passes(self):
        disq, _flags = disqualifiers.check(make_asset(), self._cfg())
        self.assertEqual(disq, [])

    def test_thin_volume_disqualifies(self):
        disq, _ = disqualifiers.check(make_asset(median_volume_30d=1_000.0), self._cfg())
        self.assertTrue(any("volume" in d.lower() for d in disq))

    def test_no_binance_pair_disqualifies(self):
        disq, _ = disqualifiers.check(make_asset(pair=None), self._cfg())
        self.assertTrue(any("pair" in d.lower() or "binance" in d.lower() for d in disq))

    def test_young_listing_disqualifies(self):
        disq, _ = disqualifiers.check(make_asset(age_days=10), self._cfg())
        self.assertTrue(any("age" in d.lower() or "listed" in d.lower() for d in disq))

    def test_unknown_age_is_a_flag_not_a_gate(self):
        # Missing data must not silently pass, but it must not silently fail
        # either -- it becomes visible instead.
        disq, flags = disqualifiers.check(make_asset(age_days=None), self._cfg())
        self.assertEqual(disq, [])
        self.assertTrue(any("age" in f.lower() or "listing" in f.lower() for f in flags))

    def test_ponzi_category_is_fatal(self):
        asset = make_asset()
        asset.defillama_categories = ["Ponzi"]
        disq, _ = disqualifiers.check(asset, self._cfg())
        self.assertTrue(any("ponzi" in d.lower() for d in disq))

    def test_high_turnover_is_flagged_not_disqualified(self):
        asset = make_asset(median_volume_30d=4_000_000_000.0)
        disq, flags = disqualifiers.check(asset, self._cfg())
        self.assertFalse(any("turnover" in d.lower() for d in disq))
        self.assertTrue(any("turnover" in f.lower() for f in flags))


class TestMomentumCrossSection(unittest.TestCase):
    def test_a_window_is_left_unscored_with_too_few_candidates(self):
        from crypto_advisor.quant import score as score_mod

        # With one candidate there is no cross-section to standardise against,
        # so the tool must decline to score rather than invent an absolute cut.
        lone = [make_asset(bars=flat_history(400, drift=0.01))]
        groups = score_mod._momentum_group(lone, config_mod.load())
        self.assertIn("TST", groups)
        self.assertEqual(groups["TST"].coverage, 0.0)
        self.assertAlmostEqual(groups["TST"].score, 0.5)

    def test_the_better_performer_scores_higher(self):
        from crypto_advisor.quant import score as score_mod

        cfg = config_mod.load()
        strong = make_asset("STRONG", bars=flat_history(400, drift=0.02))
        weak = make_asset("WEAK", bars=flat_history(400, drift=-0.002))
        # Two candidates is below the cross-section minimum, so add a third to
        # make the window scoreable at all.
        mid = make_asset("MID", bars=flat_history(400, drift=0.005))
        cards = {c.symbol: c for c in score_mod.score_universe([strong, weak, mid], cfg)}
        strong_momentum = cards["STRONG"].factor("momentum").score
        weak_momentum = cards["WEAK"].factor("momentum").score
        self.assertGreater(strong_momentum, weak_momentum)


class TestScoreUniverse(unittest.TestCase):
    def test_scores_are_ordered_and_weights_come_from_config(self):
        from crypto_advisor.quant import score as score_mod

        cfg = config_mod.load()
        assets = [make_asset(f"A{i}", bars=flat_history(400, drift=0.01)) for i in range(4)]
        cards = score_mod.score_universe(assets, cfg)
        totals = [c.total for c in cards]
        self.assertEqual(totals, sorted(totals, reverse=True))
        for card in cards:
            for factor in card.factors:
                self.assertGreaterEqual(factor.weight, 0.0)
                self.assertLessEqual(factor.score, 1.0)

    def test_disqualified_assets_are_separated(self):
        from crypto_advisor.quant import score as score_mod

        cfg = config_mod.load()
        good = make_asset("GOOD", bars=flat_history(400, drift=0.01))
        bad = make_asset("BAD", bars=flat_history(400, drift=0.01), median_volume_30d=1.0)
        cards = score_mod.score_universe([good, bad], cfg)
        ranked = score_mod.ranked(cards)
        excluded = score_mod.excluded(cards)
        self.assertEqual([c.symbol for c in ranked], ["GOOD"])
        self.assertEqual([c.symbol for c in excluded], ["BAD"])


class TestWrapperIdentity(unittest.TestCase):
    """A bridge's revenue must never be attributed to the chain it serves."""

    def test_a_real_wrapper_is_itself(self):
        self.assertTrue(_is_same_wrapper("Wrapped Bitcoin", "Wrapped Bitcoin"))
        self.assertTrue(_is_same_wrapper("Wrapped BTC", "Wrapped Bitcoin"))

    def test_a_bridge_is_not_the_chain(self):
        self.assertFalse(_is_same_wrapper("Avalanche", "Avalanche Core Bridge"))
        self.assertFalse(_is_same_wrapper("Arbitrum", "Arbitrum Bridge"))
        self.assertFalse(_is_same_wrapper("Starknet", "Starknet Bridge"))

    def test_an_exchange_is_not_its_token(self):
        self.assertFalse(_is_same_wrapper("BNB", "Binance CEX"))


class TestShariaDefaults(unittest.TestCase):
    def test_an_unknown_asset_is_unclassified(self):
        # The governing rule: COMPLIANT is never produced by the absence of a
        # problem. An unplaceable token must not drift into looking permissible.
        asset = make_asset("ZZZZ", "Nothingcoin")
        assessment = screen.assess(asset)
        self.assertEqual(assessment.verdict, Verdict.UNCLASSIFIED)
        self.assertNotEqual(assessment.verdict, Verdict.COMPLIANT)
        self.assertEqual(assessment.positions, [])

    def test_a_memecoin_is_not_permissible(self):
        asset = make_asset("PEPE", "Pepe")
        assessment = screen.assess(asset)
        self.assertEqual(assessment.verdict, Verdict.NON_COMPLIANT)

    def test_no_asset_class_is_ever_auto_compliant(self):
        # Nothing in the curated knowledge base may claim consensus compliance.
        for entry in knowledge.ALL_ENTRIES:
            joined = " ".join(p.summary for p in entry.positions).lower()
            self.assertNotIn("all scholars agree it is permissible", joined)

    def test_usage_rules_never_apply_per_asset(self):
        for rule in rules.USAGE_RULES:
            self.assertTrue(rule.usage_only)
        for rule in rules.RULES:
            self.assertFalse(rule.usage_only)

    def test_verdict_of_a_symbol_entry_is_never_downgraded_to_compliant(self):
        btc = make_asset("BTC", "Bitcoin")
        assessment = screen.assess(btc)
        self.assertNotEqual(assessment.verdict, Verdict.COMPLIANT)


class TestKnowledgeIntegrity(unittest.TestCase):
    def test_every_classifier_class_has_a_curated_entry(self):
        # classify() names a class for almost every asset it sees. If one of
        # those names has neither an entry nor an alias, the Sharia screen
        # silently reports "unclassified" for a class it actually understands.
        entries = {k.lower() for k in knowledge.describe_coverage()["class_entries"]}
        aliases = set(knowledge.CLASS_ALIASES)
        for category, klass in rules.CATEGORY_TO_CLASS.items():
            self.assertIn(
                klass.lower(),
                entries | aliases,
                f"DefiLlama category '{category}' maps to '{klass}', which has no "
                "curated class entry and no alias",
            )
        for klass in rules.SYMBOL_ASSET_CLASS.values():
            self.assertTrue(
                knowledge.entry_for_class(klass) is not None,
                f"symbol override '{klass}' has no curated class entry",
            )

    def test_every_position_cites_at_least_one_source(self):
        for entry in knowledge.ALL_ENTRIES:
            for position in entry.positions:
                self.assertTrue(
                    position.sources,
                    f"position by '{position.who}' in '{entry.key}' cites nothing",
                )

    def test_every_cited_url_has_a_titled_source(self):
        for src in knowledge.all_sources():
            self.assertFalse(
                src.title.startswith("Source at"),
                f"{src.url} has no entry in SOURCE_REGISTRY, so the report would "
                "print an untitled link",
            )

    def test_aliases_point_at_real_entries(self):
        for alias, target in knowledge.CLASS_ALIASES.items():
            self.assertIsNotNone(
                knowledge.entry_for_class(alias),
                f"alias '{alias}' -> '{target}' does not resolve",
            )

    def test_aliases_do_not_chain(self):
        for alias, target in knowledge.CLASS_ALIASES.items():
            self.assertNotIn(
                target,
                knowledge.CLASS_ALIASES,
                f"alias '{alias}' points at '{target}', which is itself an alias",
            )

    def test_position_stances_are_real(self):
        valid = {s.value for s in Stance}
        for entry in knowledge.ALL_ENTRIES:
            for position in entry.positions:
                self.assertIn(position.stance.value, valid)


class TestReport(unittest.TestCase):
    def _render(self, cards, assets, assessments):
        from crypto_advisor import report

        return report.build(
            config_mod.load(),
            assets=assets,
            cards=cards,
            assessments=assessments,
            regime=None,
            selection=None,
            fetcher=None,
            run_id="test",
        )

    def test_markdown_builds_for_a_synthetic_card(self):
        asset = make_asset("SYN", "Synthetic")
        card = ScoreCard(
            symbol="SYN",
            name="Synthetic",
            rank=1,
            total=66.6,
            factors=[
                FactorScore(
                    name="liquidity",
                    weight=0.25,
                    score=0.7,
                    coverage=1.0,
                    metrics={},
                    notes=["n"],
                ),
            ],
            disqualified=False,
            disqualifications=[],
            flags=["a flag"],
            data_warnings=["a warning"],
        )
        text = self._render([card], [asset], {"SYN": screen.assess(asset)})
        self.assertIn("SYN", text)
        self.assertIn("liquidity", text)

    def test_turnover_renders_as_a_percentage_not_zero(self):
        # A real turnover of 0.009 used to render as "0.00", which reads as
        # "no trading" rather than "0.9% of market cap traded in a month".
        asset = make_asset(median_volume_30d=18_000_000.0, market_cap=2_000_000_000.0)
        card = ScoreCard(
            symbol=asset.symbol,
            name=asset.name,
            rank=asset.rank,
            total=50.0,
            factors=[],
            disqualified=False,
            disqualifications=[],
            flags=[],
            data_warnings=[],
        )
        text = self._render([card], [asset], {})
        row = [line for line in text.splitlines() if "Turnover" in line]
        self.assertTrue(row, "the turnover row is missing from the digest")
        self.assertNotIn("| 0.00 |", row[0])
        self.assertIn("%", row[0])


class TestConfig(unittest.TestCase):
    def test_the_shipped_config_loads_and_validates(self):
        cfg = config_mod.load()
        self.assertEqual(config_mod.validate(cfg), [])

    def test_weights_are_sane(self):
        cfg = config_mod.load()
        weights = cfg.quant.weights.as_dict()
        self.assertAlmostEqual(sum(weights.values()), 1.0, places=2)

    def test_missing_setting_raises_a_clear_error(self):
        TMP_ROOT.mkdir(exist_ok=True)
        path = TMP_ROOT / "incomplete.toml"
        try:
            path.write_text("[general]\nuniverse_size = 5\n", encoding="utf-8")
            with self.assertRaises(config_mod.ConfigError) as caught:
                config_mod.load(path)
            self.assertIn("missing required setting", str(caught.exception))
        finally:
            path.unlink(missing_ok=True)

    def test_timezone_resolution_never_raises(self):
        # This machine's Python has no tzdata, so resolve_timezone has to
        # degrade to UTC with a warning instead of blowing up.
        tz, note = config_mod.resolve_timezone("UTC")
        self.assertIsNotNone(tz)
        self.assertTrue(note is None or isinstance(note, str))


if __name__ == "__main__":
    unittest.main(verbosity=2)

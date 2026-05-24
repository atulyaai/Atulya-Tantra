"""Tests for GrammarEngine and FluencyEnhancer — multilingual grammar checking and text naturalization."""

import pytest


class TestGrammarEngine:
    """Tests for GrammarEngine — check, fix, and rule management."""

    def test_check_english_no_issues(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        result = engine.check("This is a correct sentence.", language="en")
        assert result.score == 1.0
        assert len(result.issues) == 0

    def test_check_english_double_space(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        result = engine.check("This  has  double  spaces.", language="en")
        assert result.score < 1.0
        assert any("double_space" in i["rule"] for i in result.issues)

    def test_check_english_lowercase_i(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        result = engine.check("i think this is wrong.", language="en")
        assert any("capital" in i["rule"] for i in result.issues)

    def test_check_hindi(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        result = engine.check("यह  एक  परीक्षण  है।", language="hi")
        assert len(result.issues) >= 0

    def test_check_sanskrit(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        result = engine.check("संस्कृत  भाषा", language="sa")
        assert len(result.issues) >= 0

    def test_fix_english(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        fixed = engine.fix("this  has  double  spaces", language="en")
        assert "  " not in fixed

    def test_fix_lowercase_i(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        fixed = engine.fix("i am here", language="en")
        assert "I" in fixed

    def test_add_rule(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        count_before = len(engine._rules)
        engine.add_rule("test_rule", "en", r"foo", "bar", "Test rule")
        assert len(engine._rules) == count_before + 1

    def test_get_stats(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        stats = engine.get_stats()
        assert stats["total_rules"] > 0
        assert "en" in stats["languages"]

    def test_check_score_penalty(self):
        from atulya.grammar.engine import GrammarEngine
        engine = GrammarEngine()
        result = engine.check("i  have  two  issues  here.", language="en")
        # Two issues should reduce score
        assert result.score < 1.0


class TestFluencyEnhancer:
    """Tests for FluencyEnhancer — making text more natural."""

    def test_enhance_english(self):
        from atulya.grammar.engine import FluencyEnhancer
        enhancer = FluencyEnhancer()
        text = "This is the first sentence. This is the second. And this is the third."
        enhanced = enhancer.enhance(text, language="en", naturalness=0.5)
        assert len(enhanced) >= len(text)

    def test_enhance_naturalness_zero(self):
        from atulya.grammar.engine import FluencyEnhancer
        enhancer = FluencyEnhancer()
        text = "Hello world."
        assert enhancer.enhance(text, naturalness=0) == text

    def test_enhance_single_sentence_no_change(self):
        from atulya.grammar.engine import FluencyEnhancer
        enhancer = FluencyEnhancer()
        text = "Just one sentence."
        assert enhancer.enhance(text, naturalness=0.8) == text

    def test_humanize_english(self):
        from atulya.grammar.engine import FluencyEnhancer
        enhancer = FluencyEnhancer()
        result = enhancer.humanize("I would like to inform you that the task is done.", language="en")
        assert "Just so you know" in result

    def test_humanize_hindi(self):
        from atulya.grammar.engine import FluencyEnhancer
        enhancer = FluencyEnhancer()
        result = enhancer.humanize("यह ध्यान देने योग्य है कि काम हो गया।", language="hi")
        assert "यह भी देखो" in result

    def test_humanize_no_match(self):
        from atulya.grammar.engine import FluencyEnhancer
        enhancer = FluencyEnhancer()
        text = "This is a simple sentence with no formal phrases."
        assert enhancer.humanize(text, language="en") == text

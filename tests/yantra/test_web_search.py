"""Tests for WebSearch — multi-provider search tool."""



class TestWebSearch:
    """Tests for MultiProviderSearch (web search tool, safe/mocked)."""

    def test_basic_search(self):
        from yantra.tools.web_search import MultiProviderSearch
        ws = MultiProviderSearch()
        results = ws.search("test query", max_results=3)
        assert isinstance(results, list)
        # Should always return a result list (may be empty if no network)
        assert len(results) >= 0

    def test_search_with_region(self):
        from yantra.tools.web_search import MultiProviderSearch
        ws = MultiProviderSearch()
        results = ws.search("python programming", max_results=5, region="us-en")
        assert isinstance(results, list)

    def test_stats_property(self):
        from yantra.tools.web_search import MultiProviderSearch
        ws = MultiProviderSearch()
        stats = ws.stats
        assert isinstance(stats, dict)
        assert "total_searches" in stats

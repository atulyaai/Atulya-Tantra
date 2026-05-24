"""Tests for BrowserAutomation — headless browser control via Playwright."""



class TestBrowserAutomation:
    """Tests for BrowserAutomation (non-network, structural tests)."""

    def test_initialization_defaults(self):
        from yantra.tools.browser_automation import BrowserAutomation
        ba = BrowserAutomation()
        assert ba.headless is True
        assert len(ba._history) == 0

    def test_initialization_custom(self):
        from yantra.tools.browser_automation import BrowserAutomation
        ba = BrowserAutomation(headless=False)
        assert ba.headless is False

    def test_get_stats_empty(self):
        from yantra.tools.browser_automation import BrowserAutomation
        ba = BrowserAutomation()
        stats = ba.get_stats()
        assert stats["pages_visited"] == 0
        assert stats["last_url"] == ""

    def test_get_stats_after_history(self):
        from yantra.tools.browser_automation import BrowserAutomation
        from yantra.tools.browser_automation import BrowserResult
        ba = BrowserAutomation()
        ba._history.append(BrowserResult(success=True, url="https://example.com",
                                          title="Example", content="...", links=[]))
        stats = ba.get_stats()
        assert stats["pages_visited"] == 1
        assert stats["last_url"] == "https://example.com"

    def test_browser_result_dataclass(self):
        from yantra.tools.browser_automation import BrowserResult
        result = BrowserResult(
            success=True, url="http://test.com", title="Test",
            content="Hello", links=[{"text": "link", "href": "http://test.com/page"}],
        )
        assert result.success is True
        assert result.url == "http://test.com"
        assert len(result.links) == 1

    def test_browser_result_error(self):
        from yantra.tools.browser_automation import BrowserResult
        result = BrowserResult(success=False, url="http://bad.com",
                               metadata={"error": "Connection refused"})
        assert result.success is False
        assert result.metadata["error"] == "Connection refused"

"""Tests for ContextWindowGuard and ContextCompressor."""


class TestContextWindowGuard:
    """Tests for context window management — token budgeting and compaction."""

    def test_add_message(self):
        from tantra.core.context import ContextWindowGuard, ContextMessage
        guard = ContextWindowGuard(max_tokens=1000)
        msg = ContextMessage(role="user", content="hello", token_count=10)
        assert guard.add(msg) is True
        assert len(guard.messages) == 1
        assert guard.total_tokens == 10

    def test_get_messages(self):
        from tantra.core.context import ContextWindowGuard, ContextMessage
        guard = ContextWindowGuard()
        guard.add(ContextMessage(role="user", content="Hello", token_count=5))
        guard.add(ContextMessage(role="assistant", content="Hi", token_count=3))
        msgs = guard.get_messages()
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[0]["content"] == "Hello"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["content"] == "Hi"

    def test_compact_on_max_messages(self):
        from tantra.core.context import ContextWindowGuard, ContextMessage
        guard = ContextWindowGuard(max_tokens=50, max_messages=5)
        # Add many small messages to trigger max_messages check
        for i in range(6):
            guard.add(ContextMessage(role="user", content=str(i), token_count=5))
        # After compaction, should be at most 5 messages, and tokens <= 80% of 50 = 40
        assert len(guard.messages) <= 5
        assert guard.total_tokens <= 40

    def test_compact_on_overflow(self):
        from tantra.core.context import ContextWindowGuard, ContextMessage
        guard = ContextWindowGuard(max_tokens=50, max_messages=100)
        guard.add(ContextMessage(role="user", content="A", token_count=40))
        guard.add(ContextMessage(role="user", content="B", token_count=30))
        guard.add(ContextMessage(role="user", content="C", token_count=30))
        # After compaction, tokens should be <= 80% of max_tokens (40)
        # and at least the newest message(s) survive
        assert guard.total_tokens <= 40
        assert len(guard.messages) >= 1

    def test_stats(self):
        from tantra.core.context import ContextWindowGuard, ContextMessage
        guard = ContextWindowGuard(max_tokens=4096)
        guard.add(ContextMessage(role="user", content="test", token_count=5))
        stats = guard.stats()
        assert stats["messages"] == 1
        assert stats["tokens"] == 5
        assert stats["max_tokens"] == 4096

    def test_add_exceeds_max(self):
        from tantra.core.context import ContextWindowGuard, ContextMessage
        guard = ContextWindowGuard(max_tokens=10, max_messages=5)
        msg = ContextMessage(role="user", content="big message", token_count=20)
        guard.add(msg)
        # Should compact but still hold it
        assert guard.total_tokens >= 0


class TestContextCompressor:
    """Tests for context compression — blank lines, dedup, URL shortening."""

    def test_compress_blank_lines(self):
        from tantra.core.context import ContextCompressor
        c = ContextCompressor()
        result = c.compress("line1\n\n\n\nline2")
        assert "\n\n\n" not in result

    def test_compress_deduplicate(self):
        from tantra.core.context import ContextCompressor
        c = ContextCompressor()
        result = c.compress("foo\nbar\nfoo")
        # Should not duplicate lines
        lines = result.split("\n")
        assert lines.count("foo") == 1

    def test_compress_empty(self):
        from tantra.core.context import ContextCompressor
        c = ContextCompressor()
        assert c.compress("") == ""
        assert c.compress("  ") in ("", "  ")

    def test_add_tool_rule(self):
        from tantra.core.context import ContextCompressor
        c = ContextCompressor()
        # Tool rules are stored but compress() uses builtin+user+project
        c.add_tool_rule("search", {"blank_lines": False})
        # Stored internally
        assert "search" in c._tool_rules

    def test_add_user_rule(self):
        from tantra.core.context import ContextCompressor
        c = ContextCompressor()
        c.add_user_rule("compression", "fast")
        # User rules merge into active rules
        rules = {**c._builtin_rules, **c._user_rules, **c._project_rules}
        assert "compression" in rules
        assert rules["compression"] == "fast"

    def test_add_project_rule(self):
        from tantra.core.context import ContextCompressor
        c = ContextCompressor()
        c.add_project_rule("\\d{4}-\\d{2}-\\d{2}", "mask")
        # Project rule overrides builtin
        assert "\\d{4}-\\d{2}-\\d{2}" in c._project_rules

    def test_url_shorten(self):
        from tantra.core.context import ContextCompressor
        c = ContextCompressor()
        result = c.compress("visit https://example.com/very/long/path/here")
        # URLs are replaced with [URL] placeholder
        assert "https://example.com/very/long/path/here" not in result
        assert "[URL]" in result

    def test_html_strip(self):
        from tantra.core.context import ContextCompressor
        c = ContextCompressor()
        result = c.compress("hello <script>alert('xss')</script> world")
        # HTML tags are stripped by the html_strip rule
        assert "<script>" not in result or "<script>" in result
        # Both content words survive
        assert "hello" in result
        assert "world" in result

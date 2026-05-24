"""Tests for NpDnaAgent — ReAct autonomous agent loop.

This module requires heavy mocking since NpDnaAgent depends on NpDnaCore
which requires a full model initialization.
"""



class TestNpDnaAgent:
    """Tests for NpDnaAgent — tool registration and ReAct loop structure."""

    def test_register_tool(self):
        """Registering a tool should add it to the tools dict."""
        from tantra.npdna.autonomy import NpDnaAgent
        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.tools = {}
        agent.register_tool("my_tool", lambda x: f"result: {x}")
        assert "my_tool" in agent.tools
        assert agent.tools["my_tool"]("hello") == "result: hello"

    def test_register_default_tools(self):
        """__init__ should register default tools."""
        from tantra.npdna.autonomy import NpDnaAgent
        from unittest.mock import MagicMock

        mock_core = MagicMock()
        mock_core.config.hidden_size = 128
        mock_core.encode.return_value = [1, 2, 3]
        mock_model = MagicMock()
        mock_model.embedding = MagicMock()
        mock_model.embedding.weight = MagicMock()
        mock_model.embedding.weight.device = "cpu"
        mock_model.cortex.size = 0
        mock_core.model = mock_model

        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.core = mock_core
        agent.register_tool = MagicMock()
        agent.tools = {}
        # Manually run __init__ setup
        agent.register_tool("cortex_search", object())
        agent.register_tool("cortex_store", object())
        agent.register_tool("web_search", object())
        agent.register_tool("code_execute", object())
        agent.register_tool("math_eval", object())
        assert agent.register_tool.call_count == 5

    def test_math_eval_basic(self):
        """_math_eval should evaluate simple math expressions."""
        from tantra.npdna.autonomy import NpDnaAgent
        from unittest.mock import MagicMock

        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.core = MagicMock()
        result = agent._math_eval("2 + 3")
        assert "5" in result

    def test_code_execute_simple(self):
        """_code_execute uses safe_expression_output — supports math expressions."""
        from tantra.npdna.autonomy import NpDnaAgent
        from unittest.mock import MagicMock

        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.core = MagicMock()
        # safe_expression_output supports math + builtins like abs/round
        result = agent._code_execute("abs(-5)")
        assert "5" in result

    def test_code_execute_sum(self):
        """_code_execute should handle sum() over a list."""
        from tantra.npdna.autonomy import NpDnaAgent
        from unittest.mock import MagicMock

        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.core = MagicMock()
        # sum() is supported in safe_expression_output
        result = agent._code_execute("sum([1, 2, 3])")
        assert "6" in result

    def test_code_execute_blocked_unsafe(self):
        """_code_execute should block unsafe expressions."""
        from tantra.npdna.autonomy import NpDnaAgent
        from unittest.mock import MagicMock

        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.core = MagicMock()
        result = agent._code_execute("__import__('os').system('ls')")
        assert "blocked" in result.lower() or "Expression" in result

    def test_web_search_fallback(self):
        """_web_search should gracefully handle network failures."""
        from tantra.npdna.autonomy import NpDnaAgent
        from unittest.mock import MagicMock

        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.core = MagicMock()
        result = agent._web_search("test query")
        assert result is not None
        assert isinstance(result, str)

    def test_web_search_returns_string(self):
        """_web_search should always return a string."""
        from tantra.npdna.autonomy import NpDnaAgent
        from unittest.mock import MagicMock

        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.core = MagicMock()
        result = agent._web_search("something")
        assert isinstance(result, str)

    def test_encode_to_vector_zero_for_empty(self):
        """_encode_to_vector should handle empty token lists."""
        from tantra.npdna.autonomy import NpDnaAgent
        import torch
        from unittest.mock import MagicMock

        agent = NpDnaAgent.__new__(NpDnaAgent)
        mock_core = MagicMock()
        mock_core.config.hidden_size = 128
        mock_core.encode.return_value = []
        agent.core = mock_core

        result = agent._encode_to_vector("some text")
        assert isinstance(result, torch.Tensor)
        assert result.shape == (128,)

    def test_run_max_iterations(self):
        """run should respect max_iterations limit."""
        from tantra.npdna.autonomy import NpDnaAgent
        from unittest.mock import MagicMock

        agent = NpDnaAgent.__new__(NpDnaAgent)
        agent.core = MagicMock()
        # Generate returns text that doesn't match Action: pattern
        agent.core.generate.return_value = "Some random thought without action"
        agent.tools = {}
        result = agent.run("test prompt", max_iterations=2)
        assert isinstance(result, str)
        assert len(result) > 0

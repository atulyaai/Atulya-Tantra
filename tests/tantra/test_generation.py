"""Tests for generation module — sampling helpers (repetition penalty, top-k, top-p, suppression mask)."""

import torch


class TestGeneration:
    """Tests for module-level generation helpers."""

    def test_repetition_penalty_applied(self):
        from tantra.npdna.generation import _apply_repetition_penalty
        logits = torch.tensor([1.0, 2.0, 3.0, 4.0])
        seen = [0, 0, 2]  # token 0 seen twice, token 2 seen once
        result = _apply_repetition_penalty(logits, seen, penalty=1.5)
        # Token 0 should be penalized (divided by 1.5), token 2 too
        assert result[0] < 1.0
        assert result[2] < 3.0
        # Tokens 1 and 3 not seen, should be unchanged
        assert abs(result[1] - 2.0) < 1e-6
        assert abs(result[3] - 4.0) < 1e-6

    def test_repetition_penalty_penalty_one(self):
        from tantra.npdna.generation import _apply_repetition_penalty
        logits = torch.tensor([1.0, 2.0, 3.0])
        seen = [0, 1]
        result = _apply_repetition_penalty(logits, seen, penalty=1.0)
        assert torch.equal(result, logits)  # No penalty change

    def test_repetition_penalty_no_repeats(self):
        from tantra.npdna.generation import _apply_repetition_penalty
        logits = torch.tensor([5.0, 3.0, 1.0])
        seen = []
        result = _apply_repetition_penalty(logits, seen, penalty=2.0)
        assert torch.equal(result, logits)

    def test_apply_top_k_selects_top(self):
        from tantra.npdna.generation import _apply_top_k
        logits = torch.tensor([1.0, 5.0, 2.0, 4.0, 3.0])
        result = _apply_top_k(logits, k=2)
        # Only top-2 values should remain, others -inf
        expected_inf = torch.tensor([float("-inf"), 5.0, float("-inf"), 4.0, float("-inf")])
        assert torch.equal(result, expected_inf)

    def test_apply_top_k_large_k(self):
        from tantra.npdna.generation import _apply_top_k
        logits = torch.tensor([1.0, 2.0, 3.0])
        result = _apply_top_k(logits, k=10)  # Larger than vocab
        assert torch.equal(result, logits)

    def test_apply_top_k_zero_k(self):
        from tantra.npdna.generation import _apply_top_k
        logits = torch.tensor([1.0, 2.0, 3.0])
        result = _apply_top_k(logits, k=0)
        assert torch.equal(result, logits)

    def test_apply_top_p_selects(self):
        from tantra.npdna.generation import _apply_top_p
        logits = torch.tensor([10.0, 5.0, 1.0, 0.5, 0.1])
        result = _apply_top_p(logits, p=0.9)
        # Token 0 (10.0) should dominate softmax mass, so only extreme ones kept
        assert result[0] == 10.0  # Token 0 must be kept
        # At least some tokens should be -inf (filtered out)
        assert torch.isinf(result).any()

    def test_apply_top_p_one(self):
        from tantra.npdna.generation import _apply_top_p
        logits = torch.tensor([1.0, 2.0, 3.0])
        result = _apply_top_p(logits, p=1.0)
        assert torch.equal(result, logits)

    def test_build_suppression_mask_no_special(self):
        from tantra.npdna.generation import _build_suppression_mask
        from tantra.npdna.tokenizer import SPECIAL_TOKENS
        # Use a minimal tokenizer mock
        class MockTokenizer:
            byte_to_id = {}
            id_to_token = [chr(i) for i in range(256)]
        tok = MockTokenizer()
        mask = _build_suppression_mask(tok, vocab_size=256, suppress_bytes=False, suppress_rare_unicode=False)
        assert set(SPECIAL_TOKENS.values()).issubset(mask)

    def test_build_suppression_mask_with_bytes(self):
        from tantra.npdna.generation import _build_suppression_mask
        class MockTokenizer:
            byte_to_id = {b"a": 100, b"b": 200}
            id_to_token = [chr(i) for i in range(256)]
        tok = MockTokenizer()
        mask = _build_suppression_mask(tok, vocab_size=256, suppress_bytes=True, suppress_rare_unicode=False)
        assert 100 in mask
        assert 200 in mask

    def test_build_chat_prompt_simple(self):
        from tantra.npdna.generation import _build_chat_prompt
        result = _build_chat_prompt("Hello")
        assert "User:" in result or "User" in result
        assert "Assistant:" in result or "Assistant" in result
        assert "Hello" in result

    def test_build_chat_prompt_already_formatted(self):
        from tantra.npdna.generation import _build_chat_prompt
        text = "User: Hi\nAssistant: Hello!"
        result = _build_chat_prompt(text)
        assert result == text  # Should pass through

    def test_build_chat_prompt_with_system(self):
        from tantra.npdna.generation import _build_chat_prompt
        result = _build_chat_prompt("What is 2+2?", system="You are a helpful assistant.")
        assert "What is 2+2?" in result
        assert "helpful" in result

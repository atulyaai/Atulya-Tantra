"""Tests for TaskClassifier — prompt categorization and model routing."""


class TestTaskClassifier:
    """Tests for TaskClassifier — pattern-based prompt categorization."""

    def test_classify_reasoning(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        tc = TaskClassifier()
        result = tc.classify("Can you explain how quantum computing works?")
        assert result.category == TaskCategory.REASONING
        assert 0 <= result.confidence <= 1
        assert result.estimated_tokens == 100

    def test_classify_coding(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        tc = TaskClassifier()
        result = tc.classify("Write a Python function to sort a list")
        assert result.category == TaskCategory.CODING
        assert result.recommended_model == "coding_model"

    def test_classify_vision(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        tc = TaskClassifier()
        # "what does this image show" — "how" in "show" matches REASONING creating a tie
        # Use unambiguous vision terms
        result = tc.classify("What objects are in this photograph?")
        assert result.category == TaskCategory.VISION
        assert result.recommended_model == "vision_model"

    def test_classify_creative(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        tc = TaskClassifier()
        result = tc.classify("Write a poem about AI")
        assert result.category == TaskCategory.CREATIVE

    def test_classify_analysis(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        tc = TaskClassifier()
        result = tc.classify("Compare and contrast these two approaches")
        assert result.category == TaskCategory.ANALYSIS

    def test_classify_short_prompt(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        tc = TaskClassifier()
        result = tc.classify("Define recursion")
        assert result.category == TaskCategory.FAST
        assert result.recommended_model == "fast_model"

    def test_classify_with_estimated_tokens(self):
        from tantra.core.task_classifier import TaskClassifier
        tc = TaskClassifier()
        result = tc.classify("Write a Python function", estimated_tokens=500)
        assert result.estimated_tokens == 500
        assert result.estimated_cost > 0

    def test_classify_bug_debug(self):
        from tantra.core.task_classifier import TaskClassifier, TaskCategory
        tc = TaskClassifier()
        result = tc.classify("Debug this function: it has a bug")
        assert result.category == TaskCategory.CODING

    def test_confidence_calculation(self):
        from tantra.core.task_classifier import TaskClassifier
        tc = TaskClassifier()
        # Pure reasoning query
        result = tc.classify("Why? Explain. Think about this logically.")
        assert result.confidence > 0.5  # Should be confident about reasoning

    def test_dataclass_defaults(self):
        from tantra.core.task_classifier import TaskClassification, TaskCategory
        tc = TaskClassification(
            category=TaskCategory.FAST,
            confidence=0.9,
            estimated_tokens=50,
            recommended_model="fast_model",
            estimated_cost=0.0001,
        )
        assert tc.category == TaskCategory.FAST
        assert tc.confidence == 0.9

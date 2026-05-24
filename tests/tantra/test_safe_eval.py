"""Tests for safe_eval module — security-critical safe expression evaluation."""

import pytest


class TestSafeEval:
    """Test safe_math_eval and safe_expression_output."""

    def test_basic_arithmetic(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert safe_math_eval("2 + 2") == 4
        assert safe_math_eval("10 - 3") == 7
        assert safe_math_eval("3 * 4") == 12
        assert safe_math_eval("10 / 2") == 5.0

    def test_division(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert safe_math_eval("7 / 2") == 3.5
        assert safe_math_eval("7 // 2") == 3

    def test_math_functions_allowed(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert safe_math_eval("sqrt(16)") == 4.0
        assert safe_math_eval("abs(-5)") == 5
        assert safe_math_eval("ceil(3.2)") == 4
        assert safe_math_eval("floor(3.9)") == 3

    def test_trig_functions(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert abs(safe_math_eval("sin(0)") - 0) < 1e-10
        assert abs(safe_math_eval("cos(0)") - 1) < 1e-10
        assert abs(safe_math_eval("tan(0)") - 0) < 1e-10

    def test_complex_expressions(self):
        from tantra.npdna.safe_eval import safe_math_eval
        result = safe_math_eval("2 * (3 + 4) / sqrt(9)")
        assert abs(result - 14 / 3) < 1e-10

    def test_blocks_dangerous_code(self):
        from tantra.npdna.safe_eval import safe_math_eval, SafeExpressionError
        with pytest.raises(SafeExpressionError):
            safe_math_eval("__import__('os')")
        with pytest.raises(SafeExpressionError):
            safe_math_eval("open('/etc/passwd')")

    def test_blocks_imports_and_file_access(self):
        from tantra.npdna.safe_eval import safe_math_eval, SafeExpressionError
        with pytest.raises(SafeExpressionError):
            safe_math_eval("import os")
        with pytest.raises(SafeExpressionError):
            safe_math_eval("open('file.txt')")

    def test_blocks_attributes_and_subscripts(self):
        from tantra.npdna.safe_eval import safe_math_eval, SafeExpressionError
        with pytest.raises(SafeExpressionError):
            safe_math_eval("().__class__")
        with pytest.raises(SafeExpressionError):
            safe_math_eval("[1,2][0]")

    def test_safe_expression_output_basic(self):
        from tantra.npdna.safe_eval import safe_expression_output
        assert safe_expression_output("2 + 2") == "4"
        assert safe_expression_output("sqrt(9)") == "3.0"

    def test_safe_expression_output_dangerous(self):
        from tantra.npdna.safe_eval import safe_expression_output
        result = safe_expression_output("__import__('os').system('rm -rf /')")
        assert "blocked" in result.lower() or "Expression blocked" in result

    def test_invalid_syntax_graceful(self):
        from tantra.npdna.safe_eval import safe_expression_output
        result = safe_expression_output("2 +* 2")
        assert "blocked" in result.lower() or "Expression blocked" in result

    def test_large_integers(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert safe_math_eval("10 ** 3") == 1000

    def test_factorial(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert safe_math_eval("abs(-5) + 1") == 6

    def test_modulo(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert safe_math_eval("10 % 3") == 1

    def test_negation(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert safe_math_eval("-5") == -5
        assert safe_math_eval("+5") == 5

    def test_pi_and_e(self):
        from tantra.npdna.safe_eval import safe_math_eval
        import math
        assert abs(safe_math_eval("pi") - math.pi) < 1e-10
        assert abs(safe_math_eval("e") - math.e) < 1e-10

    def test_log_functions(self):
        from tantra.npdna.safe_eval import safe_math_eval
        assert abs(safe_math_eval("log(1)") - 0) < 1e-10
        assert abs(safe_math_eval("log10(100)") - 2) < 1e-10

    def test_expression_too_long(self):
        from tantra.npdna.safe_eval import safe_math_eval, SafeExpressionError
        with pytest.raises(SafeExpressionError):
            safe_math_eval("1" * 600)

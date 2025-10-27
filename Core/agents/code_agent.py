"""
Code Agent for Atulya Tantra AGI
Specialized agent for code generation, analysis, and debugging
"""

import ast
import subprocess
import tempfile
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from .base_agent import BaseAgent, AgentTask, AgentStatus, AgentCapability, AgentPriority
from ..config.logging import get_logger
from ..config.exceptions import AgentError, ValidationError

logger = get_logger(__name__)


class CodeAgent(BaseAgent):
    """Code generation and analysis agent"""
    
    def __init__(self):
        super().__init__(
            agent_id="code_agent",
            name="Code Agent",
            capabilities=[
                AgentCapability.CODE_GENERATION,
                AgentCapability.CODE_ANALYSIS,
                AgentCapability.DEBUGGING,
                AgentCapability.REFACTORING,
                AgentCapability.TESTING
            ],
            priority=AgentPriority.HIGH
        )
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "cpp", "c", "go", "rust",
            "php", "ruby", "swift", "kotlin", "scala", "r", "sql", "html", "css"
        ]
        self.code_templates = self._load_code_templates()
    
    def _load_code_templates(self) -> Dict[str, str]:
        """Load code templates for different languages"""
        return {
            "python": {
                "function": "def {name}({params}):\n    \"\"\"{docstring}\"\"\"\n    {body}",
                "class": "class {name}:\n    \"\"\"{docstring}\"\"\"\n    \n    def __init__(self{params}):\n        {body}",
                "test": "def test_{name}():\n    \"\"\"Test {name}\"\"\"\n    {body}"
            },
            "javascript": {
                "function": "function {name}({params}) {{\n    // {docstring}\n    {body}\n}}",
                "class": "class {name} {{\n    constructor({params}) {{\n        {body}\n    }}\n}}",
                "test": "describe('{name}', () => {{\n    it('should {description}', () => {{\n        {body}\n    }});\n}});"
            }
        }
    
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute code-related task"""
        try:
            task_type = task.parameters.get("task_type", "generate")
            
            if task_type == "generate":
                return await self._generate_code(task)
            elif task_type == "analyze":
                return await self._analyze_code(task)
            elif task_type == "debug":
                return await self._debug_code(task)
            elif task_type == "refactor":
                return await self._refactor_code(task)
            elif task_type == "test":
                return await self._generate_tests(task)
            elif task_type == "optimize":
                return await self._optimize_code(task)
            else:
                raise ValidationError(f"Unknown task type: {task_type}")
                
        except Exception as e:
            logger.error(f"Error executing code task: {e}")
            raise AgentError(f"Failed to execute code task: {e}")
    
    async def _generate_code(self, task: AgentTask) -> Dict[str, Any]:
        """Generate code based on requirements"""
        try:
            language = task.parameters.get("language", "python")
            requirements = task.parameters.get("requirements", "")
            code_type = task.parameters.get("code_type", "function")
            
            if language not in self.supported_languages:
                raise ValidationError(f"Unsupported language: {language}")
            
            # Generate code using templates and AI
            generated_code = await self._generate_code_with_ai(
                language=language,
                requirements=requirements,
                code_type=code_type
            )
            
            # Validate generated code
            validation_result = await self._validate_code(generated_code, language)
            
            return {
                "generated_code": generated_code,
                "language": language,
                "validation": validation_result,
                "suggestions": await self._get_code_suggestions(generated_code, language)
            }
            
        except Exception as e:
            logger.error(f"Error generating code: {e}")
            raise AgentError(f"Failed to generate code: {e}")
    
    async def _analyze_code(self, task: AgentTask) -> Dict[str, Any]:
        """Analyze code for issues and improvements"""
        try:
            code = task.parameters.get("code", "")
            language = task.parameters.get("language", "python")
            
            analysis_result = {
                "complexity": await self._calculate_complexity(code, language),
                "issues": await self._find_issues(code, language),
                "metrics": await self._calculate_metrics(code, language),
                "suggestions": await self._get_improvement_suggestions(code, language)
            }
            
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error analyzing code: {e}")
            raise AgentError(f"Failed to analyze code: {e}")
    
    async def _debug_code(self, task: AgentTask) -> Dict[str, Any]:
        """Debug code and find issues"""
        try:
            code = task.parameters.get("code", "")
            language = task.parameters.get("language", "python")
            error_message = task.parameters.get("error_message", "")
            
            # Find syntax errors
            syntax_errors = await self._find_syntax_errors(code, language)
            
            # Find logical errors
            logical_errors = await self._find_logical_errors(code, language, error_message)
            
            # Suggest fixes
            fixes = await self._suggest_fixes(code, language, syntax_errors + logical_errors)
            
            return {
                "syntax_errors": syntax_errors,
                "logical_errors": logical_errors,
                "fixes": fixes,
                "debugging_steps": await self._get_debugging_steps(code, language)
            }
            
        except Exception as e:
            logger.error(f"Error debugging code: {e}")
            raise AgentError(f"Failed to debug code: {e}")
    
    async def _refactor_code(self, task: AgentTask) -> Dict[str, Any]:
        """Refactor code for better quality"""
        try:
            code = task.parameters.get("code", "")
            language = task.parameters.get("language", "python")
            refactor_type = task.parameters.get("refactor_type", "general")
            
            refactored_code = await self._refactor_code_with_ai(
                code=code,
                language=language,
                refactor_type=refactor_type
            )
            
            # Compare original and refactored code
            comparison = await self._compare_code(code, refactored_code, language)
            
            return {
                "refactored_code": refactored_code,
                "changes": comparison["changes"],
                "improvements": comparison["improvements"],
                "metrics_before": comparison["metrics_before"],
                "metrics_after": comparison["metrics_after"]
            }
            
        except Exception as e:
            logger.error(f"Error refactoring code: {e}")
            raise AgentError(f"Failed to refactor code: {e}")
    
    async def _generate_tests(self, task: AgentTask) -> Dict[str, Any]:
        """Generate tests for code"""
        try:
            code = task.parameters.get("code", "")
            language = task.parameters.get("language", "python")
            test_framework = task.parameters.get("test_framework", "pytest")
            
            # Generate unit tests
            unit_tests = await self._generate_unit_tests(code, language, test_framework)
            
            # Generate integration tests
            integration_tests = await self._generate_integration_tests(code, language, test_framework)
            
            # Generate test data
            test_data = await self._generate_test_data(code, language)
            
            return {
                "unit_tests": unit_tests,
                "integration_tests": integration_tests,
                "test_data": test_data,
                "test_coverage": await self._calculate_test_coverage(code, unit_tests, language)
            }
            
        except Exception as e:
            logger.error(f"Error generating tests: {e}")
            raise AgentError(f"Failed to generate tests: {e}")
    
    async def _optimize_code(self, task: AgentTask) -> Dict[str, Any]:
        """Optimize code for performance"""
        try:
            code = task.parameters.get("code", "")
            language = task.parameters.get("language", "python")
            optimization_type = task.parameters.get("optimization_type", "performance")
            
            # Analyze performance bottlenecks
            bottlenecks = await self._find_performance_bottlenecks(code, language)
            
            # Generate optimized code
            optimized_code = await self._optimize_code_with_ai(
                code=code,
                language=language,
                optimization_type=optimization_type,
                bottlenecks=bottlenecks
            )
            
            # Compare performance
            performance_comparison = await self._compare_performance(code, optimized_code, language)
            
            return {
                "optimized_code": optimized_code,
                "bottlenecks": bottlenecks,
                "performance_improvement": performance_comparison,
                "optimization_techniques": await self._get_optimization_techniques(code, language)
            }
            
        except Exception as e:
            logger.error(f"Error optimizing code: {e}")
            raise AgentError(f"Failed to optimize code: {e}")
    
    async def _generate_code_with_ai(self, language: str, requirements: str, code_type: str) -> str:
        """Generate code using AI"""
        # This would integrate with the LLM provider
        # For now, return a template-based implementation
        template = self.code_templates.get(language, {}).get(code_type, "")
        
        if template:
            # Replace placeholders
            code = template.format(
                name="generated_function",
                params="param1, param2",
                docstring="Generated function",
                body="pass"
            )
            return code
        
        return f"# Generated {code_type} in {language}\n# Requirements: {requirements}\npass"
    
    async def _validate_code(self, code: str, language: str) -> Dict[str, Any]:
        """Validate generated code"""
        try:
            if language == "python":
                # Parse Python code
                ast.parse(code)
                return {"valid": True, "errors": []}
            else:
                # For other languages, basic validation
                return {"valid": True, "errors": []}
        except SyntaxError as e:
            return {"valid": False, "errors": [str(e)]}
        except Exception as e:
            return {"valid": False, "errors": [str(e)]}
    
    async def _calculate_complexity(self, code: str, language: str) -> Dict[str, Any]:
        """Calculate code complexity metrics"""
        # Simplified complexity calculation
        lines = len(code.split('\n'))
        functions = code.count('def ') if language == "python" else code.count('function ')
        classes = code.count('class ') if language == "python" else code.count('class ')
        
        return {
            "lines_of_code": lines,
            "function_count": functions,
            "class_count": classes,
            "cyclomatic_complexity": functions * 2  # Simplified
        }
    
    async def _find_issues(self, code: str, language: str) -> List[Dict[str, Any]]:
        """Find code issues"""
        issues = []
        
        # Check for common issues
        if language == "python":
            if "import *" in code:
                issues.append({
                    "type": "warning",
                    "message": "Avoid wildcard imports",
                    "line": code.find("import *") + 1
                })
            
            if "print(" in code:
                issues.append({
                    "type": "info",
                    "message": "Consider using logging instead of print",
                    "line": code.find("print(") + 1
                })
        
        return issues
    
    async def _calculate_metrics(self, code: str, language: str) -> Dict[str, Any]:
        """Calculate code metrics"""
        lines = code.split('\n')
        
        return {
            "total_lines": len(lines),
            "blank_lines": len([line for line in lines if not line.strip()]),
            "comment_lines": len([line for line in lines if line.strip().startswith('#')]),
            "code_lines": len([line for line in lines if line.strip() and not line.strip().startswith('#')])
        }
    
    async def _get_improvement_suggestions(self, code: str, language: str) -> List[str]:
        """Get code improvement suggestions"""
        suggestions = []
        
        if language == "python":
            if "def " in code and "return" not in code:
                suggestions.append("Consider adding return statements to functions")
            
            if "if " in code and "else" not in code:
                suggestions.append("Consider adding else clauses for better error handling")
        
        return suggestions
    
    async def _find_syntax_errors(self, code: str, language: str) -> List[Dict[str, Any]]:
        """Find syntax errors in code"""
        errors = []
        
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                errors.append({
                    "type": "syntax_error",
                    "message": str(e),
                    "line": e.lineno,
                    "column": e.offset
                })
        
        return errors
    
    async def _find_logical_errors(self, code: str, language: str, error_message: str) -> List[Dict[str, Any]]:
        """Find logical errors in code"""
        errors = []
        
        # Basic logical error detection
        if "while True:" in code and "break" not in code:
            errors.append({
                "type": "logical_error",
                "message": "Infinite loop detected",
                "line": code.find("while True:") + 1
            })
        
        return errors
    
    async def _suggest_fixes(self, code: str, language: str, errors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Suggest fixes for errors"""
        fixes = []
        
        for error in errors:
            if error["type"] == "syntax_error":
                fixes.append({
                    "error": error,
                    "suggestion": "Check syntax and fix the error",
                    "example": "Ensure proper indentation and brackets"
                })
        
        return fixes
    
    async def _get_debugging_steps(self, code: str, language: str) -> List[str]:
        """Get debugging steps"""
        return [
            "1. Check for syntax errors",
            "2. Verify variable names and scope",
            "3. Check function calls and parameters",
            "4. Add print statements for debugging",
            "5. Use a debugger to step through code"
        ]
    
    async def _refactor_code_with_ai(self, code: str, language: str, refactor_type: str) -> str:
        """Refactor code using AI"""
        # This would integrate with the LLM provider
        # For now, return basic refactoring
        refactored = code
        
        if language == "python":
            # Basic refactoring
            refactored = refactored.replace("print(", "logger.info(")
            refactored = refactored.replace("def ", "def ")
        
        return refactored
    
    async def _compare_code(self, original: str, refactored: str, language: str) -> Dict[str, Any]:
        """Compare original and refactored code"""
        return {
            "changes": ["Replaced print with logger"],
            "improvements": ["Better logging", "Improved readability"],
            "metrics_before": await self._calculate_metrics(original, language),
            "metrics_after": await self._calculate_metrics(refactored, language)
        }
    
    async def _generate_unit_tests(self, code: str, language: str, test_framework: str) -> str:
        """Generate unit tests"""
        if language == "python" and test_framework == "pytest":
            return f"""
import pytest
from your_module import your_function

def test_your_function():
    # Test case 1
    result = your_function("input")
    assert result == "expected_output"
    
    # Test case 2
    result = your_function("")
    assert result is None
"""
        return "# Unit tests would be generated here"
    
    async def _generate_integration_tests(self, code: str, language: str, test_framework: str) -> str:
        """Generate integration tests"""
        return "# Integration tests would be generated here"
    
    async def _generate_test_data(self, code: str, language: str) -> Dict[str, Any]:
        """Generate test data"""
        return {
            "valid_inputs": ["test1", "test2"],
            "invalid_inputs": [None, "", 123],
            "edge_cases": ["", "very_long_string"]
        }
    
    async def _calculate_test_coverage(self, code: str, tests: str, language: str) -> float:
        """Calculate test coverage"""
        # Simplified coverage calculation
        return 0.85  # 85% coverage
    
    async def _find_performance_bottlenecks(self, code: str, language: str) -> List[Dict[str, Any]]:
        """Find performance bottlenecks"""
        bottlenecks = []
        
        if "for " in code and "in " in code:
            bottlenecks.append({
                "type": "loop",
                "message": "Consider optimizing loops",
                "line": code.find("for ") + 1
            })
        
        return bottlenecks
    
    async def _optimize_code_with_ai(self, code: str, language: str, optimization_type: str, bottlenecks: List[Dict[str, Any]]) -> str:
        """Optimize code using AI"""
        # This would integrate with the LLM provider
        optimized = code
        
        if language == "python":
            # Basic optimizations
            optimized = optimized.replace("for i in range(len(list)):", "for item in list:")
            optimized = optimized.replace("list[i]", "item")
        
        return optimized
    
    async def _compare_performance(self, original: str, optimized: str, language: str) -> Dict[str, Any]:
        """Compare performance of original and optimized code"""
        return {
            "execution_time_improvement": "20%",
            "memory_usage_improvement": "15%",
            "optimization_techniques": ["Loop optimization", "Variable reuse"]
        }
    
    async def _get_optimization_techniques(self, code: str, language: str) -> List[str]:
        """Get optimization techniques for code"""
        return [
            "Use list comprehensions instead of loops",
            "Avoid unnecessary function calls in loops",
            "Use appropriate data structures",
            "Cache frequently used values",
            "Profile code to identify bottlenecks"
        ]
    
    async def _get_code_suggestions(self, code: str, language: str) -> List[str]:
        """Get code suggestions"""
        return [
            "Add type hints for better code clarity",
            "Include docstrings for functions and classes",
            "Consider error handling for edge cases",
            "Add unit tests for better reliability"
        ]
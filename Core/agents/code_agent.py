"""
Code Agent for Atulya Tantra AGI
Specialized agent for code generation, analysis, and execution
"""

import ast
import subprocess
import tempfile
import os
from typing import Dict, List, Any, Optional
from datetime import datetime

from .base_agent import BaseAgent, AgentTask, AgentCapability, AgentStatus
from ..config.logging import get_logger
from ..config.exceptions import AgentError
from ..brain import generate_response, get_llm_router

logger = get_logger(__name__)


class CodeAgent(BaseAgent):
    """Agent specialized in code generation, analysis, and execution"""
    
    def __init__(self):
        super().__init__(
            name="CodeAgent",
            description="Specialized agent for code generation, analysis, debugging, and execution",
            capabilities=[
                AgentCapability.CODE_EXECUTION,
                AgentCapability.TEXT_GENERATION,
                AgentCapability.FILE_PROCESSING
            ],
            max_concurrent_tasks=3,
            timeout_seconds=600  # Longer timeout for code execution
        )
        
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "cpp", "c", "go", 
            "rust", "php", "ruby", "swift", "kotlin", "scala", "r", "sql"
        ]
        self.safe_execution = True  # Only execute safe code by default
    
    async def can_handle_task(self, task: AgentTask) -> bool:
        """Check if this agent can handle the given task"""
        task_type = task.task_type or ""
        description = (task.description or "").lower()
        
        # Check for code-related keywords
        code_keywords = [
            "code", "programming", "debug", "fix", "implement", "function",
            "class", "algorithm", "syntax", "error", "bug", "refactor",
            "optimize", "test", "unit test", "integration test", "compile",
            "execute", "run", "script", "api", "endpoint", "database query"
        ]
        
        return (
            task_type in ["code_generation", "code_analysis", "code_execution", "debugging", "testing"] or
            any(keyword in description for keyword in code_keywords)
        )
    
    async def get_task_estimate(self, task: AgentTask) -> Dict[str, Any]:
        """Estimate task execution time and resource requirements"""
        task_type = task.task_type or ""
        description = task.description or ""
        
        # Base estimates
        if task_type == "code_generation":
            estimated_time = 30  # seconds
            complexity = "medium"
        elif task_type == "code_analysis":
            estimated_time = 20
            complexity = "low"
        elif task_type == "code_execution":
            estimated_time = 60
            complexity = "high"
        elif task_type == "debugging":
            estimated_time = 120
            complexity = "high"
        else:
            estimated_time = 45
            complexity = "medium"
        
        # Adjust based on description length/complexity
        if len(description) > 500:
            estimated_time *= 1.5
            complexity = "high"
        elif len(description) < 100:
            estimated_time *= 0.7
            complexity = "low"
        
        return {
            "estimated_time_seconds": estimated_time,
            "complexity": complexity,
            "resource_requirements": {
                "memory_mb": 100,
                "cpu_usage": "medium",
                "disk_space_mb": 10
            }
        }
    
    async def execute_task(self, task: AgentTask) -> Dict[str, Any]:
        """Execute a code-related task"""
        try:
            task_type = task.task_type or "code_generation"
            input_data = task.input_data or {}
            
            if task_type == "code_generation":
                return await self._generate_code(task, input_data)
            elif task_type == "code_analysis":
                return await self._analyze_code(task, input_data)
            elif task_type == "code_execution":
                return await self._execute_code(task, input_data)
            elif task_type == "debugging":
                return await self._debug_code(task, input_data)
            elif task_type == "testing":
                return await self._create_tests(task, input_data)
            else:
                return await self._general_code_task(task, input_data)
                
        except Exception as e:
            logger.error(f"CodeAgent execution error: {e}")
            raise AgentError(f"Code execution failed: {e}")
    
    async def _generate_code(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate code based on requirements"""
        requirements = input_data.get("requirements", task.description)
        language = input_data.get("language", "python")
        style = input_data.get("style", "clean and readable")
        
        # Create a detailed prompt for code generation
        prompt = f"""
You are an expert {language} programmer. Generate high-quality, production-ready code based on the following requirements:

Requirements: {requirements}
Programming Language: {language}
Code Style: {style}

Please provide:
1. Complete, working code
2. Clear comments explaining the logic
3. Error handling where appropriate
4. Type hints (if applicable to the language)
5. Brief explanation of the approach

Code:
"""
        
        response = await generate_response(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.3,  # Lower temperature for more consistent code
            preferred_provider="openai"  # OpenAI is generally better for code generation
        )
        
        # Extract code from response
        code = self._extract_code_from_response(response, language)
        
        # Validate the generated code
        validation_result = await self._validate_code(code, language)
        
        return {
            "generated_code": code,
            "language": language,
            "validation": validation_result,
            "explanation": response,
            "metadata": {
                "task_type": "code_generation",
                "language": language,
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _analyze_code(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze provided code for issues, patterns, and improvements"""
        code = input_data.get("code", "")
        language = input_data.get("language", "python")
        
        if not code:
            raise AgentError("No code provided for analysis")
        
        prompt = f"""
Analyze the following {language} code and provide a comprehensive analysis:

Code:
```{language}
{code}
```

Please analyze:
1. Code quality and style
2. Potential bugs or issues
3. Performance considerations
4. Security vulnerabilities
5. Best practices adherence
6. Suggestions for improvement
7. Complexity assessment

Provide detailed feedback with specific examples and recommendations.
"""
        
        analysis = await generate_response(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.2,
            preferred_provider="openai"
        )
        
        # Perform automated analysis
        automated_analysis = await self._automated_code_analysis(code, language)
        
        return {
            "analysis": analysis,
            "automated_analysis": automated_analysis,
            "language": language,
            "code_length": len(code),
            "metadata": {
                "task_type": "code_analysis",
                "analyzed_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _execute_code(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute code safely and return results"""
        code = input_data.get("code", "")
        language = input_data.get("language", "python")
        
        if not code:
            raise AgentError("No code provided for execution")
        
        if not self.safe_execution:
            raise AgentError("Code execution is disabled for security reasons")
        
        # Check if language is supported
        if language not in self.supported_languages:
            raise AgentError(f"Language {language} is not supported for execution")
        
        # Execute code based on language
        if language == "python":
            return await self._execute_python_code(code)
        elif language in ["javascript", "typescript"]:
            return await self._execute_javascript_code(code)
        else:
            # For other languages, provide compilation/execution guidance
            return await self._provide_execution_guidance(code, language)
    
    async def _debug_code(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Debug code issues and provide fixes"""
        code = input_data.get("code", "")
        error_message = input_data.get("error", "")
        language = input_data.get("language", "python")
        
        prompt = f"""
Debug the following {language} code that is producing an error:

Code:
```{language}
{code}
```

Error Message: {error_message}

Please:
1. Identify the root cause of the error
2. Explain why the error occurs
3. Provide a corrected version of the code
4. Suggest best practices to prevent similar issues
5. If the error is unclear, suggest debugging steps

Provide a clear, step-by-step debugging approach.
"""
        
        debug_analysis = await generate_response(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.1,  # Very low temperature for debugging
            preferred_provider="openai"
        )
        
        # Try to automatically fix common issues
        fixed_code = await self._auto_fix_code(code, language, error_message)
        
        return {
            "debug_analysis": debug_analysis,
            "original_code": code,
            "fixed_code": fixed_code,
            "error_message": error_message,
            "language": language,
            "metadata": {
                "task_type": "debugging",
                "debugged_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _create_tests(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate unit tests for provided code"""
        code = input_data.get("code", "")
        language = input_data.get("language", "python")
        test_framework = input_data.get("test_framework", "pytest" if language == "python" else "jest")
        
        prompt = f"""
Generate comprehensive unit tests for the following {language} code using {test_framework}:

Code:
```{language}
{code}
```

Please provide:
1. Test cases covering all functions/methods
2. Edge cases and boundary conditions
3. Error handling tests
4. Mock objects where appropriate
5. Clear test descriptions
6. Expected outputs

Make the tests thorough and maintainable.
"""
        
        tests = await generate_response(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.3,
            preferred_provider="openai"
        )
        
        return {
            "generated_tests": tests,
            "test_framework": test_framework,
            "language": language,
            "original_code": code,
            "metadata": {
                "task_type": "testing",
                "generated_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _general_code_task(self, task: AgentTask, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle general code-related tasks"""
        description = task.description or ""
        
        prompt = f"""
You are an expert software engineer. Help with the following coding task:

Task: {description}

Please provide:
1. A clear solution approach
2. Implementation details
3. Code examples if applicable
4. Best practices and considerations
5. Potential challenges and solutions

Be thorough and professional in your response.
"""
        
        response = await generate_response(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.4,
            preferred_provider="openai"
        )
        
        return {
            "solution": response,
            "task_description": description,
            "metadata": {
                "task_type": "general_code_task",
                "completed_at": datetime.utcnow().isoformat()
            }
        }
    
    def _extract_code_from_response(self, response: str, language: str) -> str:
        """Extract code blocks from LLM response"""
        import re
        
        # Look for code blocks
        code_pattern = rf"```{language}\n(.*?)\n```"
        matches = re.findall(code_pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        
        # Look for generic code blocks
        generic_pattern = r"```\n(.*?)\n```"
        matches = re.findall(generic_pattern, response, re.DOTALL)
        
        if matches:
            return matches[0].strip()
        
        # If no code blocks found, return the response as-is
        return response.strip()
    
    async def _validate_code(self, code: str, language: str) -> Dict[str, Any]:
        """Validate generated code"""
        validation_result = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as e:
                validation_result["is_valid"] = False
                validation_result["errors"].append(f"Syntax error: {e}")
        
        # Check for common issues
        if "import os" in code and "os.system" in code:
            validation_result["warnings"].append("Code contains potentially unsafe os.system calls")
        
        if "eval(" in code or "exec(" in code:
            validation_result["warnings"].append("Code contains eval/exec which can be dangerous")
        
        return validation_result
    
    async def _execute_python_code(self, code: str) -> Dict[str, Any]:
        """Execute Python code safely"""
        try:
            # Validate code for dangerous operations
            if not self._is_code_safe(code):
                return {
                    "stdout": "",
                    "stderr": "Code contains potentially dangerous operations and cannot be executed",
                    "return_code": -1,
                    "execution_time": "blocked",
                    "metadata": {
                        "language": "python",
                        "executed_at": datetime.utcnow().isoformat(),
                        "safety_check": "failed"
                    }
                }
            
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Execute the code in a restricted environment
            result = subprocess.run(
                ['python', '-c', f'exec(open("{temp_file}").read())'],
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=tempfile.gettempdir()  # Execute in temp directory
            )
            
            # Clean up
            try:
                os.unlink(temp_file)
            except OSError:
                pass  # File might already be deleted
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "execution_time": "N/A",  # Could be measured if needed
                "metadata": {
                    "language": "python",
                    "executed_at": datetime.utcnow().isoformat()
                }
            }
            
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "Code execution timed out",
                "return_code": -1,
                "execution_time": "timeout",
                "metadata": {
                    "language": "python",
                    "executed_at": datetime.utcnow().isoformat()
                }
            }
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {e}",
                "return_code": -1,
                "execution_time": "error",
                "metadata": {
                    "language": "python",
                    "executed_at": datetime.utcnow().isoformat()
                }
            }
    
    async def _execute_javascript_code(self, code: str) -> Dict[str, Any]:
        """Execute JavaScript code using Node.js"""
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                f.write(code)
                temp_file = f.name
            
            # Execute the code
            result = subprocess.run(
                ['node', temp_file],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Clean up
            os.unlink(temp_file)
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "execution_time": "N/A",
                "metadata": {
                    "language": "javascript",
                    "executed_at": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            return {
                "stdout": "",
                "stderr": f"Execution error: {e}",
                "return_code": -1,
                "execution_time": "error",
                "metadata": {
                    "language": "javascript",
                    "executed_at": datetime.utcnow().isoformat()
                }
            }
    
    async def _provide_execution_guidance(self, code: str, language: str) -> Dict[str, Any]:
        """Provide guidance for executing code in unsupported languages"""
        guidance = f"""
To execute this {language} code:

1. Save the code to a file with appropriate extension (.{language})
2. Install the necessary compiler/interpreter for {language}
3. Compile the code (if needed): [compilation command]
4. Execute the code: [execution command]

Note: Automatic execution is not supported for {language} for security reasons.
"""
        
        return {
            "guidance": guidance,
            "code": code,
            "language": language,
            "execution_supported": False,
            "metadata": {
                "task_type": "execution_guidance",
                "provided_at": datetime.utcnow().isoformat()
            }
        }
    
    async def _automated_code_analysis(self, code: str, language: str) -> Dict[str, Any]:
        """Perform automated code analysis"""
        analysis = {
            "lines_of_code": len(code.splitlines()),
            "character_count": len(code),
            "complexity_indicators": [],
            "potential_issues": []
        }
        
        # Simple complexity analysis
        if language == "python":
            # Count nested levels
            max_indent = 0
            for line in code.splitlines():
                if line.strip():
                    indent = len(line) - len(line.lstrip())
                    max_indent = max(max_indent, indent)
            
            if max_indent > 12:  # More than 3 levels of nesting
                analysis["complexity_indicators"].append("High nesting level")
            
            # Check for long functions
            lines = code.splitlines()
            function_lines = 0
            in_function = False
            
            for line in lines:
                if line.strip().startswith('def '):
                    if in_function and function_lines > 50:
                        analysis["potential_issues"].append("Long function detected")
                    function_lines = 0
                    in_function = True
                elif in_function:
                    function_lines += 1
        
        return analysis
    
    async def _auto_fix_code(self, code: str, language: str, error_message: str) -> str:
        """Attempt to automatically fix common code issues"""
        if language == "python":
            # Common Python fixes
            if "IndentationError" in error_message:
                # Try to fix indentation
                lines = code.splitlines()
                fixed_lines = []
                for line in lines:
                    if line.strip():
                        # Convert tabs to spaces
                        fixed_line = line.expandtabs(4)
                        fixed_lines.append(fixed_line)
                    else:
                        fixed_lines.append(line)
                return '\n'.join(fixed_lines)
            
            elif "SyntaxError" in error_message and "unexpected EOF" in error_message:
                # Try to add missing closing brackets/parentheses
                open_parens = code.count('(')
                close_parens = code.count(')')
                if open_parens > close_parens:
                    code += ')' * (open_parens - close_parens)
                
                open_brackets = code.count('[')
                close_brackets = code.count(']')
                if open_brackets > close_brackets:
                    code += ']' * (open_brackets - close_brackets)
                
                open_braces = code.count('{')
                close_braces = code.count('}')
                if open_braces > close_braces:
                    code += '}' * (open_braces - close_braces)
        
        return code
    
    def _is_code_safe(self, code: str) -> bool:
        """Check if code is safe to execute"""
        dangerous_patterns = [
            'import os', 'import subprocess', 'import sys', 'import shutil',
            'import socket', 'import urllib', 'import requests', 'import http',
            '__import__', 'eval(', 'exec(', 'compile(',
            'open(', 'file(', 'input(', 'raw_input(',
            'os.system', 'os.popen', 'subprocess.call', 'subprocess.run',
            'subprocess.Popen', 'execfile(', 'reload(',
            'exit(', 'quit(', 'sys.exit('
        ]
        
        code_lower = code.lower()
        for pattern in dangerous_patterns:
            if pattern in code_lower:
                return False
        
        # Check for file system operations
        if any(op in code_lower for op in ['rm ', 'del ', 'remove', 'unlink', 'rmdir']):
            return False
        
        # Check for network operations
        if any(op in code_lower for op in ['socket', 'urllib', 'requests', 'http']):
            return False
        
        return True


# Export the agent class
__all__ = ["CodeAgent"]

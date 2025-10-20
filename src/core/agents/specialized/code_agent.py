"""
Atulya Tantra - Code Agent
Version: 2.5.0
Specialized agent for code generation, analysis, and debugging
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import re
import ast
import uuid
from src.core.agents.specialized.base_agent import BaseAgent, AgentCapability, AgentTask, AgentResult, AgentStatus, TaskComplexity

logger = logging.getLogger(__name__)


@dataclass
class CodeAnalysis:
    """Code analysis result"""
    language: str
    complexity_score: float
    issues: List[Dict[str, Any]]
    suggestions: List[str]
    metrics: Dict[str, Any]


@dataclass
class CodeGeneration:
    """Code generation result"""
    language: str
    code: str
    explanation: str
    test_cases: List[str]
    documentation: str


class CodeAgent:
    """Specialized agent for code-related tasks"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.agent_id = "code_agent"
        self.name = "Code Agent"
        self.status = AgentStatus.IDLE
        
        # Supported languages
        self.supported_languages = [
            "python", "javascript", "typescript", "java", "cpp", "csharp",
            "go", "rust", "php", "ruby", "swift", "kotlin", "sql"
        ]
        
        # Initialize capabilities
        self.capabilities = [
            AgentCapability(
                name="code_generation",
                description="Generate code based on specifications",
                supported_languages=self.supported_languages,
                supported_formats=["text", "markdown"],
                max_complexity=TaskComplexity.VERY_COMPLEX,
                estimated_time=30
            ),
            AgentCapability(
                name="code_analysis",
                description="Analyze code for issues and improvements",
                supported_languages=self.supported_languages,
                supported_formats=["text", "json"],
                max_complexity=TaskComplexity.COMPLEX,
                estimated_time=15
            ),
            AgentCapability(
                name="debugging",
                description="Help debug code issues",
                supported_languages=self.supported_languages,
                supported_formats=["text", "markdown"],
                max_complexity=TaskComplexity.COMPLEX,
                estimated_time=20
            ),
            AgentCapability(
                name="refactoring",
                description="Suggest code improvements and refactoring",
                supported_languages=self.supported_languages,
                supported_formats=["text", "markdown"],
                max_complexity=TaskComplexity.MODERATE,
                estimated_time=25
            )
        ]
        
        logger.info("CodeAgent initialized")
    
    async def can_handle(self, task_type: str, requirements: Dict[str, Any]) -> bool:
        """Check if agent can handle a specific task"""
        
        # Check if task type is supported
        supported_types = ["code_generation", "code_analysis", "debugging", "refactoring"]
        if task_type not in supported_types:
            return False
        
        # Check language support
        if "language" in requirements:
            language = requirements["language"].lower()
            if language not in self.supported_languages:
                return False
        
        # Check complexity
        if "complexity" in requirements:
            complexity = requirements["complexity"]
            for capability in self.capabilities:
                if capability.name == task_type:
                    if complexity == "very_complex" and capability.max_complexity != TaskComplexity.VERY_COMPLEX:
                        return False
        
        return True
    
    async def process_task(self, task: AgentTask) -> AgentResult:
        """Process a code-related task"""
        
        self.status = AgentStatus.PROCESSING
        start_time = datetime.now()
        
        try:
            if task.task_type == "code_generation":
                result = await self._generate_code(task.input_data, task.requirements)
            elif task.task_type == "code_analysis":
                result = await self._analyze_code(task.input_data, task.requirements)
            elif task.task_type == "debugging":
                result = await self._debug_code(task.input_data, task.requirements)
            elif task.task_type == "refactoring":
                result = await self._refactor_code(task.input_data, task.requirements)
            else:
                raise ValueError(f"Unknown task type: {task.task_type}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=True,
                result=result,
                metadata={
                    "task_type": task.task_type,
                    "language": task.requirements.get("language", "unknown"),
                    "complexity": task.requirements.get("complexity", "moderate")
                },
                execution_time=execution_time,
                confidence=0.85,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Code agent task failed: {e}")
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=False,
                result=None,
                metadata={"error": str(e)},
                execution_time=execution_time,
                confidence=0.0,
                timestamp=datetime.now()
            )
        finally:
            self.status = AgentStatus.IDLE
    
    async def _generate_code(self, input_data: Dict[str, Any], requirements: Dict[str, Any]) -> CodeGeneration:
        """Generate code based on specifications"""
        
        specification = input_data.get("specification", "")
        language = requirements.get("language", "python")
        
        # Simple code generation logic
        # In production, this would use AI models or templates
        
        if "function" in specification.lower():
            code = self._generate_function(language, specification)
        elif "class" in specification.lower():
            code = self._generate_class(language, specification)
        elif "api" in specification.lower():
            code = self._generate_api(language, specification)
        else:
            code = self._generate_generic(language, specification)
        
        return CodeGeneration(
            language=language,
            code=code,
            explanation=f"Generated {language} code based on specification",
            test_cases=self._generate_test_cases(language, code),
            documentation=self._generate_documentation(language, code)
        )
    
    async def _analyze_code(self, input_data: Dict[str, Any], requirements: Dict[str, Any]) -> CodeAnalysis:
        """Analyze code for issues and improvements"""
        
        code = input_data.get("code", "")
        language = requirements.get("language", "python")
        
        issues = []
        suggestions = []
        
        # Basic code analysis
        if language == "python":
            issues.extend(self._analyze_python_code(code))
        elif language == "javascript":
            issues.extend(self._analyze_javascript_code(code))
        
        # Generate suggestions based on issues
        for issue in issues:
            if issue["type"] == "complexity":
                suggestions.append("Consider breaking down complex functions into smaller ones")
            elif issue["type"] == "naming":
                suggestions.append("Use more descriptive variable and function names")
            elif issue["type"] == "performance":
                suggestions.append("Consider optimizing for better performance")
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity(code, language)
        
        return CodeAnalysis(
            language=language,
            complexity_score=complexity_score,
            issues=issues,
            suggestions=suggestions,
            metrics={
                "lines_of_code": len(code.split('\n')),
                "functions": len(re.findall(r'def\s+\w+', code)),
                "classes": len(re.findall(r'class\s+\w+', code)),
                "complexity_score": complexity_score
            }
        )
    
    async def _debug_code(self, input_data: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Help debug code issues"""
        
        code = input_data.get("code", "")
        error_message = input_data.get("error", "")
        language = requirements.get("language", "python")
        
        # Analyze error and provide debugging help
        debug_info = {
            "error_analysis": self._analyze_error(error_message, language),
            "potential_fixes": self._suggest_fixes(code, error_message, language),
            "debugging_steps": self._generate_debugging_steps(code, error_message, language),
            "prevention_tips": self._generate_prevention_tips(error_message, language)
        }
        
        return debug_info
    
    async def _refactor_code(self, input_data: Dict[str, Any], requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Suggest code refactoring improvements"""
        
        code = input_data.get("code", "")
        language = requirements.get("language", "python")
        
        # Analyze code for refactoring opportunities
        refactoring_suggestions = {
            "extract_methods": self._suggest_method_extraction(code, language),
            "rename_variables": self._suggest_variable_renaming(code, language),
            "simplify_conditions": self._suggest_condition_simplification(code, language),
            "remove_duplication": self._suggest_deduplication(code, language),
            "improve_structure": self._suggest_structure_improvements(code, language)
        }
        
        return refactoring_suggestions
    
    def _generate_function(self, language: str, specification: str) -> str:
        """Generate a function based on specification"""
        
        if language == "python":
            return f'''def {self._extract_function_name(specification)}():
    """
    {specification}
    """
    # TODO: Implement function logic
    pass'''
        
        elif language == "javascript":
            return f'''function {self._extract_function_name(specification)}() {{
    // {specification}
    // TODO: Implement function logic
}}'''
        
        else:
            return f"// {specification}\n// TODO: Implement in {language}"
    
    def _generate_class(self, language: str, specification: str) -> str:
        """Generate a class based on specification"""
        
        if language == "python":
            return f'''class {self._extract_class_name(specification)}:
    """
    {specification}
    """
    
    def __init__(self):
        # TODO: Initialize class attributes
        pass'''
        
        elif language == "javascript":
            return f'''class {self._extract_class_name(specification)} {{
    constructor() {{
        // TODO: Initialize class attributes
    }}
}}'''
        
        else:
            return f"// {specification}\n// TODO: Implement class in {language}"
    
    def _generate_api(self, language: str, specification: str) -> str:
        """Generate API code based on specification"""
        
        if language == "python":
            return f'''from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {{"message": "{specification}"}}

@app.get("/health")
async def health():
    return {{"status": "healthy"}}'''
        
        elif language == "javascript":
            return f'''const express = require('express');
const app = express();

app.get('/', (req, res) => {{
    res.json({{ message: '{specification}' }});
}});

app.get('/health', (req, res) => {{
    res.json({{ status: 'healthy' }});
}});'''
        
        else:
            return f"// {specification}\n// TODO: Implement API in {language}"
    
    def _generate_generic(self, language: str, specification: str) -> str:
        """Generate generic code based on specification"""
        
        return f'''// {specification}
// Generated code for {language}

// TODO: Implement based on requirements'''
    
    def _analyze_python_code(self, code: str) -> List[Dict[str, Any]]:
        """Analyze Python code for issues"""
        
        issues = []
        
        # Check for long functions
        lines = code.split('\n')
        if len(lines) > 50:
            issues.append({
                "type": "complexity",
                "severity": "warning",
                "message": "Function is too long (>50 lines)",
                "line": 1
            })
        
        # Check for complex conditions
        if 'and' in code and 'or' in code:
            issues.append({
                "type": "complexity",
                "severity": "info",
                "message": "Complex boolean logic detected",
                "line": 1
            })
        
        # Check for potential performance issues
        if 'for' in code and 'for' in code[code.find('for') + 1:]:
            issues.append({
                "type": "performance",
                "severity": "warning",
                "message": "Nested loops detected",
                "line": 1
            })
        
        return issues
    
    def _analyze_javascript_code(self, code: str) -> List[Dict[str, Any]]:
        """Analyze JavaScript code for issues"""
        
        issues = []
        
        # Check for var usage
        if 'var ' in code:
            issues.append({
                "type": "best_practice",
                "severity": "warning",
                "message": "Consider using 'let' or 'const' instead of 'var'",
                "line": 1
            })
        
        # Check for == vs ===
        if ' == ' in code:
            issues.append({
                "type": "best_practice",
                "severity": "warning",
                "message": "Consider using strict equality (===) instead of loose equality (==)",
                "line": 1
            })
        
        return issues
    
    def _calculate_complexity(self, code: str, language: str) -> float:
        """Calculate code complexity score"""
        
        # Simple complexity calculation
        lines = len(code.split('\n'))
        functions = len(re.findall(r'def\s+\w+|function\s+\w+', code))
        classes = len(re.findall(r'class\s+\w+', code))
        
        # Basic complexity formula
        complexity = (lines * 0.1) + (functions * 2) + (classes * 3)
        
        return min(10.0, complexity)
    
    def _analyze_error(self, error_message: str, language: str) -> Dict[str, Any]:
        """Analyze error message"""
        
        return {
            "error_type": "Unknown",
            "description": error_message,
            "common_causes": [
                "Syntax error",
                "Runtime error",
                "Logic error"
            ],
            "severity": "error"
        }
    
    def _suggest_fixes(self, code: str, error_message: str, language: str) -> List[str]:
        """Suggest potential fixes for the error"""
        
        return [
            "Check syntax and indentation",
            "Verify variable names and scope",
            "Add error handling",
            "Check data types and conversions"
        ]
    
    def _generate_debugging_steps(self, code: str, error_message: str, language: str) -> List[str]:
        """Generate debugging steps"""
        
        return [
            "Add print/log statements to trace execution",
            "Use debugger to step through code",
            "Check input values and types",
            "Verify function parameters",
            "Test with simplified data"
        ]
    
    def _generate_prevention_tips(self, error_message: str, language: str) -> List[str]:
        """Generate tips to prevent similar errors"""
        
        return [
            "Use type hints and validation",
            "Write unit tests",
            "Follow coding standards",
            "Use linting tools",
            "Code review practices"
        ]
    
    def _suggest_method_extraction(self, code: str, language: str) -> List[str]:
        """Suggest method extraction opportunities"""
        
        return [
            "Extract complex logic into separate methods",
            "Create utility functions for common operations",
            "Break down large functions"
        ]
    
    def _suggest_variable_renaming(self, code: str, language: str) -> List[str]:
        """Suggest variable renaming improvements"""
        
        return [
            "Use descriptive variable names",
            "Avoid single-letter variable names",
            "Follow naming conventions"
        ]
    
    def _suggest_condition_simplification(self, code: str, language: str) -> List[str]:
        """Suggest condition simplification"""
        
        return [
            "Simplify complex boolean expressions",
            "Use early returns to reduce nesting",
            "Extract complex conditions into variables"
        ]
    
    def _suggest_deduplication(self, code: str, language: str) -> List[str]:
        """Suggest code deduplication"""
        
        return [
            "Extract common code into functions",
            "Use loops instead of repeated code",
            "Create reusable utility functions"
        ]
    
    def _suggest_structure_improvements(self, code: str, language: str) -> List[str]:
        """Suggest structural improvements"""
        
        return [
            "Organize code into logical sections",
            "Group related functionality",
            "Use appropriate design patterns"
        ]
    
    def _extract_function_name(self, specification: str) -> str:
        """Extract function name from specification"""
        
        # Simple extraction logic
        words = specification.split()
        if words:
            return words[0].lower()
        return "generated_function"
    
    def _extract_class_name(self, specification: str) -> str:
        """Extract class name from specification"""
        
        # Simple extraction logic
        words = specification.split()
        if words:
            return words[0].title()
        return "GeneratedClass"
    
    def _generate_test_cases(self, language: str, code: str) -> List[str]:
        """Generate test cases for the code"""
        
        return [
            "Test with normal input",
            "Test with edge cases",
            "Test with invalid input",
            "Test error conditions"
        ]
    
    def _generate_documentation(self, language: str, code: str) -> str:
        """Generate documentation for the code"""
        
        return f"""# Generated Code Documentation

## Overview
This code was generated based on the provided specification.

## Language
{language}

## Usage
```{language}
{code}
```

## Notes
- Review and test the generated code before use
- Add appropriate error handling
- Consider performance implications
"""
    
    async def get_capabilities(self) -> List[AgentCapability]:
        """Get detailed capabilities"""
        return self.capabilities
    
    async def health_check(self) -> Dict[str, Any]:
        """Check agent health"""
        return {
            "code_agent": True,
            "status": self.status.value,
            "supported_languages": self.supported_languages,
            "capabilities": len(self.capabilities)
        }

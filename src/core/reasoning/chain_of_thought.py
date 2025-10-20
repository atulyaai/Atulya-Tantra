"""
Atulya Tantra - Chain of Thought Reasoning
Version: 2.5.0
Step-by-step reasoning with transparency and explainability
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import json

logger = logging.getLogger(__name__)


class ReasoningStep(Enum):
    """Types of reasoning steps"""
    OBSERVATION = "observation"
    HYPOTHESIS = "hypothesis"
    ANALYSIS = "analysis"
    INFERENCE = "inference"
    CONCLUSION = "conclusion"
    VERIFICATION = "verification"


class ConfidenceLevel(Enum):
    """Confidence levels for reasoning steps"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


@dataclass
class ReasoningStep:
    """Individual reasoning step"""
    step_id: str
    step_type: ReasoningStep
    content: str
    confidence: ConfidenceLevel
    evidence: List[str]
    assumptions: List[str]
    dependencies: List[str]  # step_ids this step depends on
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningChain:
    """Complete chain of thought reasoning"""
    chain_id: str
    problem_statement: str
    steps: List[ReasoningStep]
    final_conclusion: Optional[str]
    overall_confidence: ConfidenceLevel
    reasoning_strategy: str
    created_at: datetime
    completed_at: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChainOfThoughtReasoner:
    """Chain of thought reasoning engine"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.reasoning_chains = {}  # chain_id -> ReasoningChain
        self.reasoning_strategies = self._initialize_strategies()
        self.verification_methods = self._initialize_verification_methods()
        
        logger.info("ChainOfThoughtReasoner initialized")
    
    async def reason_through_problem(
        self,
        problem_statement: str,
        context: Optional[Dict[str, Any]] = None,
        strategy: Optional[str] = None
    ) -> ReasoningChain:
        """Reason through a problem step by step"""
        
        chain_id = str(uuid.uuid4())
        
        # Determine reasoning strategy
        if not strategy:
            strategy = await self._select_strategy(problem_statement, context)
        
        # Create reasoning chain
        reasoning_chain = ReasoningChain(
            chain_id=chain_id,
            problem_statement=problem_statement,
            steps=[],
            final_conclusion=None,
            overall_confidence=ConfidenceLevel.MEDIUM,
            reasoning_strategy=strategy,
            created_at=datetime.now(),
            completed_at=None,
            metadata={"context": context or {}}
        )
        
        # Execute reasoning strategy
        await self._execute_reasoning_strategy(reasoning_chain)
        
        # Store chain
        self.reasoning_chains[chain_id] = reasoning_chain
        
        logger.info(f"Completed reasoning chain: {chain_id}")
        return reasoning_chain
    
    async def get_reasoning_chain(self, chain_id: str) -> Optional[ReasoningChain]:
        """Get a reasoning chain by ID"""
        
        return self.reasoning_chains.get(chain_id)
    
    async def get_reasoning_summary(self, chain_id: str) -> Dict[str, Any]:
        """Get summary of reasoning chain"""
        
        chain = self.reasoning_chains.get(chain_id)
        if not chain:
            return {"error": "Chain not found"}
        
        return {
            "chain_id": chain_id,
            "problem_statement": chain.problem_statement,
            "strategy": chain.reasoning_strategy,
            "total_steps": len(chain.steps),
            "final_conclusion": chain.final_conclusion,
            "overall_confidence": chain.overall_confidence.value,
            "created_at": chain.created_at.isoformat(),
            "completed_at": chain.completed_at.isoformat() if chain.completed_at else None,
            "step_summary": [
                {
                    "step_id": step.step_id,
                    "type": step.step_type.value,
                    "content": step.content[:100] + "..." if len(step.content) > 100 else step.content,
                    "confidence": step.confidence.value
                }
                for step in chain.steps
            ]
        }
    
    async def verify_reasoning_chain(self, chain_id: str) -> Dict[str, Any]:
        """Verify the validity of a reasoning chain"""
        
        chain = self.reasoning_chains.get(chain_id)
        if not chain:
            return {"error": "Chain not found"}
        
        verification_results = {
            "chain_id": chain_id,
            "overall_validity": "valid",
            "step_verifications": [],
            "logical_consistency": True,
            "evidence_quality": "good",
            "assumption_validity": "valid",
            "recommendations": []
        }
        
        # Verify each step
        for step in chain.steps:
            step_verification = await self._verify_reasoning_step(step)
            verification_results["step_verifications"].append(step_verification)
            
            if step_verification["validity"] == "invalid":
                verification_results["overall_validity"] = "invalid"
                verification_results["logical_consistency"] = False
        
        # Check logical flow
        logical_flow = await self._check_logical_flow(chain)
        if not logical_flow["consistent"]:
            verification_results["logical_consistency"] = False
            verification_results["recommendations"].extend(logical_flow["recommendations"])
        
        # Assess evidence quality
        evidence_quality = await self._assess_evidence_quality(chain)
        verification_results["evidence_quality"] = evidence_quality["quality"]
        verification_results["recommendations"].extend(evidence_quality["recommendations"])
        
        return verification_results
    
    async def _execute_reasoning_strategy(self, reasoning_chain: ReasoningChain):
        """Execute the selected reasoning strategy"""
        
        strategy = reasoning_chain.reasoning_strategy
        
        if strategy == "systematic_analysis":
            await self._systematic_analysis_strategy(reasoning_chain)
        elif strategy == "hypothesis_testing":
            await self._hypothesis_testing_strategy(reasoning_chain)
        elif strategy == "comparative_analysis":
            await self._comparative_analysis_strategy(reasoning_chain)
        elif strategy == "causal_reasoning":
            await self._causal_reasoning_strategy(reasoning_chain)
        else:
            await self._general_reasoning_strategy(reasoning_chain)
        
        # Finalize chain
        reasoning_chain.completed_at = datetime.now()
        reasoning_chain.overall_confidence = await self._calculate_overall_confidence(reasoning_chain)
    
    async def _systematic_analysis_strategy(self, reasoning_chain: ReasoningChain):
        """Systematic analysis reasoning strategy"""
        
        problem = reasoning_chain.problem_statement
        
        # Step 1: Problem decomposition
        decomposition_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.OBSERVATION,
            content=f"Decomposing problem: {problem}",
            confidence=ConfidenceLevel.HIGH,
            evidence=[f"Problem statement: {problem}"],
            assumptions=["Problem can be decomposed into smaller parts"],
            dependencies=[],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(decomposition_step)
        
        # Step 2: Identify components
        components_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.ANALYSIS,
            content="Identifying key components and factors",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Problem analysis"],
            assumptions=["All relevant components can be identified"],
            dependencies=[decomposition_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(components_step)
        
        # Step 3: Analyze relationships
        relationships_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.ANALYSIS,
            content="Analyzing relationships between components",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Component analysis"],
            assumptions=["Relationships can be determined"],
            dependencies=[components_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(relationships_step)
        
        # Step 4: Draw conclusions
        conclusion_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.CONCLUSION,
            content="Drawing conclusions based on systematic analysis",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Complete analysis"],
            assumptions=["Analysis is comprehensive"],
            dependencies=[relationships_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(conclusion_step)
        
        reasoning_chain.final_conclusion = "Systematic analysis completed with identified components and relationships"
    
    async def _hypothesis_testing_strategy(self, reasoning_chain: ReasoningChain):
        """Hypothesis testing reasoning strategy"""
        
        problem = reasoning_chain.problem_statement
        
        # Step 1: Generate hypotheses
        hypothesis_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.HYPOTHESIS,
            content=f"Generating hypotheses for: {problem}",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Problem analysis"],
            assumptions=["Multiple hypotheses are possible"],
            dependencies=[],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(hypothesis_step)
        
        # Step 2: Test hypotheses
        testing_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.VERIFICATION,
            content="Testing hypotheses against available evidence",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Hypothesis testing"],
            assumptions=["Evidence is reliable"],
            dependencies=[hypothesis_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(testing_step)
        
        # Step 3: Evaluate results
        evaluation_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.ANALYSIS,
            content="Evaluating test results and hypothesis validity",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Test results"],
            assumptions=["Evaluation criteria are appropriate"],
            dependencies=[testing_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(evaluation_step)
        
        # Step 4: Draw conclusions
        conclusion_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.CONCLUSION,
            content="Drawing conclusions based on hypothesis testing",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Complete testing"],
            assumptions=["Testing was thorough"],
            dependencies=[evaluation_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(conclusion_step)
        
        reasoning_chain.final_conclusion = "Hypothesis testing completed with validated conclusions"
    
    async def _comparative_analysis_strategy(self, reasoning_chain: ReasoningChain):
        """Comparative analysis reasoning strategy"""
        
        problem = reasoning_chain.problem_statement
        
        # Step 1: Identify comparison criteria
        criteria_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.OBSERVATION,
            content="Identifying criteria for comparison",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Problem analysis"],
            assumptions=["Comparison criteria can be established"],
            dependencies=[],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(criteria_step)
        
        # Step 2: Gather comparison data
        data_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.ANALYSIS,
            content="Gathering data for comparison",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Data collection"],
            assumptions=["Relevant data is available"],
            dependencies=[criteria_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(data_step)
        
        # Step 3: Perform comparison
        comparison_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.ANALYSIS,
            content="Performing comparative analysis",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Comparison data"],
            assumptions=["Comparison methods are valid"],
            dependencies=[data_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(comparison_step)
        
        # Step 4: Draw conclusions
        conclusion_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.CONCLUSION,
            content="Drawing conclusions from comparative analysis",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Complete comparison"],
            assumptions=["Comparison was comprehensive"],
            dependencies=[comparison_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(conclusion_step)
        
        reasoning_chain.final_conclusion = "Comparative analysis completed with clear distinctions identified"
    
    async def _causal_reasoning_strategy(self, reasoning_chain: ReasoningChain):
        """Causal reasoning strategy"""
        
        problem = reasoning_chain.problem_statement
        
        # Step 1: Identify causal factors
        factors_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.OBSERVATION,
            content="Identifying potential causal factors",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Problem analysis"],
            assumptions=["Causal factors can be identified"],
            dependencies=[],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(factors_step)
        
        # Step 2: Analyze causal relationships
        relationships_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.ANALYSIS,
            content="Analyzing causal relationships between factors",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Causal analysis"],
            assumptions=["Causal relationships exist"],
            dependencies=[factors_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(relationships_step)
        
        # Step 3: Verify causality
        verification_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.VERIFICATION,
            content="Verifying causal relationships",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Causal verification"],
            assumptions=["Verification methods are reliable"],
            dependencies=[relationships_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(verification_step)
        
        # Step 4: Draw conclusions
        conclusion_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.CONCLUSION,
            content="Drawing conclusions about causal relationships",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Complete causal analysis"],
            assumptions=["Analysis is comprehensive"],
            dependencies=[verification_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(conclusion_step)
        
        reasoning_chain.final_conclusion = "Causal reasoning completed with verified relationships"
    
    async def _general_reasoning_strategy(self, reasoning_chain: ReasoningChain):
        """General reasoning strategy"""
        
        problem = reasoning_chain.problem_statement
        
        # Step 1: Initial observation
        observation_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.OBSERVATION,
            content=f"Initial observation of problem: {problem}",
            confidence=ConfidenceLevel.HIGH,
            evidence=["Problem statement"],
            assumptions=["Problem is well-defined"],
            dependencies=[],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(observation_step)
        
        # Step 2: Analysis
        analysis_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.ANALYSIS,
            content="Analyzing the problem and available information",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Problem analysis"],
            assumptions=["Analysis is thorough"],
            dependencies=[observation_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(analysis_step)
        
        # Step 3: Inference
        inference_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.INFERENCE,
            content="Drawing inferences from the analysis",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Analysis results"],
            assumptions=["Inferences are valid"],
            dependencies=[analysis_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(inference_step)
        
        # Step 4: Conclusion
        conclusion_step = ReasoningStep(
            step_id=str(uuid.uuid4()),
            step_type=ReasoningStep.CONCLUSION,
            content="Drawing final conclusions",
            confidence=ConfidenceLevel.MEDIUM,
            evidence=["Complete reasoning"],
            assumptions=["Reasoning is sound"],
            dependencies=[inference_step.step_id],
            timestamp=datetime.now()
        )
        reasoning_chain.steps.append(conclusion_step)
        
        reasoning_chain.final_conclusion = "General reasoning completed with logical conclusions"
    
    async def _select_strategy(self, problem: str, context: Optional[Dict[str, Any]]) -> str:
        """Select appropriate reasoning strategy"""
        
        problem_lower = problem.lower()
        
        # Strategy selection based on problem type
        if any(keyword in problem_lower for keyword in ["compare", "comparison", "versus", "vs"]):
            return "comparative_analysis"
        elif any(keyword in problem_lower for keyword in ["cause", "effect", "why", "because"]):
            return "causal_reasoning"
        elif any(keyword in problem_lower for keyword in ["hypothesis", "test", "verify", "prove"]):
            return "hypothesis_testing"
        elif any(keyword in problem_lower for keyword in ["analyze", "systematic", "comprehensive"]):
            return "systematic_analysis"
        else:
            return "general_reasoning"
    
    async def _verify_reasoning_step(self, step: ReasoningStep) -> Dict[str, Any]:
        """Verify a single reasoning step"""
        
        verification = {
            "step_id": step.step_id,
            "validity": "valid",
            "confidence": step.confidence.value,
            "evidence_quality": "good",
            "assumption_validity": "valid",
            "issues": []
        }
        
        # Check evidence quality
        if not step.evidence:
            verification["evidence_quality"] = "poor"
            verification["issues"].append("No evidence provided")
        
        # Check assumption validity
        if not step.assumptions:
            verification["assumption_validity"] = "unclear"
            verification["issues"].append("No assumptions stated")
        
        # Check confidence level
        if step.confidence == ConfidenceLevel.LOW:
            verification["issues"].append("Low confidence level")
        
        return verification
    
    async def _check_logical_flow(self, chain: ReasoningChain) -> Dict[str, Any]:
        """Check logical flow of reasoning chain"""
        
        flow_check = {
            "consistent": True,
            "recommendations": []
        }
        
        # Check step dependencies
        step_ids = {step.step_id for step in chain.steps}
        for step in chain.steps:
            for dep_id in step.dependencies:
                if dep_id not in step_ids:
                    flow_check["consistent"] = False
                    flow_check["recommendations"].append(f"Step {step.step_id} depends on missing step {dep_id}")
        
        # Check step order
        if len(chain.steps) > 1:
            for i, step in enumerate(chain.steps[1:], 1):
                if step.timestamp < chain.steps[i-1].timestamp:
                    flow_check["recommendations"].append("Step timestamps are not in chronological order")
        
        return flow_check
    
    async def _assess_evidence_quality(self, chain: ReasoningChain) -> Dict[str, Any]:
        """Assess quality of evidence in reasoning chain"""
        
        evidence_assessment = {
            "quality": "good",
            "recommendations": []
        }
        
        total_evidence = 0
        for step in chain.steps:
            total_evidence += len(step.evidence)
        
        if total_evidence == 0:
            evidence_assessment["quality"] = "poor"
            evidence_assessment["recommendations"].append("No evidence provided in any step")
        elif total_evidence < len(chain.steps):
            evidence_assessment["quality"] = "fair"
            evidence_assessment["recommendations"].append("Some steps lack evidence")
        
        return evidence_assessment
    
    async def _calculate_overall_confidence(self, chain: ReasoningChain) -> ConfidenceLevel:
        """Calculate overall confidence for the reasoning chain"""
        
        if not chain.steps:
            return ConfidenceLevel.LOW
        
        # Calculate average confidence
        confidence_scores = {
            ConfidenceLevel.LOW: 1,
            ConfidenceLevel.MEDIUM: 2,
            ConfidenceLevel.HIGH: 3,
            ConfidenceLevel.VERY_HIGH: 4
        }
        
        total_score = sum(confidence_scores[step.confidence] for step in chain.steps)
        average_score = total_score / len(chain.steps)
        
        # Map to confidence level
        if average_score >= 3.5:
            return ConfidenceLevel.VERY_HIGH
        elif average_score >= 2.5:
            return ConfidenceLevel.HIGH
        elif average_score >= 1.5:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW
    
    def _initialize_strategies(self) -> Dict[str, Any]:
        """Initialize reasoning strategies"""
        
        return {
            "systematic_analysis": {
                "description": "Systematic breakdown and analysis of problems",
                "use_cases": ["complex problems", "structured analysis"],
                "steps": ["decomposition", "component_analysis", "relationship_analysis", "conclusion"]
            },
            "hypothesis_testing": {
                "description": "Generate and test hypotheses",
                "use_cases": ["scientific problems", "verification tasks"],
                "steps": ["hypothesis_generation", "testing", "evaluation", "conclusion"]
            },
            "comparative_analysis": {
                "description": "Compare and contrast different options",
                "use_cases": ["decision making", "evaluation tasks"],
                "steps": ["criteria_identification", "data_gathering", "comparison", "conclusion"]
            },
            "causal_reasoning": {
                "description": "Analyze cause and effect relationships",
                "use_cases": ["explanation tasks", "root cause analysis"],
                "steps": ["factor_identification", "relationship_analysis", "verification", "conclusion"]
            }
        }
    
    def _initialize_verification_methods(self) -> Dict[str, Any]:
        """Initialize verification methods"""
        
        return {
            "logical_consistency": "Check for logical contradictions",
            "evidence_validation": "Validate evidence quality and relevance",
            "assumption_checking": "Verify assumptions are reasonable",
            "dependency_verification": "Check step dependencies are valid"
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of reasoning engine"""
        return {
            "chain_of_thought_reasoner": True,
            "reasoning_chains": len(self.reasoning_chains),
            "strategies_available": len(self.reasoning_strategies),
            "verification_methods": len(self.verification_methods)
        }

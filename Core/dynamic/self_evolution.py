"""
Self-Evolution Engine
System that learns, adapts, and evolves its own capabilities
"""

import asyncio
import json
import time
import threading
from typing import Dict, List, Any, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
from collections import defaultdict, deque
import pickle
import hashlib

from ..config.logging import get_logger
from ..config.exceptions import EvolutionError

logger = get_logger(__name__)


class EvolutionType(str, Enum):
    """Types of evolution"""
    PERFORMANCE_OPTIMIZATION = "performance_optimization"
    CAPABILITY_EXPANSION = "capability_expansion"
    ERROR_REDUCTION = "error_reduction"
    EFFICIENCY_IMPROVEMENT = "efficiency_improvement"
    ADAPTIVE_LEARNING = "adaptive_learning"


class LearningMode(str, Enum):
    """Learning modes"""
    SUPERVISED = "supervised"
    UNSUPERVISED = "unsupervised"
    REINFORCEMENT = "reinforcement"
    META_LEARNING = "meta_learning"


@dataclass
class LearningData:
    """Learning data point"""
    timestamp: datetime
    input_data: Any
    output_data: Any
    success: bool
    performance_metrics: Dict[str, float]
    context: Dict[str, Any] = field(default_factory=dict)
    feedback: Optional[float] = None


@dataclass
class EvolutionRule:
    """Evolution rule definition"""
    name: str
    condition: Callable
    action: Callable
    priority: int = 1
    enabled: bool = True
    success_count: int = 0
    failure_count: int = 0
    last_triggered: Optional[datetime] = None


@dataclass
class Capability:
    """System capability definition"""
    name: str
    description: str
    current_level: float
    max_level: float
    learning_rate: float
    dependencies: List[str] = field(default_factory=list)
    performance_history: deque = field(default_factory=lambda: deque(maxlen=1000))
    last_updated: datetime = field(default_factory=datetime.utcnow)


class LearningSystem:
    """Advanced learning system for self-evolution"""
    
    def __init__(self, memory_size: int = 10000):
        self.memory_size = memory_size
        self.learning_data: deque = deque(maxlen=memory_size)
        self.patterns: Dict[str, Any] = {}
        self.models: Dict[str, Any] = {}
        self.learning_mode = LearningMode.UNSUPERVISED
        self.is_learning = False
        
        # Learning parameters
        self.learning_rate = 0.01
        self.exploration_rate = 0.1
        self.memory_decay = 0.95
        
        # Performance tracking
        self.performance_history = deque(maxlen=1000)
        self.improvement_threshold = 0.05
        
    def add_learning_data(self, data: LearningData):
        """Add learning data point"""
        self.learning_data.append(data)
        
        # Update patterns
        self._update_patterns(data)
        
        # Trigger learning if enough data
        if len(self.learning_data) % 100 == 0:
            asyncio.create_task(self._learn_from_data())
    
    def _update_patterns(self, data: LearningData):
        """Update pattern recognition"""
        # Simple pattern extraction (can be enhanced with ML)
        pattern_key = self._extract_pattern_key(data)
        
        if pattern_key not in self.patterns:
            self.patterns[pattern_key] = {
                'count': 0,
                'success_rate': 0.0,
                'avg_performance': 0.0,
                'last_seen': data.timestamp
            }
        
        pattern = self.patterns[pattern_key]
        pattern['count'] += 1
        
        # Update success rate
        if data.success:
            pattern['success_rate'] = (pattern['success_rate'] * (pattern['count'] - 1) + 1) / pattern['count']
        else:
            pattern['success_rate'] = (pattern['success_rate'] * (pattern['count'] - 1)) / pattern['count']
        
        # Update average performance
        avg_perf = sum(data.performance_metrics.values()) / len(data.performance_metrics)
        pattern['avg_performance'] = (pattern['avg_performance'] * (pattern['count'] - 1) + avg_perf) / pattern['count']
        pattern['last_seen'] = data.timestamp
    
    def _extract_pattern_key(self, data: LearningData) -> str:
        """Extract pattern key from data"""
        # Simple hash-based pattern key
        key_data = {
            'input_type': type(data.input_data).__name__,
            'context_keys': sorted(data.context.keys()),
            'success': data.success
        }
        return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()[:16]
    
    async def _learn_from_data(self):
        """Learn from accumulated data"""
        if self.is_learning:
            return
        
        self.is_learning = True
        try:
            # Analyze patterns
            await self._analyze_patterns()
            
            # Update models
            await self._update_models()
            
            # Generate insights
            await self._generate_insights()
            
        finally:
            self.is_learning = False
    
    async def _analyze_patterns(self):
        """Analyze learning patterns"""
        # Find high-performing patterns
        high_performance_patterns = [
            (key, pattern) for key, pattern in self.patterns.items()
            if pattern['success_rate'] > 0.8 and pattern['avg_performance'] > 0.7
        ]
        
        # Find low-performing patterns
        low_performance_patterns = [
            (key, pattern) for key, pattern in self.patterns.items()
            if pattern['success_rate'] < 0.3 or pattern['avg_performance'] < 0.3
        ]
        
        logger.info(f"Found {len(high_performance_patterns)} high-performance patterns")
        logger.info(f"Found {len(low_performance_patterns)} low-performance patterns")
    
    async def _update_models(self):
        """Update learning models"""
        # This would implement actual ML model updates
        # For now, we'll simulate model updates
        pass
    
    async def _generate_insights(self):
        """Generate learning insights"""
        insights = []
        
        # Analyze success patterns
        recent_data = list(self.learning_data)[-100:]  # Last 100 data points
        if recent_data:
            success_rate = sum(1 for d in recent_data if d.success) / len(recent_data)
            avg_performance = sum(
                sum(d.performance_metrics.values()) / len(d.performance_metrics)
                for d in recent_data
            ) / len(recent_data)
            
            insights.append({
                'type': 'performance_summary',
                'success_rate': success_rate,
                'avg_performance': avg_performance,
                'data_points': len(recent_data)
            })
        
        # Store insights
        self.insights = insights
    
    def get_learning_statistics(self) -> Dict[str, Any]:
        """Get learning statistics"""
        if not self.learning_data:
            return {"message": "No learning data available"}
        
        recent_data = list(self.learning_data)[-1000:]  # Last 1000 data points
        
        return {
            "total_data_points": len(self.learning_data),
            "recent_data_points": len(recent_data),
            "patterns_discovered": len(self.patterns),
            "learning_mode": self.learning_mode.value,
            "is_learning": self.is_learning,
            "success_rate": sum(1 for d in recent_data if d.success) / len(recent_data) if recent_data else 0,
            "avg_performance": sum(
                sum(d.performance_metrics.values()) / len(d.performance_metrics)
                for d in recent_data
            ) / len(recent_data) if recent_data else 0,
            "insights": getattr(self, 'insights', [])
        }


class SelfEvolutionEngine:
    """Main self-evolution engine"""
    
    def __init__(self):
        self.learning_system = LearningSystem()
        self.capabilities: Dict[str, Capability] = {}
        self.evolution_rules: List[EvolutionRule] = []
        self.is_evolving = False
        self.evolution_history: List[Dict[str, Any]] = []
        
        # Initialize default capabilities
        self._initialize_default_capabilities()
        
        # Initialize evolution rules
        self._initialize_evolution_rules()
        
        # Start evolution process
        self._start_evolution_process()
    
    def _initialize_default_capabilities(self):
        """Initialize default system capabilities"""
        default_capabilities = [
            Capability(
                name="text_processing",
                description="Text processing and analysis",
                current_level=0.7,
                max_level=1.0,
                learning_rate=0.01
            ),
            Capability(
                name="code_generation",
                description="Code generation and analysis",
                current_level=0.6,
                max_level=1.0,
                learning_rate=0.01
            ),
            Capability(
                name="data_analysis",
                description="Data analysis and insights",
                current_level=0.5,
                max_level=1.0,
                learning_rate=0.01
            ),
            Capability(
                name="system_optimization",
                description="System performance optimization",
                current_level=0.4,
                max_level=1.0,
                learning_rate=0.005
            ),
            Capability(
                name="error_handling",
                description="Error detection and handling",
                current_level=0.8,
                max_level=1.0,
                learning_rate=0.02
            )
        ]
        
        for cap in default_capabilities:
            self.capabilities[cap.name] = cap
        
        logger.info(f"Initialized {len(self.capabilities)} capabilities")
    
    def _initialize_evolution_rules(self):
        """Initialize evolution rules"""
        # Performance optimization rule
        def performance_condition():
            recent_performance = list(self.learning_system.learning_data)[-100:]
            if not recent_performance:
                return False
            
            avg_performance = sum(
                sum(d.performance_metrics.values()) / len(d.performance_metrics)
                for d in recent_performance
            ) / len(recent_performance)
            
            return avg_performance < 0.7
        
        def performance_action():
            # Optimize system performance
            logger.info("Triggering performance optimization")
            return {"action": "optimize_performance", "target": "system"}
        
        self.evolution_rules.append(EvolutionRule(
            name="performance_optimization",
            condition=performance_condition,
            action=performance_action,
            priority=1
        ))
        
        # Capability expansion rule
        def capability_condition():
            # Check if any capability is at max level
            return any(cap.current_level >= cap.max_level * 0.9 for cap in self.capabilities.values())
        
        def capability_action():
            # Expand capabilities
            logger.info("Triggering capability expansion")
            return {"action": "expand_capabilities", "target": "all"}
        
        self.evolution_rules.append(EvolutionRule(
            name="capability_expansion",
            condition=capability_condition,
            action=capability_action,
            priority=2
        ))
        
        # Error reduction rule
        def error_condition():
            recent_data = list(self.learning_system.learning_data)[-50:]
            if not recent_data:
                return False
            
            error_rate = sum(1 for d in recent_data if not d.success) / len(recent_data)
            return error_rate > 0.2
        
        def error_action():
            # Improve error handling
            logger.info("Triggering error reduction")
            return {"action": "reduce_errors", "target": "error_handling"}
        
        self.evolution_rules.append(EvolutionRule(
            name="error_reduction",
            condition=error_condition,
            action=error_action,
            priority=3
        ))
        
        logger.info(f"Initialized {len(self.evolution_rules)} evolution rules")
    
    def _start_evolution_process(self):
        """Start the evolution process"""
        def evolution_loop():
            while True:
                try:
                    if not self.is_evolving:
                        asyncio.create_task(self._run_evolution_cycle())
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    logger.error(f"Error in evolution loop: {e}")
                    time.sleep(300)  # Wait 5 minutes on error
        
        thread = threading.Thread(target=evolution_loop, daemon=True)
        thread.start()
        logger.info("Evolution process started")
    
    async def _run_evolution_cycle(self):
        """Run a single evolution cycle"""
        if self.is_evolving:
            return
        
        self.is_evolving = True
        try:
            # Check evolution rules
            triggered_rules = []
            for rule in self.evolution_rules:
                if rule.enabled and rule.condition():
                    try:
                        result = rule.action()
                        rule.success_count += 1
                        rule.last_triggered = datetime.utcnow()
                        triggered_rules.append({
                            'rule': rule.name,
                            'result': result,
                            'timestamp': datetime.utcnow()
                        })
                        logger.info(f"Evolution rule triggered: {rule.name}")
                    except Exception as e:
                        rule.failure_count += 1
                        logger.error(f"Error in evolution rule {rule.name}: {e}")
            
            # Update capabilities based on learning
            await self._update_capabilities()
            
            # Record evolution event
            if triggered_rules:
                self.evolution_history.append({
                    'timestamp': datetime.utcnow(),
                    'triggered_rules': triggered_rules,
                    'capabilities': {name: cap.current_level for name, cap in self.capabilities.items()}
                })
            
        finally:
            self.is_evolving = False
    
    async def _update_capabilities(self):
        """Update capabilities based on learning data"""
        recent_data = list(self.learning_system.learning_data)[-100:]
        if not recent_data:
            return
        
        # Calculate performance metrics for each capability
        capability_performance = defaultdict(list)
        
        for data in recent_data:
            for metric_name, value in data.performance_metrics.items():
                # Map metrics to capabilities
                if 'text' in metric_name.lower():
                    capability_performance['text_processing'].append(value)
                elif 'code' in metric_name.lower():
                    capability_performance['code_generation'].append(value)
                elif 'data' in metric_name.lower():
                    capability_performance['data_analysis'].append(value)
                elif 'error' in metric_name.lower():
                    capability_performance['error_handling'].append(value)
                else:
                    capability_performance['system_optimization'].append(value)
        
        # Update capability levels
        for cap_name, cap in self.capabilities.items():
            if cap_name in capability_performance:
                performance_values = capability_performance[cap_name]
                avg_performance = sum(performance_values) / len(performance_values)
                
                # Update capability level based on performance
                improvement = (avg_performance - 0.5) * cap.learning_rate
                new_level = max(0.0, min(cap.max_level, cap.current_level + improvement))
                
                if abs(new_level - cap.current_level) > 0.01:  # Significant change
                    cap.current_level = new_level
                    cap.last_updated = datetime.utcnow()
                    cap.performance_history.append(avg_performance)
                    
                    logger.info(f"Updated capability {cap_name}: {cap.current_level:.3f}")
    
    def add_learning_data(self, input_data: Any, output_data: Any, success: bool, 
                         performance_metrics: Dict[str, float], context: Dict[str, Any] = None):
        """Add learning data to the system"""
        learning_data = LearningData(
            timestamp=datetime.utcnow(),
            input_data=input_data,
            output_data=output_data,
            success=success,
            performance_metrics=performance_metrics,
            context=context or {}
        )
        
        self.learning_system.add_learning_data(learning_data)
    
    def get_capability_level(self, name: str) -> float:
        """Get current capability level"""
        return self.capabilities.get(name, Capability("unknown", "", 0.0, 1.0, 0.01)).current_level
    
    def improve_capability(self, name: str, improvement: float):
        """Manually improve a capability"""
        if name in self.capabilities:
            cap = self.capabilities[name]
            new_level = max(0.0, min(cap.max_level, cap.current_level + improvement))
            cap.current_level = new_level
            cap.last_updated = datetime.utcnow()
            logger.info(f"Manually improved capability {name}: {new_level:.3f}")
    
    def add_evolution_rule(self, rule: EvolutionRule):
        """Add a new evolution rule"""
        self.evolution_rules.append(rule)
        logger.info(f"Added evolution rule: {rule.name}")
    
    def get_evolution_status(self) -> Dict[str, Any]:
        """Get current evolution status"""
        return {
            "is_evolving": self.is_evolving,
            "capabilities": {
                name: {
                    "level": cap.current_level,
                    "max_level": cap.max_level,
                    "learning_rate": cap.learning_rate,
                    "last_updated": cap.last_updated.isoformat(),
                    "performance_history_length": len(cap.performance_history)
                }
                for name, cap in self.capabilities.items()
            },
            "evolution_rules": [
                {
                    "name": rule.name,
                    "enabled": rule.enabled,
                    "priority": rule.priority,
                    "success_count": rule.success_count,
                    "failure_count": rule.failure_count,
                    "last_triggered": rule.last_triggered.isoformat() if rule.last_triggered else None
                }
                for rule in self.evolution_rules
            ],
            "learning_statistics": self.learning_system.get_learning_statistics(),
            "evolution_history_length": len(self.evolution_history)
        }
    
    def get_evolution_recommendations(self) -> List[Dict[str, Any]]:
        """Get evolution recommendations"""
        recommendations = []
        
        # Check for low-performing capabilities
        for name, cap in self.capabilities.items():
            if cap.current_level < 0.5:
                recommendations.append({
                    "type": "capability_improvement",
                    "capability": name,
                    "current_level": cap.current_level,
                    "recommendation": f"Focus on improving {name} capability",
                    "priority": "high"
                })
        
        # Check for underutilized capabilities
        for name, cap in self.capabilities.items():
            if cap.current_level > 0.8 and len(cap.performance_history) < 10:
                recommendations.append({
                    "type": "capability_utilization",
                    "capability": name,
                    "current_level": cap.current_level,
                    "recommendation": f"Utilize {name} capability more frequently",
                    "priority": "medium"
                })
        
        # Check learning system performance
        learning_stats = self.learning_system.get_learning_statistics()
        if learning_stats.get("success_rate", 0) < 0.7:
            recommendations.append({
                "type": "learning_optimization",
                "recommendation": "Improve learning system performance",
                "priority": "high"
            })
        
        return recommendations
    
    def export_evolution_data(self) -> Dict[str, Any]:
        """Export evolution data for analysis"""
        return {
            "capabilities": {
                name: {
                    "level": cap.current_level,
                    "max_level": cap.max_level,
                    "learning_rate": cap.learning_rate,
                    "performance_history": list(cap.performance_history),
                    "last_updated": cap.last_updated.isoformat()
                }
                for name, cap in self.capabilities.items()
            },
            "evolution_history": [
                {
                    "timestamp": event["timestamp"].isoformat(),
                    "triggered_rules": event["triggered_rules"],
                    "capabilities": event["capabilities"]
                }
                for event in self.evolution_history
            ],
            "learning_data": [
                {
                    "timestamp": data.timestamp.isoformat(),
                    "success": data.success,
                    "performance_metrics": data.performance_metrics,
                    "context": data.context
                }
                for data in list(self.learning_system.learning_data)[-1000:]  # Last 1000 data points
            ]
        }


# Global evolution engine instance
_evolution_engine: Optional[SelfEvolutionEngine] = None


def get_evolution_engine() -> SelfEvolutionEngine:
    """Get global evolution engine instance"""
    global _evolution_engine
    if _evolution_engine is None:
        _evolution_engine = SelfEvolutionEngine()
    return _evolution_engine


def add_learning_data(input_data: Any, output_data: Any, success: bool, 
                     performance_metrics: Dict[str, float], context: Dict[str, Any] = None):
    """Add learning data to the global evolution engine"""
    engine = get_evolution_engine()
    engine.add_learning_data(input_data, output_data, success, performance_metrics, context)
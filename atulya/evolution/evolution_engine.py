"""Evolution Engine for AGI growth and learning"""

from typing import Dict, Any, List
from datetime import datetime
import logging
import random

logger = logging.getLogger(__name__)


class EvolutionEngine:
    """
    Manages continuous evolution and self-improvement of Atulya
    """

    def __init__(self):
        """Initialize Evolution Engine"""
        self.evolution_history = []
        self.current_generation = 0
        self.fitness_scores = []
        self.parameters = {
            "learning_rate": 0.001,
            "exploration_factor": 0.1,
            "mutation_rate": 0.05
        }
        logger.info("Evolution Engine initialized")

    def evolve(self, task: str, result: Dict, insights: Dict) -> Dict:
        """
        Perform evolutionary step based on task result
        
        Args:
            task: Task executed
            result: Task result
            insights: Learning insights
            
        Returns:
            Evolution metrics
        """
        self.current_generation += 1
        
        # Calculate fitness
        fitness = self._calculate_fitness(result, insights)
        self.fitness_scores.append(fitness)
        
        # Store evolution step
        evolution_entry = {
            "generation": self.current_generation,
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "fitness": fitness,
            "insights": insights
        }
        
        self.evolution_history.append(evolution_entry)
        
        # Adapt parameters based on performance
        self._adapt_parameters(fitness)
        
        logger.info(f"Generation {self.current_generation}: fitness={fitness:.4f}")
        
        return {
            "generation": self.current_generation,
            "fitness": fitness,
            "adapted_parameters": self.parameters.copy()
        }

    def _calculate_fitness(self, result: Dict, insights: Dict) -> float:
        """
        Calculate fitness score
        
        Args:
            result: Task result
            insights: Execution insights
            
        Returns:
            Fitness score (0-1)
        """
        score = 0.0
        
        # Success component
        if insights.get("success"):
            score += 0.5
        
        # Confidence component
        confidence = insights.get("confidence", 0.0)
        score += confidence * 0.3
        
        # Efficiency component (inverse of execution time)
        exec_time = insights.get("execution_time", 1.0)
        score += min(0.2, 0.1 / exec_time)
        
        return min(1.0, score)

    def _adapt_parameters(self, fitness: float) -> None:
        """
        Adapt learning parameters based on fitness
        
        Args:
            fitness: Current fitness score
        """
        # If fitness is improving, increase learning rate
        if len(self.fitness_scores) > 1:
            prev_fitness = self.fitness_scores[-2]
            
            if fitness > prev_fitness:
                self.parameters["learning_rate"] *= 1.05
                self.parameters["exploration_factor"] *= 0.95
            else:
                self.parameters["learning_rate"] *= 0.95
                self.parameters["exploration_factor"] *= 1.05
        
        # Clamp parameters
        self.parameters["learning_rate"] = max(0.0001, min(0.01, self.parameters["learning_rate"]))
        self.parameters["exploration_factor"] = max(0.01, min(0.5, self.parameters["exploration_factor"]))

    def mutate_strategy(self) -> Dict:
        """
        Perform strategic mutation for exploration
        
        Returns:
            Mutation parameters
        """
        mutations = {}
        
        for param, value in self.parameters.items():
            mutation_amount = random.gauss(0, self.parameters["mutation_rate"])
            mutations[param] = value * (1 + mutation_amount)
        
        return mutations

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get evolution metrics and progress
        
        Returns:
            Evolution metrics
        """
        if not self.fitness_scores:
            return {
                "generation": 0,
                "avg_fitness": 0.0,
                "max_fitness": 0.0,
                "evolution_progress": 0.0
            }
        
        avg_fitness = sum(self.fitness_scores) / len(self.fitness_scores)
        max_fitness = max(self.fitness_scores)
        
        # Calculate progress (improvement over generations)
        progress = 0.0
        if len(self.fitness_scores) > 1:
            initial_fitness = self.fitness_scores[0]
            current_fitness = self.fitness_scores[-1]
            progress = (current_fitness - initial_fitness) / initial_fitness if initial_fitness > 0 else 0
        
        return {
            "generation": self.current_generation,
            "avg_fitness": round(avg_fitness, 4),
            "max_fitness": round(max_fitness, 4),
            "evolution_progress": round(progress, 4),
            "parameters": self.parameters.copy()
        }

    def boost_learning(self) -> Dict:
        """
        Boost learning capabilities
        
        Returns:
            Boost results
        """
        boost_results = {
            "learning_rate_increase": 0.2,
            "exploration_increase": 0.1,
            "previous_parameters": self.parameters.copy()
        }
        
        self.parameters["learning_rate"] *= 1.2
        self.parameters["exploration_factor"] *= 1.1
        
        boost_results["new_parameters"] = self.parameters.copy()
        
        logger.info("Learning capabilities boosted")
        return boost_results

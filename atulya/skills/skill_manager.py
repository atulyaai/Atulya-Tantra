"""Skill Manager for dynamic skill acquisition and management"""

from typing import Dict, List, Any, Optional
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SkillManager:
    """
    Manages skills acquisition, refinement, and application
    """

    def __init__(self):
        """Initialize Skill Manager"""
        self.skills = {}
        self.skill_history = []
        self.proficiency_levels = {}
        logger.info("Skill Manager initialized")

    def add_skill(self, skill_name: str, skill_data: Dict) -> bool:
        """
        Add a new skill
        
        Args:
            skill_name: Name of the skill
            skill_data: Skill definition and training data
            
        Returns:
            Success status
        """
        if skill_name in self.skills:
            logger.warning(f"Skill '{skill_name}' already exists")
            return False
        
        skill_entry = {
            "name": skill_name,
            "data": skill_data,
            "created_at": datetime.now().isoformat(),
            "proficiency": skill_data.get("initial_proficiency", 0.5),
            "usage_count": 0,
            "success_count": 0
        }
        
        self.skills[skill_name] = skill_entry
        self.proficiency_levels[skill_name] = skill_entry["proficiency"]
        
        logger.info(f"Skill '{skill_name}' added")
        return True

    def use_skill(self, skill_name: str, context: Dict = None) -> Dict:
        """
        Use a skill
        
        Args:
            skill_name: Name of the skill to use
            context: Optional execution context
            
        Returns:
            Skill execution result
        """
        if skill_name not in self.skills:
            logger.error(f"Skill '{skill_name}' not found")
            return {
                "success": False,
                "error": f"Skill '{skill_name}' not found"
            }
        
        skill = self.skills[skill_name]
        skill["usage_count"] += 1
        
        # Simulate skill execution
        success = skill["proficiency"] > 0.5
        
        if success:
            skill["success_count"] += 1
            self._improve_skill(skill_name)
        
        result = {
            "skill": skill_name,
            "success": success,
            "proficiency": skill["proficiency"],
            "usage_count": skill["usage_count"]
        }
        
        return result

    def _improve_skill(self, skill_name: str) -> None:
        """
        Improve skill proficiency through use
        
        Args:
            skill_name: Name of the skill
        """
        if skill_name in self.skills:
            skill = self.skills[skill_name]
            improvement = 0.01 * (1 - skill["proficiency"])  # Diminishing returns
            skill["proficiency"] = min(1.0, skill["proficiency"] + improvement)
            self.proficiency_levels[skill_name] = skill["proficiency"]

    def get_skill(self, skill_name: str) -> Optional[Dict]:
        """
        Get skill information
        
        Args:
            skill_name: Name of the skill
            
        Returns:
            Skill data or None
        """
        return self.skills.get(skill_name)

    def list_skills(self) -> List[Dict]:
        """
        List all skills
        
        Returns:
            List of skills with proficiency levels
        """
        return [
            {
                "name": name,
                "proficiency": skill["proficiency"],
                "usage_count": skill["usage_count"],
                "success_rate": skill["success_count"] / max(1, skill["usage_count"])
            }
            for name, skill in self.skills.items()
        ]

    def count_skills(self) -> int:
        """
        Get number of skills
        
        Returns:
            Skill count
        """
        return len(self.skills)

    def refine_skills(self) -> Dict:
        """
        Refine all skills based on usage data
        
        Returns:
            Refinement results
        """
        refined_count = 0
        
        for skill_name, skill in self.skills.items():
            if skill["usage_count"] > 0:
                success_rate = skill["success_count"] / skill["usage_count"]
                
                # Adjust proficiency based on success rate
                if success_rate > 0.8:
                    skill["proficiency"] = min(1.0, skill["proficiency"] + 0.05)
                    refined_count += 1
                elif success_rate < 0.5:
                    skill["proficiency"] = max(0.0, skill["proficiency"] - 0.02)
        
        logger.info(f"Refined {refined_count} skills")
        
        return {
            "refined_count": refined_count,
            "skills": self.list_skills()
        }

    def get_best_skill(self, category: str = None) -> Optional[str]:
        """
        Get best performing skill
        
        Args:
            category: Optional skill category filter
            
        Returns:
            Skill name with highest proficiency
        """
        if not self.skills:
            return None
        
        best_skill = max(self.skills.items(),
                        key=lambda x: x[1]["proficiency"])
        
        return best_skill[0]

    def export_skills(self) -> Dict:
        """
        Export all skills for backup
        
        Returns:
            Exported skills data
        """
        return {
            "export_date": datetime.now().isoformat(),
            "skills": self.list_skills(),
            "proficiency_levels": self.proficiency_levels.copy()
        }

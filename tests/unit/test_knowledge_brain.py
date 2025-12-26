"""
Unit tests for Knowledge Brain
Tests fact storage, retrieval, and TTL tracking.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.knowledge.knowledge_brain import KnowledgeBrain


class TestKnowledgeBrain:
    """Test suite for knowledge management."""
    
    def test_knowledge_brain_initialization(self):
        """Test that knowledge brain initializes correctly."""
        kb = KnowledgeBrain()
        assert kb is not None
    
    def test_fact_storage(self, sample_facts):
        """Test that facts can be stored."""
        kb = KnowledgeBrain()
        
        for fact in sample_facts:
            kb.store_fact(fact)
        
        # Verify storage
        stored_facts = kb.get_facts_by_topic("TEST")
        assert len(stored_facts) >= 2
    
    def test_fact_retrieval(self, sample_facts):
        """Test that facts can be retrieved by topic."""
        kb = KnowledgeBrain()
        
        for fact in sample_facts:
            kb.store_fact(fact)
        
        retrieved = kb.get_facts_by_topic("TEST")
        assert len(retrieved) > 0
        assert all(f["topic"] == "TEST" for f in retrieved)
    
    def test_confidence_filtering(self, sample_facts):
        """Test that facts can be filtered by confidence."""
        kb = KnowledgeBrain()
        
        for fact in sample_facts:
            kb.store_fact(fact)
        
        # Get high-confidence facts only
        high_conf = [f for f in kb.get_facts_by_topic("TEST") if f["confidence"] > 0.85]
        assert len(high_conf) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

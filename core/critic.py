class Critic:
    def verify(self, task, results, metadata=None):
        # v0.3 Multi-Objective Evaluation
        # Quality Dimensions
        headings = results.count("#")
        clarity_score = min(headings * 0.2, 0.4)
        
        has_structure = "Summary" in results or "Outcome" in results
        structure_score = 0.3 if has_structure else 0.0
        
        words = results.lower().split()
        unique_words = set(words)
        redundancy_ratio = 1.0 - (len(unique_words) / len(words)) if len(words) > 0 else 1.0
        redundancy_score = 0.3 if redundancy_ratio < 0.2 else 0.1
        
        quality_score = clarity_score + structure_score + redundancy_score
        
        # Resource Dimension (Signal Expansion)
        step_count = metadata.get("step_count", 0) if metadata else 0
        # Architecture Rule: Signal exists to influence selection resolution. 
        # v0.3 DOES NOT define preferences; it only exposes the signal.
        resource_usage = {"step_count": step_count}
        
        # Multi-Dimensional Map
        return {
            "quality": quality_score,
            "resource": resource_usage,
            "details": {
                "clarity": clarity_score,
                "structure": has_structure,
                "redundancy": redundancy_score
            }
        }

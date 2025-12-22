class Critic:
    def verify(self, task, results):
        # v0.2-E++ Numeric Scoring
        # Criteria: Clarity (headings), Structure (length/markers), Redundancy (repeated phrases)
        
        score = 0.0
        details = {}
        
        # 1. Clarity (Headings count)
        headings = results.count("#")
        clarity_score = min(headings * 0.2, 0.4) # Max 0.4 for clarity
        details["clarity"] = clarity_score
        
        # 2. Structure (Binary marker check)
        has_structure = "Summary" in results or "Outcome" in results
        structure_score = 0.3 if has_structure else 0.0
        details["structure"] = has_structure
        
        # 3. Redundancy (Simple length/repetition check)
        words = results.lower().split()
        unique_words = set(words)
        redundancy_ratio = 1.0 - (len(unique_words) / len(words)) if len(words) > 0 else 1.0
        redundancy_score = 0.3 if redundancy_ratio < 0.2 else 0.1
        details["redundancy"] = redundancy_score
        
        score = clarity_score + structure_score + redundancy_score
        
        return score, details

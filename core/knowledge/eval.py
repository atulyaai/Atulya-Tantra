import logging

class AtulyaEvalHarness:
    """
    Phase K3-B: Evaluation Protocol.
    Measures CoreLM progress using system-level delta metrics.
    """
    def __init__(self):
        self.logger = logging.getLogger("EvalHarness")

    def evaluate_fidelity(self, model_summary, ground_truth_summary):
        """
        Measures semantic loss between model output and ground truth.
        In Phase K3 Tier A, we use a basic ROUGE-inspired string overlap 
        or semantic comparison.
        """
        # Baseline: Character-level overlap (Strict Tier A)
        set1 = set(model_summary.lower().split())
        set2 = set(ground_truth_summary.lower().split())
        
        intersection = set1.intersection(set2)
        score = len(intersection) / max(len(set2), 1)
        return score

    def evaluate_calibration(self, perceived_uncertainty, actual_error):
        """
        Calibrates model self-awareness.
        Correlation should be high between uncertainty and error.
        """
        # High uncertainty (1.0) for high error (1.0) is a positive calibration
        # Score = 1 - abs(uncertainty - error)
        return 1.0 - abs(perceived_uncertainty - actual_error)

    def evaluate_friction_detection(self, model_response, factual_conflict_known=False):
        """
        Checks if the model correctly identified COGNITIVE_FRICTION.
        """
        keywords = ["friction", "contradict", "conflict", "clash"]
        detected = any(k in model_response.lower() for k in keywords)
        return detected == factual_conflict_known

    def run_suite(self, results_list):
        """
        Aggregates a results list into a final quality score.
        """
        if not results_list:
            return 0.0
            
        total_score = sum(r['score'] for r in results_list)
        return total_score / len(results_list)

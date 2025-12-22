# Phase K3 — CoreLM Data & Evaluation Implementation Plan

## Goal
Establish the data preparation pipeline and the internal evaluation harness required to train and validate `Atulya-CoreLM` according to ADR-011.

## Proposed Components

### 1. `CurriculumBuilder` (core/knowledge/curriculum.py)
- **Formatter**: Transforms Atomic Facts from the Knowledge Brain into training-ready templates.
- **Reliability Gauger**: Applies differential weighting to data chunks based on source lineage.
- **Synthetic Pair Generator**: Creates (Facts -> Summary) pairs for distillery training.

### 2. `AtulyaEvalHarness` (core/knowledge/eval.py)
- **Consistency Checker**: Measures the model's ability to identify contradictions in provided context.
- **Calibration Metric**: Benchmarks the alignment between perceived uncertainty and factual error.
- **Fidelity Ranker**: Automated scoring of distillation quality (Summarization vs. Ground Truth).

### 3. `WeightDeploymentManager` (core/knowledge/deployment.py)
- **Safety Gate**: Verifies that new model weights meet all K3 evaluation thresholds before deployment.
- **Rollback Engine**: Preserves the previous "Safe-Point" weights for immediate restoration if drift is detected.

## Verification Plan
1. **Scenario: Curriculum Weighting**: Inject data from a High-Reliability and Low-Reliability source. Verify the `CurriculumBuilder` assigns correct importance markers.
2. **Scenario: Contradiction Detection**: Run the `EvalHarness` on a contradictory knowledge window and verify it scores the model's detection accuracy.
3. **Scenario: Calibration Audit**: Feed the model purposefully incorrect context and verify that its uncertainty metadata (ADR-010) increases accordingly.
4. **Scenario: Deployment Gate**: Attempt to "deploy" weights that fail the Fidelity Ranker and verify the `WeightDeploymentManager` blocks the update.

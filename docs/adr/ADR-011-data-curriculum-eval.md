# ADR-011: Phase K3 CoreLM Data Curriculum & Evaluation Protocol

## Status
Proposed (Phase K3 Initiation)

## Context
Phase K1 and K2 defined the "where" and "how" of knowledge interaction. Phase K3 defines the "what"—the specific data curriculum and internal evaluation metrics that allow `Atulya-CoreLM` to grow into a disciplined knowledge organ. This ADR ensures that training is not a random ingestion of text, but a controlled compression of verified truth.

## 1. Data Curriculum Strategy
Training data is treated as a **Curriculum**, not a scrape.
- **Track 1: Foundations (Permanent)**: High-quality, slow-decay knowledge (e.g., core logic, architecture, immutable history).
- **Track 2: Domain-Specific (Delta)**: Specialized partitions (e.g., tool API specs, internal system logs, specific tech docs).
- **Track 3: Summarization Pairs**: Synthetic datasets consisting of (Atomic Facts list) -> (Compressed Summary) to reinforce the distillery function.

## 2. Chunking & Tokenization
- **Semantic Chunking**: Knowledge is not chunked by token count alone, but by "Topic Boundaries" defined in the Knowledge Brain.
- **Tokenization Persistence**: The tokenizer MUST be stable. Changing tokenizers is a breaking change for the Knowledge Brain state.

## 3. Leakage Prevention
To prevent "hallucinated spills" from noisy sources:
- **Source Labeling**: Every token window in the curriculum is tagged with a `SOURCE_RELIABILITY` score.
- **Differential Weighting**: High-reliability sources (Internal Docs) exert more "gradient pressure" than lower-reliability sources (External News).

## 4. Parameter Growth Path (Scalability)
- **Modular Expansion**: We start with 300M parameters.
- **Transition Gate**: Growth to 600M or 1.2B is authorized only when the smaller model saturates its evaluation metrics (i.e., further training on the same curriculum yields < 1% improvement).

## 5. Evaluation Protocol (Internal Benchmarking)
We do NOT use external benchmarks (e.g., MMLU). We use **System-Level Delta Metrics**:
- **Semantic Loss**: Measure the model's ability to reconstruct Atomic Facts from its weights.
- **Confidence Calibration**: Does the model's uncertainty triplet (ADR-010) correlate with actual errors? (Self-Awareness score).
- **Distillation Fidelity**: A BLEU/ROUGE comparison of model summaries vs. Ground-Truth summaries in the Knowledge Brain.
- **Cognitive Friction Score**: How well does the model detect contradictions injected into its context?

## 6. Training Safety
- **Offline Only**: Training occurs on isolated hardware (CPU/GPU) without direct bridge to the active Kernel.
- **Binary Deploy**: Only the final resulting weights (compressed knowledge) are transferred to the active Atulya-CoreLM directory after passing ALL evaluation gates.

## Consequences
- Training becomes predictable and verifiable.
- The model's "IQ" is measured by its utility to Atulya Tantra, not by general trivia.
- Avoids the "bloat" of unnecessary parameters.

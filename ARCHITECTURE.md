# NP-DNA Architecture — Deep Technical Guide

> **For AI agents and developers who need to understand the internals.**
> If you're adding features, fixing bugs, or extending the system, start here.

---

## Table of Contents
1. [System Overview](#system-overview)
2. [Data Flow](#data-flow)
3. [Component Deep-Dives](#component-deep-dives)
4. [The Math Behind DNA Compression](#the-math-behind-dna-compression)
5. [Training Pipeline](#training-pipeline)
6. [Adding New Modalities](#adding-new-modalities)
7. [Performance Characteristics](#performance-characteristics)
8. [Known Issues & Gotchas](#known-issues--gotchas)

---

## System Overview

NP-DNA (NeuroPlastic DNA Network) is a neural architecture that achieves large model intelligence with small parameter counts through four innovations:

```
┌─────────────────────────────────────────────────────────┐
│                    NP-DNA Architecture                  │
│                                                         │
│  Input IDs ──▶ Embedding ──▶ [Mesh Layer × N] ──▶ Head │
│                                   │                     │
│                              ┌────┴────┐                │
│                         Genome    Cortex                │
│                     (compress)   (memory)               │
│                              │                          │
│                        Plasticity                       │
│                      (self-adapt)                       │
└─────────────────────────────────────────────────────────┘
```

### Key Files

| File | Class | Responsibility |
|---|---|---|
| `config.py` | `NpDnaConfig`, `GenomeConfig`, etc. | All hyperparameters as dataclasses |
| `genome.py` | `Genome` | Generate weight matrices from DNA seeds |
| `strand.py` | `Strand` | Single SSM processing unit |
| `mesh.py` | `NeuralMesh` | Top-k routing across multiple Strands |
| `cortex.py` | `MemoryCortex` | External vector knowledge store |
| `model.py` | `NpDnaModel`, `NpDnaCore` | Full model + high-level API |
| `plasticity.py` | `PlasticityEngine` | Monitor and adapt architecture |
| `tokenizer.py` | `AtulyaTokenizer` | BPE with auto-growth |

---

## Data Flow

### Forward Pass (Inference)

```
1. input_ids: (batch, seq_len)
     │
2.   ▼ Embedding lookup
   x: (batch, seq_len, hidden_size)
     │
3.   ▼ For each Mesh Layer:
   ┌───────────────────────────────────┐
   │  Router computes scores for all   │
   │  Strands, selects top-k           │
   │                                   │
   │  Selected Strands generate their  │
   │  weights from Genome (on-demand)  │
   │                                   │
   │  Each Strand processes x using    │
   │  Causal Gated SSM (O(T) linear)   │
   │                                   │
   │  Outputs are weighted-summed      │
   │  x = x + sum(strand_outputs)      │
   └───────────────────────────────────┘
     │
4.   ▼ LayerNorm
     │
5.   ▼ Memory Cortex augmentation (optional)
   cortex_values = cortex.retrieve(x.mean(dim=1))
   x = x + project(cortex_values)
     │
6.   ▼ LM Head (tied with embedding)
   logits: (batch, seq_len, vocab_size)
```

### Training Step

```
1. Encode text → token IDs
2. input_ids = ids[:-1], labels = ids[1:]  (causal LM)
3. logits, balance_loss = model(input_ids)
4. ce_loss = CrossEntropy(logits, labels)
5. total_loss = ce_loss + 0.01 * balance_loss
6. loss.backward()
7. clip_grad_norm_(params, 1.0)
8. optimizer.step()
9. plasticity.check(step)  ← may trigger auto-scaling
```

---

## Component Deep-Dives

### 1. DNA Genome (`genome.py`)

**What:** A small network that generates weight matrices for all Strands from compact "DNA seeds".

**How:**
```python
# Each Strand has a seed vector (latent_dim,) — typically 256 floats
seed = self.seeds[strand_id]           # (256,)

# Shared encoder compresses seed to latent space
latent = self.encoder(seed)            # (256,) → (latent_dim,)

# Decoders generate low-rank factors
# For a weight of shape (hidden, state):
U = self.decoders["gate_U"](latent)    # → (hidden × rank,) → reshape (hidden, rank)
V = self.decoders["gate_V"](latent)    # → (rank × state,)  → reshape (rank, state)

# Full weight matrix reconstructed
W_gate = U @ V                         # (hidden, rank) × (rank, state) = (hidden, state)
```

**Compression math:**
- Direct: `hidden × state = 256 × 128 = 32,768` params per weight
- DNA: `seed(256) + shared_genome` → generates same `32,768` values
- Shared genome is amortized across ALL strands
- Net compression: **10-100x** depending on strand count

**Key invariant:** Different seeds → different weights. Same seed → same weights (deterministic).

### 2. Strand (`strand.py`)

**What:** A single processing unit using Causal Gated SSM. Like a neuron in a brain.

**How:**
```
For each time step t:
    gate_t    = sigmoid(x_t @ W_gate + state_{t-1} @ W_recurrent)
    update_t  = tanh(x_t @ W_state)
    state_t   = gate_t * state_{t-1} + (1 - gate_t) * update_t
    output_t  = state_t @ W_output
```

**Key properties:**
- **Causal:** Position t can only see positions 0..t-1 (no future leakage)
- **O(T) time:** Linear in sequence length (vs O(T²) for attention)
- **O(1) memory per token:** Fixed state vector, no KV cache growth
- **Weights are NOT stored:** Generated on-demand by Genome

### 3. Neural Mesh (`mesh.py`)

**What:** Sparse routing layer. Routes each token to only the top-k most relevant Strands.

**How:**
```python
# Router is a linear layer: hidden_size → num_strands
scores = self.router(x)                   # (batch, seq, num_strands)
top_k_scores, top_k_idx = scores.topk(k)  # Select top-k
weights = softmax(top_k_scores)            # Normalize

# Only compute selected Strands (rest are skipped)
for i, strand in selected_strands:
    output += weights[i] * strand(x)
```

**Balance loss:** Prevents routing collapse (all tokens going to same Strand):
```python
# Mean router probability per strand should stay close to uniform.
routing_probs = torch.softmax(scores, dim=-1).mean(dim=(0, 1))
balance_loss = num_strands * (routing_probs * routing_probs).sum()
loss = ce_loss + balance_weight * balance_loss
```

**Usage tracking:** `mesh.usage_stats` tracks how often each Strand is selected. Plasticity Engine uses this to detect dead Strands.

### 4. Memory Cortex (`cortex.py`)

**What:** External vector database for knowledge. Like long-term memory.

**How:**
```python
# Store knowledge (no training needed):
cortex.store(key_vector, topic="physics", metadata={...})

# Retrieve during inference:
values, scores = cortex.retrieve(query_vector, top_k=8)
# values: (top_k, dim) — the k most similar stored vectors
# scores: (top_k,) — cosine similarity scores
```

**Eviction:** When max_entries is reached, oldest entries are evicted (FIFO). Future: LRU or importance-based.

**Augmentation:** During forward pass, retrieved vectors are projected and added to the hidden state:
```python
cortex_out = self.cortex_proj(retrieved_values.mean(0))
hidden = hidden + cortex_out
```

### 5. Plasticity Engine (`plasticity.py`)

**What:** Self-monitoring loop that detects problems and triggers architecture changes.

**Current checks:**
- **Dead strands:** Usage < 1% of average → flagged for reinitialization
- **Overloaded strands:** Usage > 3× average → may need to split
- **Loss plateau:** No improvement for N steps → may need more capacity
- **Vocab pressure:** Token coverage > 95% → trigger tokenizer growth

**Not yet implemented (future):**
- Auto-add new Strands when all are loaded
- Auto-add new Mesh layers when loss plateaus
- Auto-prune unused Cortex entries

---

## The Math Behind DNA Compression

### Why it works

Traditional model: each layer stores its own weight matrices.
```
Layer 0: W_gate(256×128) + W_state(256×128) + W_rec(128×128) + W_out(128×256) = 114,688 params
Layer 1: Same = 114,688 params
...
N layers × 114,688 = total params
```

NP-DNA: all layers share ONE Genome. Each layer just has a different seed.
```
Genome shared network: ~500K params (fixed, regardless of layer count)
Per-layer cost: 1 seed × 256 = 256 params
N layers × 256 + 500K = total params
```

**For 100 layers:**
- Traditional: 100 × 114,688 = **11.5M params**
- NP-DNA: 100 × 256 + 500K = **525K params** (22x compression)

The key insight: weight matrices across layers are NOT independent — they share statistical structure. The Genome learns this shared structure.

---

## Training Pipeline

### Full Training Flow
```
1. Build/load dataset (JSONL: instruction → output pairs)
2. Encode all texts via tokenizer (auto-grows vocab if needed)
3. Initialize NpDnaCore from config
4. Training loop:
   a. Sample batch
   b. Forward pass → logits + balance_loss
   c. Cross-entropy loss + balance regularization
   d. Backprop + gradient clipping (max norm 1.0)
   e. Optimizer step (AdamW, weight_decay=0.01)
   f. Plasticity check every N steps
5. Save model + tokenizer + cortex
```

### Chunk Training (Topic-Specific)
```
1. Load saved model
2. Freeze ALL parameters
3. Unfreeze ONLY the target Strand's DNA seed
4. Train on topic-specific data
5. Other Strands/knowledge completely unaffected
6. Save — takes ~30 seconds on CPU
```

---

## Adding New Modalities

### Voice (Phase 2)
```python
# In atulya/core/npdna/encoder_audio.py:
class AudioEncoder(nn.Module):
    def forward(self, mel_spectrogram):
        # mel: (batch, n_mels, time) → (batch, seq_len, hidden_size)
        x = self.conv_layers(mel_spectrogram)  # Downsample time dimension
        x = self.projection(x)                  # Project to hidden_size
        return x  # Plug directly into NpDnaModel
```

### Vision (Phase 3)
```python
# In atulya/core/npdna/encoder_vision.py:
class VisionEncoder(nn.Module):
    def forward(self, image):
        # image: (batch, 3, H, W) → (batch, num_patches, hidden_size)
        patches = self.patch_embed(image)        # Split into patches
        x = self.projection(patches)             # Project to hidden_size
        return x  # Plug directly into NpDnaModel
```

**The beautiful part:** Once an encoder outputs `(batch, seq_len, hidden_size)`, the entire NP-DNA pipeline (Mesh, Genome, Cortex, Head) works unchanged.

---

## Performance Characteristics

| Metric | seed | nano | micro | small |
|---|---|---|---|---|
| Total params | 1.7M | 6.7M | 14.2M | 32.4M |
| Active params | 296K | 986K | 3.6M | 17.1M |
| Compression | 5.9x | 7.2x | 5.3x | 5.4x |
| Forward (CPU) | ~2ms | ~8ms | ~30ms | ~120ms |
| Training step | ~40ms | ~150ms | ~600ms | ~2.5s |
| Memory (train) | 50MB | 150MB | 400MB | 1.5GB |

---

## Known Issues & Gotchas

1. **Dead strands in Layer 1**: The sparse router sometimes collapses to using only 2-3 strands. The balance loss helps but isn't sufficient with tiny datasets. Fix: more diverse training data.

2. **Tokenizer byte fallback**: Characters not in the initial vocab use byte-level encoding (3-4 tokens per char). This is correct but less efficient. Fix: train BPE merges from large corpus.

3. **Cortex not used during training**: Currently, the cortex only stores/retrieves during explicit calls. Future: auto-store intermediate representations during training.

4. **Windows path issues**: The identity system searches multiple paths because `Path.resolve()` behaves differently on Windows. The `_find_identity_config()` function handles this.

5. **Unicode in CLI**: Windows cp1252 console can't render Unicode box-drawing characters. Use ASCII alternatives in CLI output.

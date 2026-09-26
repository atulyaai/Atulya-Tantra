"""NP-DNA: NeuroPlastic DNA Network.

Public API:
    from tantra.npdna import NpDnaCore, NpDnaConfig, CONFIGS

    core = NpDnaCore.from_config("seed")
    ids = core.encode("Hello, world!")
    logits, loss = core.model(torch.tensor([ids]))
    text = core.generate("Hello")
"""

# Pure-Python API — safe to import without the heavy model stack (torch).
from .classifier import NpDnaTopicClassifier, tag_text
from .config import CONFIGS, PREFERRED_CONFIG_NAMES, NpDnaConfig, auto_config
from .tokenizer import AtulyaTokenizer
from .codecs import FrozenCodecRef, FrozenCodecRegistry
from .encoder_audio import AudioFeatureEncoder

# Model stack — requires torch (the optional `local` extra). The NP-DNA model
# now lives in a separate model repo; when torch is absent (e.g. the app repo
# running only the dashboard) these degrade to None instead of crashing import.
try:
    from .cortex import CortexAutoStore, MemoryCortex
    from .genome import Genome
    from .mesh import CategoryMesh, NeuralMesh
    from .model import NpDnaCore, NpDnaModel
    from .autonomy import NpDnaAgent
    from .strand import Strand
    from .plasticity_engine import PlasticityAutoScaler, PlasticityEngine, PlasticityMetrics
except ImportError:
    CortexAutoStore = None
    MemoryCortex = None
    Genome = None
    CategoryMesh = None
    NeuralMesh = None
    NpDnaCore = None
    NpDnaModel = None
    NpDnaAgent = None
    Strand = None
    PlasticityAutoScaler = None
    PlasticityEngine = None
    PlasticityMetrics = None

__all__ = [
    "CONFIGS",
    "PREFERRED_CONFIG_NAMES",
    "NpDnaConfig",
    "auto_config",
    "Genome",
    "Strand",
    "NeuralMesh",
    "CategoryMesh",
    "MemoryCortex",
    "CortexAutoStore",
    "NpDnaModel",
    "NpDnaCore",
    "NpDnaAgent",
    "PlasticityEngine",
    "PlasticityAutoScaler",
    "PlasticityMetrics",
    "AtulyaTokenizer",
    "FrozenCodecRef",
    "FrozenCodecRegistry",
    "AudioFeatureEncoder",
    "NpDnaTopicClassifier",
    "tag_text",
]


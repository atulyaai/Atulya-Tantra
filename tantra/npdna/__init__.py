"""NP-DNA: NeuroPlastic DNA Network.

Public API:
    from tantra.npdna import NpDnaCore, NpDnaConfig, CONFIGS

    core = NpDnaCore.from_config("seed")
    ids = core.encode("Hello, world!")
    logits, loss = core.model(torch.tensor([ids]))
    text = core.generate("Hello")
"""

from .classifier import NpDnaTopicClassifier, tag_text
from .config import CONFIGS, PREFERRED_CONFIG_NAMES, NpDnaConfig, auto_config
from .cortex import CortexAutoStore, MemoryCortex
from .genome import Genome
from .mesh import CategoryMesh, NeuralMesh
from .model import NpDnaCore, NpDnaModel
from .autonomy import NpDnaAgent
from .plasticity import PlasticityAutoScaler, PlasticityEngine, PlasticityMetrics
from .strand import Strand
from .tokenizer import AtulyaTokenizer
from .codecs import FrozenCodecRef, FrozenCodecRegistry
from .encoder_audio import AudioFeatureEncoder

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


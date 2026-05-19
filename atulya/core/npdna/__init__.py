"""NP-DNA: NeuroPlastic DNA Network.

Public API:
    from atulya.core.npdna import NpDnaCore, NpDnaConfig, CONFIGS

    core = NpDnaCore.from_config("seed")
    ids = core.encode("Hello, world!")
    logits, loss = core.model(torch.tensor([ids]))
    text = core.generate("Hello")
"""

from .config import CONFIGS, NpDnaConfig, auto_config
from .cortex import MemoryCortex
from .genome import Genome
from .mesh import NeuralMesh
from .model import NpDnaCore, NpDnaModel
from .plasticity import PlasticityEngine
from .strand import Strand
from .tokenizer import AtulyaTokenizer
from .multimodal import VoiceEncoder, VisionEncoder
from .autonomy import NpDnaAgent

__all__ = [
    "CONFIGS",
    "NpDnaConfig",
    "auto_config",
    "Genome",
    "Strand",
    "NeuralMesh",
    "MemoryCortex",
    "NpDnaModel",
    "NpDnaCore",
    "PlasticityEngine",
    "AtulyaTokenizer",
    "VoiceEncoder",
    "VisionEncoder",
    "NpDnaAgent",
]

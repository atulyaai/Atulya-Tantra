"""NP-DNA: NeuroPlastic DNA Network.

Public API:
    from tantra.npdna import NpDnaCore, NpDnaConfig, CONFIGS

    core = NpDnaCore.from_config("seed")
    ids = core.encode("Hello, world!")
    logits, loss = core.model(torch.tensor([ids]))
    text = core.generate("Hello")
"""

from .config import CONFIGS, NpDnaConfig, auto_config

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


def __getattr__(name: str):
    """Lazy-load Torch-backed NP-DNA components only when a route actually uses them."""
    if name == "Genome":
        from .genome import Genome

        return Genome
    if name == "Strand":
        from .strand import Strand

        return Strand
    if name == "NeuralMesh":
        from .mesh import NeuralMesh

        return NeuralMesh
    if name == "MemoryCortex":
        from .cortex import MemoryCortex

        return MemoryCortex
    if name in {"NpDnaCore", "NpDnaModel"}:
        from .model import NpDnaCore, NpDnaModel

        return {"NpDnaCore": NpDnaCore, "NpDnaModel": NpDnaModel}[name]
    if name == "PlasticityEngine":
        from .plasticity import PlasticityEngine

        return PlasticityEngine
    if name == "AtulyaTokenizer":
        from .tokenizer import AtulyaTokenizer

        return AtulyaTokenizer
    if name in {"VoiceEncoder", "VisionEncoder"}:
        from .multimodal import VoiceEncoder, VisionEncoder

        return {"VoiceEncoder": VoiceEncoder, "VisionEncoder": VisionEncoder}[name]
    if name == "NpDnaAgent":
        from .autonomy import NpDnaAgent

        return NpDnaAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Brain — the single model entrypoint for Atulya.

Everything that needs to "think" goes through :class:`Brain`. Today it wraps the
existing :class:`~atulya.intelligence.ProviderRouter` (local Qwen GGUF first,
then free cloud helpers). Tomorrow the Tantra model can be dropped in behind the
same interface without touching callers.

Design goals:
* One place that decides *which* model answers.
* A ``think`` method that returns text + which provider served it + a rough
  confidence, so higher layers can decide whether to escalate.
* No tool logic here — the engine owns the tool loop. The brain only produces
  text (and, later, structured tool calls via grammar-constrained decoding).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from atulya.intelligence import ProviderRouter


@dataclass
class Thought:
    """Result of a single ``Brain.think`` call."""

    text: str
    provider: str = ""
    confidence: float = 0.5
    escalated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# Providers that mean "the local/offline models could not really answer".
_LOW_TRUST_PROVIDERS = {"diagnostics fallback"}

# Phrases the offline fallback emits when nothing is configured/available.
_FALLBACK_MARKERS = (
    "all neural intelligence channels are offline",
    "ran out of tool iterations",
)


def estimate_confidence(text: str, provider: str) -> float:
    """Cheap, model-free confidence heuristic in 0..1.

    Not a calibrated probability — just enough signal for the engine to decide
    "answer looks weak, try a stronger provider". Real per-token logprobs can
    replace this later when the local runtime exposes them.
    """
    if not text or not text.strip():
        return 0.0
    low = text.lower()
    if provider.strip().lower() in _LOW_TRUST_PROVIDERS:
        return 0.0
    if any(marker in low for marker in _FALLBACK_MARKERS):
        return 0.1

    score = 0.6
    # Very short answers to non-trivial asks are often evasive.
    if len(text.strip()) < 8:
        score -= 0.2
    # Explicit uncertainty language.
    if any(p in low for p in ("i'm not sure", "i am not sure", "i don't know", "i cannot", "unable to")):
        score -= 0.25
    return max(0.0, min(1.0, round(score, 3)))


class Brain:
    """The model layer. Swap the router out and everything above still works."""

    def __init__(self, router: ProviderRouter | None = None):
        self.router = router or ProviderRouter()

    async def think(
        self,
        prompt: str,
        system_prompt: str = "",
        preferred_provider: str = "",
        tools: list[dict[str, Any]] | None = None,
        min_confidence: float = 0.0,
        escalate_to: str = "",
    ) -> Thought:
        """Produce a single response.

        If the first answer's confidence falls below ``min_confidence`` and an
        ``escalate_to`` provider hint is given, retry once preferring that
        provider (e.g. a stronger free cloud model) and keep whichever is
        stronger. This is the small-brain → big-brain escalation path.
        """
        text, provider = await self.router.chat(
            prompt, system_prompt, preferred_provider=preferred_provider, tools=tools
        )
        confidence = estimate_confidence(text, provider)

        if escalate_to and confidence < min_confidence:
            alt_text, alt_provider = await self.router.chat(
                prompt, system_prompt, preferred_provider=escalate_to, tools=tools
            )
            alt_conf = estimate_confidence(alt_text, alt_provider)
            if alt_conf > confidence:
                return Thought(
                    text=alt_text,
                    provider=alt_provider,
                    confidence=alt_conf,
                    escalated=True,
                    metadata={"first_provider": provider, "first_confidence": confidence},
                )

        return Thought(text=text, provider=provider, confidence=confidence)

    async def stream(
        self,
        prompt: str,
        system_prompt: str = "",
        preferred_provider: str = "",
    ) -> AsyncIterator[tuple[str, str]]:
        """Token stream passthrough — yields (piece, provider_name)."""
        async for piece, provider in self.router.stream(
            prompt, system_prompt, preferred_provider=preferred_provider
        ):
            yield piece, provider

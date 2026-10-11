import asyncio
import json
import sys

import httpx

from tools.plugins.brain import AutomaticProvider, Message, OpenAICompatibleProvider, ProviderError

if sys.platform == "win32":
    # Windows' default Proactor loop uses a local socket pair, which is blocked
    # in restricted test sandboxes even when a test performs no network I/O.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


class FakeProvider:
    def __init__(self, name: str, reply: str = "", error: ProviderError | None = None) -> None:
        self.name = name
        self.model = f"{name}-model"
        self.reply = reply
        self.error = error
        self.calls = 0

    async def complete(self, messages):
        self.calls += 1
        if self.error:
            raise self.error
        return self.reply


def test_auto_provider_skips_rejected_provider_after_first_attempt() -> None:
    rejected = FakeProvider("rejected", error=ProviderError("unauthorized", status_code=401))
    working = FakeProvider("working", reply="Hello")
    provider = AutomaticProvider([rejected, working])
    messages = [Message(role="user", content="Hi")]

    assert asyncio.run(provider.complete(messages)) == "Hello"
    assert asyncio.run(provider.complete(messages)) == "Hello"
    assert rejected.calls == 1
    assert working.calls == 2
    assert provider.name == "working"


def test_auto_provider_starts_local_only_after_cloud_candidates_fail() -> None:
    cloud = FakeProvider("cloud", error=ProviderError("forbidden", status_code=403))
    local = FakeProvider("local", reply="Local answer")
    lifecycle: list[str] = []
    provider = AutomaticProvider(
        [cloud],
        local_provider=local,
        start_local=lambda: lifecycle.append("start"),
        stop_local=lambda: lifecycle.append("stop"),
    )

    assert asyncio.run(provider.complete([Message(role="user", content="Hi")])) == "Local answer"
    assert lifecycle == ["start"]
    assert provider.name == "local"
    provider.close()
    assert lifecycle == ["start", "stop"]


def test_auto_provider_hedges_only_two_candidates_and_returns_first_success() -> None:
    class DelayedProvider(FakeProvider):
        def __init__(self, name: str, delay: float, reply: str) -> None:
            super().__init__(name, reply)
            self.delay = delay

        async def complete(self, messages):
            self.calls += 1
            await asyncio.sleep(self.delay)
            return self.reply

    preferred = DelayedProvider("preferred", 0.2, "slow")
    faster_fallback = DelayedProvider("fallback", 0.01, "fast")
    provider = AutomaticProvider([preferred, faster_fallback], hedge_delay_seconds=0.02)
    assert asyncio.run(provider.complete([Message(role="user", content="Hi")])) == "fast"
    assert preferred.calls == faster_fallback.calls == 1
    assert provider.active_provider is faster_fallback


def test_auto_provider_hedges_stream_initial_token_without_replaying_loser() -> None:
    class StreamProvider(FakeProvider):
        def __init__(self, name: str, delay: float, token: str) -> None:
            super().__init__(name)
            self.delay = delay
            self.token = token
            self.cancelled = False

        async def stream(self, _messages):
            try:
                await asyncio.sleep(self.delay)
                yield self.token
                yield " tail"
            except asyncio.CancelledError:
                self.cancelled = True
                raise

    preferred = StreamProvider("preferred", 0.2, "slow")
    fallback = StreamProvider("fallback", 0.01, "fast")
    provider = AutomaticProvider([preferred, fallback], hedge_delay_seconds=0.02)
    chunks = asyncio.run(_collect(provider.stream([Message(role="user", content="Hi")])))
    assert "".join(chunks) == "fast tail"
    assert provider.active_provider is fallback
    assert preferred.cancelled


async def _collect(stream) -> list[str]:
    return [chunk async for chunk in stream]


def test_provider_402_and_429_failures_are_cooled_down() -> None:
    provider = AutomaticProvider([])
    candidate = FakeProvider("candidate")
    provider._record_failure(candidate, 402)
    assert not provider._available(candidate)
    provider._cooldowns.clear()
    provider._record_failure(candidate, 429)
    assert not provider._available(candidate)


def test_auto_provider_enforces_overall_cloud_attempt_budget() -> None:
    class SlowProvider(FakeProvider):
        async def complete(self, _messages):
            await asyncio.sleep(1)
            return "late"

    provider = AutomaticProvider(
        [SlowProvider("slow")], hedge_delay_seconds=0, provider_budget_seconds=0.03
    )
    try:
        asyncio.run(provider.complete([Message(role="user", content="Hi")]))
    except ProviderError as exc:
        assert "available" in str(exc).lower()
    else:
        raise AssertionError("Provider call should stop at its overall cloud budget")


def test_openai_compatible_stream_parses_sse_and_reuses_injected_client() -> None:
    async def exercise() -> None:
        seen_payloads = []

        async def handle(request: httpx.Request) -> httpx.Response:
            seen_payloads.append(json.loads(request.content))
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=(
                    b'data: {"choices":[{"delta":{"content":"Hello "}}]}\n\n'
                    b'data: {"choices":[{"delta":{"content":"there."}}]}\n\n'
                    b'data: [DONE]\n\n'
                ),
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            provider = OpenAICompatibleProvider(
                base_url="https://provider.test/v1", model="test-model", client=client
            )
            chunks = [chunk async for chunk in provider.stream([Message(role="user", content="Hi")])]
            assert provider._client is client
            assert chunks == ["Hello ", "there."]
            assert seen_payloads[0]["stream"] is True

    asyncio.run(exercise())

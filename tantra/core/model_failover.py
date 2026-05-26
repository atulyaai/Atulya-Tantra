"""Model failover with health checks, live switching, and automatic fallback.

Supports OpenCode as primary provider with circuit breaker pattern.
"""
from __future__ import annotations

import asyncio
import subprocess
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)


class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ErrorType(Enum):
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    AUTH = "auth"
    SERVER = "server"
    NETWORK = "network"
    UNKNOWN = "unknown"


@dataclass
class ProviderHealth:
    status: ProviderStatus = ProviderStatus.UNKNOWN
    latency_ms: float = 0.0
    last_check: float = 0.0
    consecutive_failures: int = 0
    total_requests: int = 0
    total_failures: int = 0
    last_error: str | None = None
    last_success: float = 0.0


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_requests: int = 3
    timeout: float = 30.0


@dataclass
class CircuitBreaker:
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)
    half_open_requests: int = 0

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_requests -= 1
            if self.half_open_requests <= 0:
                self._transition(CircuitState.CLOSED)
        self.failure_count = 0

    def record_failure(self, threshold: int = 5):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.OPEN)
        elif self.failure_count >= threshold:
            self._transition(CircuitState.OPEN)

    def can_execute(self, recovery_timeout: float = 30.0, half_open_max: int = 3) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
                self.half_open_requests = half_open_max
                return True
            return False
        return self.half_open_requests > 0

    def _transition(self, new_state: CircuitState):
        self.state = new_state
        self.last_state_change = time.time()


@dataclass
class ProviderConfig:
    name: str
    priority: int = 0
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    command: str = ""
    timeout: float = 30.0
    max_retries: int = 3
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelProvider(ABC):
    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        pass

    @abstractmethod
    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        pass

    @abstractmethod
    async def streaming_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        pass

    @abstractmethod
    def classify_error(self, error: Exception) -> ErrorType:
        pass


class OpenCodeProvider(ModelProvider):
    """OpenCode CLI-based model provider.

    Uses `opencode run` or `opencode chat` to interact with the model.
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._available: bool | None = None

    def _check_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            cmd = self.config.command or "opencode"
            result = subprocess.run(
                [cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            self._available = result.returncode == 0
            return self._available
        except (FileNotFoundError, subprocess.TimeoutExpired):
            self._available = False
            return False

    async def health_check(self) -> ProviderHealth:
        start = time.time()
        try:
            available = await asyncio.to_thread(self._check_available)
            if available:
                return ProviderHealth(
                    status=ProviderStatus.HEALTHY,
                    latency_ms=(time.time() - start) * 1000,
                    last_check=time.time(),
                    last_success=time.time(),
                )
            return ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                last_check=time.time(),
                last_error="opencode not available",
            )
        except Exception as e:
            return ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                last_check=time.time(),
                last_error=str(e),
            )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any]:
        prompt = "\n".join(m.get("content", "") for m in messages)
        cmd = self.config.command or "opencode"
        args = [cmd, "run", "--temperature", str(temperature)]
        if max_tokens:
            args.extend(["--max-tokens", str(max_tokens)])
        args.append(prompt)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"OpenCode failed: {stderr.decode().strip()}")

        content = stdout.decode().strip()
        return {
            "content": content,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "provider": "opencode",
            "model": self.config.model or "opencode-default",
        }

    async def streaming_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        prompt = "\n".join(m.get("content", "") for m in messages)
        cmd = self.config.command or "opencode"
        args = [cmd, "run", "--stream", "--temperature", str(temperature)]
        if max_tokens:
            args.extend(["--max-tokens", str(max_tokens)])
        args.append(prompt)

        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stderr_task = asyncio.create_task(proc.stderr.read()) if proc.stderr else None
        try:
            if proc.stdout:
                while True:
                    try:
                        line = await asyncio.wait_for(
                            proc.stdout.readline(),
                            timeout=self.config.timeout,
                        )
                    except asyncio.TimeoutError as exc:
                        raise RuntimeError(
                            f"Streaming timed out after {self.config.timeout}s"
                        ) from exc
                    if not line:
                        break
                    decoded = line.decode().strip()
                    if decoded:
                        yield decoded

            try:
                await asyncio.wait_for(proc.wait(), timeout=self.config.timeout)
            except asyncio.TimeoutError as exc:
                raise RuntimeError(
                    f"Streaming timed out after {self.config.timeout}s"
                ) from exc

            stderr = (await stderr_task).decode().strip() if stderr_task else ""
            if proc.returncode != 0:
                detail = f": {stderr}" if stderr else ""
                raise RuntimeError(f"OpenCode streaming failed (exit {proc.returncode}){detail}")
        finally:
            if proc.returncode is None:
                proc.kill()
                await proc.wait()
            if stderr_task and not stderr_task.done():
                stderr_task.cancel()

    def classify_error(self, error: Exception) -> ErrorType:
        error_str = str(error).lower()
        if "timeout" in error_str:
            return ErrorType.TIMEOUT
        if "permission" in error_str or "not found" in error_str:
            return ErrorType.AUTH
        if "connection" in error_str:
            return ErrorType.NETWORK
        return ErrorType.SERVER


class ModelFailover:
    def __init__(self, providers: list[tuple[ModelProvider, ProviderConfig]]):
        self._providers: dict[str, tuple[ModelProvider, ProviderConfig]] = {
            cfg.name: (provider, cfg) for provider, cfg in providers
        }
        self._health: dict[str, ProviderHealth] = {
            name: ProviderHealth() for name in self._providers
        }
        self._circuit_breakers: dict[str, CircuitBreaker] = {
            name: CircuitBreaker() for name in self._providers
        }
        self._health_check_interval: float = 60.0
        self._health_check_task: asyncio.Task | None = None
        self._running = False
        self._current_provider: str | None = None
        self._failover_log: list[dict[str, Any]] = []

    async def start(self):
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_loop())
        await self._check_all_health()
        await self._select_best_provider()

    async def stop(self):
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass

    async def _health_loop(self):
        while self._running:
            try:
                await self._check_all_health()
                await self._select_best_provider()
            except Exception as e:
                logger.error("Health check loop error: %s", e)
            await asyncio.sleep(self._health_check_interval)

    async def _check_all_health(self):
        tasks = []
        for name, (provider, cfg) in self._providers.items():
            tasks.append(self._check_provider_health(name, provider, cfg))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for name, result in zip(self._providers.keys(), results):
            if isinstance(result, Exception):
                self._health[name].status = ProviderStatus.UNHEALTHY
                self._health[name].last_error = str(result)
            else:
                self._health[name] = result

    async def _check_provider_health(
        self, name: str, provider: ModelProvider, cfg: ProviderConfig
    ) -> ProviderHealth:
        start = time.time()
        try:
            health = await asyncio.wait_for(
                provider.health_check(),
                timeout=cfg.circuit_breaker.timeout
            )
            health.last_check = time.time()
            health.latency_ms = (time.time() - start) * 1000
            if health.status == ProviderStatus.HEALTHY:
                health.consecutive_failures = 0
                health.last_success = time.time()
        except asyncio.TimeoutError:
            health = ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                latency_ms=(time.time() - start) * 1000,
                last_check=time.time(),
                consecutive_failures=self._health[name].consecutive_failures + 1,
                last_error="timeout"
            )
        except Exception as e:
            health = ProviderHealth(
                status=ProviderStatus.UNHEALTHY,
                latency_ms=(time.time() - start) * 1000,
                last_check=time.time(),
                consecutive_failures=self._health[name].consecutive_failures + 1,
                last_error=str(e)
            )
        return health

    async def _select_best_provider(self):
        candidates = []
        for name, (_, cfg) in self._providers.items():
            health = self._health[name]
            cb = self._circuit_breakers[name]
            if cb.can_execute(
                cfg.circuit_breaker.recovery_timeout,
                cfg.circuit_breaker.half_open_max_requests
            ):
                if health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED):
                    candidates.append((cfg.priority, name, health.latency_ms))

        if not candidates:
            candidates = [
                (cfg.priority, name, 0)
                for name, (_, cfg) in self._providers.items()
            ]

        if candidates:
            candidates.sort(key=lambda x: (x[0], x[2]))
            best = candidates[0][1]
            if self._current_provider != best:
                logger.info("Switching provider: %s -> %s", self._current_provider, best)
                self._current_provider = best

    @property
    def current_provider(self) -> str | None:
        return self._current_provider

    async def execute(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
        force_provider: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        if force_provider:
            if force_provider not in self._providers:
                raise ValueError(f"Unknown provider: {force_provider}")
            return await self._try_provider(
                force_provider, messages, temperature, max_tokens, stream, **kwargs
            )

        ordered = sorted(
            self._providers.keys(),
            key=lambda n: self._providers[n][1].priority
        )

        last_error = None
        for name in ordered:
            cb = self._circuit_breakers[name]
            cfg = self._providers[name][1]
            if not cb.can_execute(
                cfg.circuit_breaker.recovery_timeout,
                cfg.circuit_breaker.half_open_max_requests
            ):
                continue

            try:
                result = await self._try_provider(
                    name, messages, temperature, max_tokens, stream, **kwargs
                )
                cb.record_success()
                self._health[name].consecutive_failures = 0
                self._health[name].last_success = time.time()
                return result
            except Exception as e:
                last_error = e
                error_type = self._providers[name][0].classify_error(e)
                cb.record_failure(cfg.circuit_breaker.failure_threshold)
                self._health[name].consecutive_failures += 1
                self._health[name].total_failures += 1
                self._health[name].last_error = str(e)
                self._failover_log.append({
                    "timestamp": time.time(),
                    "provider": name,
                    "error": str(e),
                    "error_type": error_type.value,
                })
                logger.warning("Provider %s failed (%s): %s", name, error_type.value, e)
                if error_type == ErrorType.AUTH:
                    break

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def _try_provider(
        self,
        name: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int | None,
        stream: bool,
        **kwargs: Any,
    ) -> dict[str, Any] | AsyncIterator[str]:
        provider, cfg = self._providers[name]
        self._health[name].total_requests += 1
        start = time.time()
        try:
            if stream:
                return await provider.streaming_completion(
                    messages, temperature, max_tokens, **kwargs
                )
            else:
                return await asyncio.wait_for(
                    provider.chat_completion(
                        messages, temperature, max_tokens, stream=False, **kwargs
                    ),
                    timeout=cfg.timeout
                )
        finally:
            latency = (time.time() - start) * 1000
            self._health[name].latency_ms = latency

    def get_status(self) -> dict[str, Any]:
        return {
            "current_provider": self._current_provider,
            "providers": {
                name: {
                    "health": {
                        "status": health.status.value,
                        "latency_ms": round(health.latency_ms, 2),
                        "consecutive_failures": health.consecutive_failures,
                        "total_requests": health.total_requests,
                        "total_failures": health.total_failures,
                        "last_error": health.last_error,
                    },
                    "circuit_breaker": {
                        "state": cb.state.value,
                        "failure_count": cb.failure_count,
                    },
                    "config": {
                        "priority": cfg.priority,
                        "model": cfg.model,
                    }
                }
                for name, (_, cfg) in self._providers.items()
                for health in [self._health[name]]
                for cb in [self._circuit_breakers[name]]
            },
            "failover_log": self._failover_log[-20:],
        }

    def switch_provider(self, name: str):
        if name not in self._providers:
            raise ValueError(f"Unknown provider: {name}")
        self._current_provider = name
        logger.info(f"Manual provider switch: {name}")


def create_failover_from_config(config: dict[str, Any]) -> ModelFailover:
    providers = []

    opencode_cfg = ProviderConfig(
        name="opencode",
        priority=0,
        model=config.get("opencode_model", "default"),
        command=config.get("opencode_command", "opencode"),
        cost_per_1k_input=0.0,
        cost_per_1k_output=0.0,
    )
    providers.append((OpenCodeProvider(opencode_cfg), opencode_cfg))

    if config.get("openai_api_key"):
        openai_cfg = ProviderConfig(
            name="openai",
            priority=10,
            model=config.get("openai_model", "gpt-4o-mini"),
            api_key=config["openai_api_key"],
            base_url=config.get("openai_base_url", ""),
            cost_per_1k_input=config.get("openai_input_cost", 0.15),
            cost_per_1k_output=config.get("openai_output_cost", 0.60),
        )
        from .model_providers import OpenAICompatibleProvider
        providers.append((OpenAICompatibleProvider(openai_cfg), openai_cfg))

    return ModelFailover(providers)

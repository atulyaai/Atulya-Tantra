from abc import ABC, abstractmethod
from typing import AsyncGenerator, Union
from atulya_core.schema.models import TantraRequest, TantraResponse

class BaseTantraAdapter(ABC):
    @abstractmethod
    async def generate(self, request: TantraRequest) -> TantraResponse:
        """Single completion request"""
        pass

    @abstractmethod
    async def stream(self, request: TantraRequest) -> AsyncGenerator[TantraResponse, None]:
        """Streaming completion request"""
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """Check if provider is available"""
        pass

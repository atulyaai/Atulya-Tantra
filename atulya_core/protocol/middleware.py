from abc import ABC, abstractmethod
from typing import List, Callable, Any
from atulya_core.schema.models import TantraRequest, TantraResponse

class TantraMiddleware(ABC):
    @abstractmethod
    async def __call__(self, request: TantraRequest, call_next: Callable) -> TantraResponse:
        pass

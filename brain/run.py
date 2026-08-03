"""Run the Atulya production-v1 runtime."""

import uvicorn

from atulya_runtime.api import create_app
from atulya_runtime.config import Settings


settings = Settings.from_environment()
app = create_app(settings)

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements_server.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_server.txt

# Copy application
COPY server/ ./server/
COPY config/ ./config/

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "server/main.py"]


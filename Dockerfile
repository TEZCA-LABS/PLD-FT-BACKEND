# Stage 1: Builder
FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for building python packages
# extended list for cryptography, asyncpg, etc.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies to a temporary location
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN addgroup --system appgroup && adduser --system --group appgroup appuser

# Copy installed python dependencies from the builder stage
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Set ownership of the application directory
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

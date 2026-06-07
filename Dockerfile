FROM python:3.12-slim

# Don't write .pyc files; flush stdout/stderr straight to the logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached across code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY . .

# Run as a non-root user
RUN useradd --create-home --uid 1000 appuser
USER appuser

CMD ["python", "main.py"]

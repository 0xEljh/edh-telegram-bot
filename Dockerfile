# Start from a lightweight Python base image
FROM python:3.11-slim

# Set environment variables to avoid interactive prompts and ensure poetry works properly
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=false

# Install system dependencies required for building packages and running poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 - && \
    ln -s /root/.local/bin/poetry /usr/local/bin/poetry


# Copy application code into the container
WORKDIR /app
COPY . /app

# Install Python dependencies
RUN poetry install --no-dev


# Command to run the application (adjust as needed)
CMD ["python", "main.py"]
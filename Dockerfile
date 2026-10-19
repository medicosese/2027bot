FROM python:3.11-slim

WORKDIR /app

# Prevent Python from writing pyc files and buffer stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy bot application
COPY . .

# Expose HTTP port for health checks / keep-alive pinging
EXPOSE 8080

# Run cloud runner
CMD ["python", "server.py"]

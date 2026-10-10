FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install system dependencies if required for psycopg2 and building packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend code, static frontend assets, and configurations
COPY backend/ ./backend/
COPY js/ ./js/
COPY css/ ./css/
COPY icons/ ./icons/
COPY utils/ ./utils/
COPY index.html ./index.html
COPY manifest.webmanifest ./manifest.webmanifest
COPY sw.js ./sw.js

# Expose the server port
EXPOSE 8000

# Start Uvicorn pointing to the main FastAPI app
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

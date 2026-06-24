FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching: deps rarely change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY api/ ./api/
COPY scripts/ ./scripts/
COPY frontend/ ./frontend/
COPY data/raw/ ./data/raw/

# Seed the database at BUILD time so the image is self-contained.
# This creates data/emissions.db inside the image.
RUN python scripts/seed.py

# HF Spaces expects the app on port 7860
EXPOSE 7860

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]
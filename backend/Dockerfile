FROM python:3.11-slim

# Dependências de sistema para librosa/soundfile/matplotlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia requirements primeiro (melhor caching de layer)
COPY requirements.txt .
# --timeout=300 + retries resolve ReadTimeoutError em redes lentas
# (librosa+matplotlib+numpy pull ~500MB de wheels)
RUN pip install --no-cache-dir --timeout=300 --retries=5 -r requirements.txt

# Copia código
COPY . .

# Non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

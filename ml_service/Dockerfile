FROM python:3.12-slim

# System deps for librosa / soundfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /ml_service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download YAMNet on build (optional, speeds up first request)
# RUN python -c "import tensorflow_hub as hub; hub.load('https://tfhub.dev/google/yamnet/1')"

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]

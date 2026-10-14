FROM python:3.11-slim

WORKDIR /app

# Gerekli sistem paketleri
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Bağımlılıkları yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodlarını kopyala
COPY server.py .

# Depolama klasörü oluştur
RUN mkdir -p BulutDepolama

ENV BULUT_HOST="0.0.0.0"
ENV BULUT_PORT="8000"
ENV BULUT_SIFRE="esatesat16."

EXPOSE 8000

CMD ["python", "server.py"]

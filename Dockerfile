FROM python:3.11-slim

LABEL maintainer="Lucas Ramon <lucasramons@gmail.com>"
LABEL description="Container do Pipeline ETL/ELT Climático com Pandas, SQLAlchemy e Prefect"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

# Instala dependências do sistema necessárias para compilação/conexão PostgreSQL
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.main"]

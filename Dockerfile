# Imagem base oficial do Python
FROM python:3.9-slim

# Variáveis de ambiente para evitar problemas com prompts e garantir encoding
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8

# Diretório de trabalho
WORKDIR /app

# Instalar dependências básicas de sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de dependências primeiro para aproveitar cache do Docker
COPY requirements.txt .

# Instalar dependências Python
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copiar todo o projeto para dentro do container
COPY ./app .

# Garantir que a pasta de logs exista
RUN mkdir -p logs

# Definir o comando padrão
CMD ["python", "rise_fall_deriv.py"]
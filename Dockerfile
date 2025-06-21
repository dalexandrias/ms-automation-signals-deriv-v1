# Imagem base
FROM python:3.9-slim

# Variáveis de ambiente para evitar problemas com prompts
ENV PYTHONUNBUFFERED=1

# Instalar dependências básicas de sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libffi-dev \
    libssl-dev \
    && apt-get clean

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o script
COPY rise_fall_deriv.py .
COPY repository.py .
COPY log_config.py .

# Criar pasta de logs
RUN mkdir -p logs

# Comando para rodar o script
CMD ["python", "rise_fall_deriv.py"]

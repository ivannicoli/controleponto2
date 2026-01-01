# Use uma imagem Python oficial estável
FROM python:3.9-slim

# Instala dependências do sistema (Tesseract OCR e bibliotecas para o OpenCV)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-por \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho
WORKDIR /app

# Copia os arquivos de requisitos primeiro para aproveitar o cache do Docker
COPY requirements.txt .

# Instala as dependências do Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Cria a pasta de uploads se não existir
RUN mkdir -p uploads

# Expõe a porta que o Flask vai rodar
EXPOSE 5001

# Comando para rodar a aplicação (bind no 0.0.0.0 para acesso externo ao container)
CMD ["python", "app.py"]

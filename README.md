# Extrator de Ponto Inteligente

Este projeto é uma aplicação web local em Python que permite extrair horários de fotos de folhas de ponto usando OCR (Tesseract) e editá-los em uma interface moderna.

## Pré-requisitos

1. **Python 3** (Já instalado no Mac)
2. **Tesseract OCR** (Necessário para leitura das imagens).
   *O sistema detectou que você já tem o tesseract instalado!*

## Instalação (Recomendado usar venv)

Para evitar conflitos, rode os seguintes comandos no terminal desta pasta:

```bash
# 1. Crie um ambiente virtual
python3 -m venv venv

# 2. Ative o ambiente
source venv/bin/activate

# 3. Instale as dependências
pip install -r requirements.txt
```

## Como Usar

1. Com o ambiente ativado, inicie o servidor:
   ```bash
   python app.py
   ```

2. Acesse no navegador:
   http://127.0.0.1:5001

3. Arraste a imagem do seu ponto para a área indicada. A IA tentará ler os dias e horários automaticamente.

## Estrutura

- `app.py`: Lógica do servidor e processamento de imagem (OCR).
- `templates/index.html`: Interface moderna com TailwindCSS e Alpine.js.

FROM python:3.11-slim

# Install system dependencies for PyMuPDF (libgl1) and Camelot (ghostscript)
RUN apt-get update && apt-get install -y \
    libgl1 \
    ghostscript \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Pre-cache NLTK data and heavy SentenceTransformer models at build-time
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')"
RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('BAAI/bge-reranker-base')"

COPY . .

EXPOSE 8501
EXPOSE 8000

CMD ["streamlit", "run", "app/main.py", "--server.port=8501", "--server.address=0.0.0.0"]

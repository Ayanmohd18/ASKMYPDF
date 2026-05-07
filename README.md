# AskMyPDF — Enterprise RAG Document Intelligence Platform

AskMyPDF is a production-grade Retrieval-Augmented Generation (RAG) system that transforms static PDF document repositories into conversational knowledge bases.

## Phase 1 Setup Instructions

1. Clone and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure the environment:
   ```bash
   cp .env.example .env
   # Fill in your API keys in the .env file
   ```

3. Run the ingestion test suite to verify the setup:
   ```bash
   pytest tests/test_ingestion.py -v
   ```

### Expected Output
When the tests complete successfully, you should see output similar to this:
```text
============================= test session starts ==============================
...
tests/test_ingestion.py::test_extract_pages PASSED                       [ 25%]
tests/test_ingestion.py::test_semantic_chunk_fields PASSED               [ 50%]
tests/test_ingestion.py::test_chunk_token_limit PASSED                   [ 75%]
tests/test_ingestion.py::test_ingest_multiple PASSED                     [100%]

============================== 4 passed in 2.34s ===============================
```

## Running the App

Local (no Docker):
  ```bash
  cp .env.example .env
  # Fill in your GEMINI_API_KEY or other backend keys
  pip install -r requirements.txt
  streamlit run app/main.py
  ```

Expected UI behavior:
  - Upload one or more PDFs using the sidebar
  - Click "Ingest Documents" and wait for completion
  - Type a question in the chat input
  - Answer appears with source cards showing document name, page, and passage

Offline mode with Ollama:
  1. Install Ollama: https://ollama.ai
  2. `ollama pull mistral`
  3. `ollama serve` (keep running in background)
  4. In `.env`: set `LLM_BACKEND=ollama`
  5. `streamlit run app/main.py`

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import os
from pathlib import Path
from dotenv import load_dotenv

from app.retriever import retrieve
from app.generator import generate, decompose_query
from app.memory import ConversationMemory
from app import vector_store

load_dotenv()

app = FastAPI(
    title="AskMyPDF API",
    description="Enterprise RAG Document Intelligence Platform REST API",
    version="2.0"
)

@app.on_event("startup")
def startup_event():
    """Initializes the vector store on backend startup."""
    index_dir = Path(os.getenv("INDEX_DIR", "data/indexes"))
    index_dir.mkdir(parents=True, exist_ok=True)
    vector_store.initialize(index_dir)

class QueryRequest(BaseModel):
    query: str
    backend: Optional[str] = "gemini"
    use_hyde: Optional[bool] = False
    use_decomposition: Optional[bool] = False

class SourceCitation(BaseModel):
    doc_name: str
    page_number: int
    text: str
    reranker_score: float

class QueryResponse(BaseModel):
    answer: str
    citations: List[SourceCitation]

@app.post("/query", response_model=QueryResponse)
def query_documents(request: QueryRequest):
    """
    Main endpoint for enterprise portal integrations to query the RAG system.
    """
    if vector_store.get_chunk_count() == 0:
        raise HTTPException(status_code=400, detail="No documents indexed. Please ingest documents first.")
        
    try:
        reranker_top_k = int(os.getenv("RERANKER_TOP_K", 5))
        
        # 1. Handle Retrieval (with optional decomposition)
        all_results = []
        if request.use_decomposition:
            sub_queries = decompose_query(request.query, request.backend)
            seen_chunk_ids = set()
            for sq in sub_queries:
                sq_results = retrieve(sq, reranker_top_k=reranker_top_k, use_hyde=request.use_hyde)
                for rc in sq_results:
                    if rc.chunk.chunk_id not in seen_chunk_ids:
                        seen_chunk_ids.add(rc.chunk.chunk_id)
                        all_results.append(rc)
            all_results.sort(key=lambda x: x.reranker_score, reverse=True)
            results = all_results[:10]
        else:
            results = retrieve(request.query, reranker_top_k=reranker_top_k, use_hyde=request.use_hyde)
            
        # 2. Generation
        # (Stateless request: using empty memory. Client must pass history if multi-turn is needed in future)
        memory = ConversationMemory()
        answer = generate(request.query, results, memory, backend=request.backend)
        
        # 3. Format Citations
        citations = []
        for rc in results:
            citations.append(SourceCitation(
                doc_name=rc.chunk.doc_name,
                page_number=rc.chunk.page_number,
                text=rc.chunk.text,
                reranker_score=rc.reranker_score
            ))
            
        return QueryResponse(answer=answer, citations=citations)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "documents_indexed": vector_store.get_all_doc_names(),
        "total_chunks": vector_store.get_chunk_count()
    }

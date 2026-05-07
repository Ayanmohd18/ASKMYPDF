"""
Hybrid Retrieval and Reranking Module.
"""
import os
from dataclasses import dataclass
from sentence_transformers import CrossEncoder
from dotenv import load_dotenv

from app import embedder
from app import vector_store
from app.ingestion import Chunk

load_dotenv()

@dataclass
class RetrievedChunk:
    chunk: Chunk
    faiss_score: float
    bm25_score: float
    rrf_score: float
    reranker_score: float

_reranker = None

def get_reranker() -> CrossEncoder:
    """Returns the singleton reranker model, loading it if necessary."""
    global _reranker
    if _reranker is None:
        print("Loading reranker model...")
        _reranker = CrossEncoder("BAAI/bge-reranker-base")
    return _reranker

def reciprocal_rank_fusion(
    semantic_results: list[tuple[Chunk, float]],
    bm25_results: list[tuple[Chunk, float]],
    k: int = 60
) -> list[RetrievedChunk]:
    """
    Merges results from semantic search and BM25 using Reciprocal Rank Fusion.
    """
    # 1. Build rank maps: chunk_id -> rank (1-indexed)
    semantic_ranks = {}
    semantic_scores = {}
    for rank, (chunk, score) in enumerate(semantic_results, start=1):
        semantic_ranks[chunk.chunk_id] = rank
        semantic_scores[chunk.chunk_id] = score
        
    bm25_ranks = {}
    bm25_scores = {}
    for rank, (chunk, score) in enumerate(bm25_results, start=1):
        bm25_ranks[chunk.chunk_id] = rank
        bm25_scores[chunk.chunk_id] = score
        
    # 2. Collect all unique chunks
    unique_chunks = {}
    for chunk, _ in semantic_results:
        unique_chunks[chunk.chunk_id] = chunk
    for chunk, _ in bm25_results:
        unique_chunks[chunk.chunk_id] = chunk
        
    # 3. Compute RRF score for each unique chunk
    retrieved_chunks = []
    for chunk_id, chunk in unique_chunks.items():
        s_rank = semantic_ranks.get(chunk_id, 1001)
        b_rank = bm25_ranks.get(chunk_id, 1001)
        
        rrf = 1.0 / (k + s_rank) + 1.0 / (k + b_rank)
        
        # 4. Build RetrievedChunk
        faiss_score = semantic_scores.get(chunk_id, 0.0)
        bm25_score = bm25_scores.get(chunk_id, 0.0)
        
        retrieved_chunks.append(RetrievedChunk(
            chunk=chunk,
            faiss_score=faiss_score,
            bm25_score=bm25_score,
            rrf_score=rrf,
            reranker_score=0.0
        ))
        
    # 5. Sort by rrf_score descending
    retrieved_chunks.sort(key=lambda x: x.rrf_score, reverse=True)
    
    # 6. Return full merged list
    return retrieved_chunks

def rerank(
    query: str,
    candidates: list[RetrievedChunk],
    top_k: int = 5
) -> list[RetrievedChunk]:
    """
    Reranks a list of candidate chunks using a cross-encoder model.
    """
    if not candidates:
        return []
        
    pairs = [[query, c.chunk.text] for c in candidates]
    
    scores = get_reranker().predict(pairs)
    
    for c, score in zip(candidates, scores):
        c.reranker_score = float(score)
        
    candidates.sort(key=lambda x: x.reranker_score, reverse=True)
    
    return candidates[:top_k]

def retrieve(
    query: str,
    semantic_top_k: int = 20,
    bm25_top_k: int = 20,
    reranker_top_k: int = 5,
    rrf_k: int = 60,
    use_hyde: bool = False
) -> list[RetrievedChunk]:
    """
    Full hybrid retrieval pipeline:
    1. Semantic search
    2. BM25 search
    3. Reciprocal Rank Fusion
    4. Cross-encoder reranking
    """
    if vector_store.get_chunk_count() == 0:
        raise ValueError("No documents indexed. Please ingest PDFs first.")
        
    # Read overrides from env vars if present
    env_semantic_top_k = int(os.getenv("SEMANTIC_TOP_K") or semantic_top_k)
    env_bm25_top_k = int(os.getenv("BM25_TOP_K") or bm25_top_k)
    env_reranker_top_k = int(os.getenv("RERANKER_TOP_K") or reranker_top_k)
    env_rrf_k = int(os.getenv("RRF_K") or rrf_k)
    
    # Check env var for HyDE if not explicitly passed
    if not use_hyde and os.getenv("USE_HYDE", "").lower() == "true":
        use_hyde = True
        
    semantic_query = query
    if use_hyde:
        try:
            from app.generator import generate_hyde_document
            import streamlit as st
            # Try to get the selected backend if in Streamlit, otherwise let generator use default
            backend = None
            try:
                if "backend" in st.session_state:
                    backend = st.session_state.backend
            except Exception:
                pass
            hypothetical_doc = generate_hyde_document(query, backend)
            semantic_query = f"{query} {hypothetical_doc}"
        except Exception as e:
            print(f"HyDE generation failed: {e}. Falling back to raw query.")
            
    # 1. Embed query (uses semantic_query for HyDE if enabled)
    query_vec = embedder.embed_query(semantic_query)
    
    # 2. Semantic Search
    semantic_results = vector_store.search_semantic(query_vec, env_semantic_top_k)
    
    # 3. BM25 Search
    bm25_results = vector_store.search_bm25(query, env_bm25_top_k)
    
    # 4. RRF merge
    rrf_results = reciprocal_rank_fusion(semantic_results, bm25_results, env_rrf_k)
    
    # 4.5 Specialized Table Boosting for numerical/comparative queries
    import re
    is_numerical_or_comparative = bool(
        re.search(r'\d', query) or 
        re.search(r'\b(compare|difference|vs|greater|less|how many|percentage|ratio|table)\b', query.lower())
    )
    
    if is_numerical_or_comparative:
        for rc in rrf_results:
            if "[TABLE]" in rc.chunk.text:
                rc.rrf_score *= 1.5  # Give a 50% boost to RRF score
                
        # Re-sort after boosting
        rrf_results.sort(key=lambda x: x.rrf_score, reverse=True)
    
    # 5. Take top-10 for reranking (hardcoded to 10 in spec)
    top10_candidates = rrf_results[:10]
    
    # 6. Rerank top 10
    final_results = rerank(query, top10_candidates, env_reranker_top_k)
    
    # 7. Return final list
    return final_results

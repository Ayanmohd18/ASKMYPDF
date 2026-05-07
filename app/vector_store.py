"""
Vector Store module managing dual FAISS and BM25 indexes.
"""
import faiss
import numpy as np
import pickle
from pathlib import Path
from rank_bm25 import BM25Okapi
from typing import List, Tuple, Optional

from app.ingestion import Chunk
from app import embedder

_faiss_index: Optional[faiss.IndexFlatIP] = None
_bm25_index: Optional[BM25Okapi] = None
_chunks: Optional[List[Chunk]] = None
_index_path: Optional[Path] = None

def initialize(index_dir: Path) -> None:
    """
    Initializes the vector store. Loads from disk if available,
    otherwise sets up empty indexes.
    """
    global _faiss_index, _bm25_index, _chunks, _index_path
    
    _index_path = index_dir / "store.pkl"
    
    if _index_path.exists():
        load()
    else:
        _faiss_index = faiss.IndexFlatIP(embedder.get_embedding_dim())
        _chunks = []
        _bm25_index = None
        print("Initialized empty vector store.")

def add_chunks(chunks: List[Chunk]) -> None:
    """
    Embeds chunks, adds them to FAISS, and rebuilds the BM25 index.
    Saves the state to disk afterwards.
    """
    global _faiss_index, _bm25_index, _chunks
    
    if not chunks:
        return
        
    # Embed texts
    texts = [chunk.text for chunk in chunks]
    embeddings = embedder.embed_documents(texts)
    
    # Add to FAISS
    _faiss_index.add(embeddings)
    
    # Add to _chunks
    _chunks.extend(chunks)
    
    # Rebuild BM25 over ALL chunks
    corpus_tokens = [chunk.text.lower().split() for chunk in _chunks]
    if corpus_tokens:
        _bm25_index = BM25Okapi(corpus_tokens)
        
    save()
    print(f"Added {len(chunks)} chunks. Total: {len(_chunks)}")

def search_semantic(query_vec: np.ndarray, top_k: int = 20) -> List[Tuple[Chunk, float]]:
    """
    Searches the FAISS index using the query vector.
    """
    if not _chunks or _faiss_index.ntotal == 0:
        return []
        
    scores, indices = _faiss_index.search(query_vec, top_k)
    
    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx != -1:
            results.append((_chunks[idx], float(score)))
            
    return results

def search_bm25(query: str, top_k: int = 20) -> List[Tuple[Chunk, float]]:
    """
    Searches the BM25 index using the query text.
    """
    if not _chunks or _bm25_index is None:
        return []
        
    query_tokens = query.lower().split()
    scores = _bm25_index.get_scores(query_tokens)
    
    # Sort indices by score descending
    top_indices = np.argsort(scores)[::-1][:top_k]
    
    results = []
    for idx in top_indices:
        score = scores[idx]
        if score > 0:
            results.append((_chunks[idx], float(score)))
            
    return results

def get_all_doc_names() -> List[str]:
    """Returns a sorted list of unique document names."""
    if not _chunks:
        return []
    return sorted(list(set(chunk.doc_name for chunk in _chunks)))

def get_chunk_count() -> int:
    """Returns the total number of chunks."""
    return len(_chunks) if _chunks else 0

def clear() -> None:
    """Clears all state and deletes the persistent file."""
    global _faiss_index, _bm25_index, _chunks
    
    _faiss_index = faiss.IndexFlatIP(embedder.get_embedding_dim())
    _bm25_index = None
    _chunks = []
    
    if _index_path and _index_path.exists():
        _index_path.unlink()
        
    if _index_path:
        faiss_path = _index_path.with_suffix(".faiss")
        if faiss_path.exists():
            faiss_path.unlink()
            
    print("Cleared persistent vector store.")

def save() -> None:
    """Pickles the current state to the _index_path."""
    if _index_path is None:
        raise ValueError("Vector store not initialized. Cannot save.")
        
    _index_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Save FAISS separately to avoid SWIG serialization bugs on Windows
    faiss_path = _index_path.with_suffix(".faiss")
    faiss.write_index(_faiss_index, str(faiss_path))
    
    with open(_index_path, "wb") as f:
        pickle.dump((_bm25_index, _chunks), f)

def load() -> None:
    """Unpickles from _index_path and restores all state variables."""
    global _faiss_index, _bm25_index, _chunks
    
    if _index_path is None or not _index_path.exists():
        raise FileNotFoundError(f"Index file not found at {_index_path}")
        
    faiss_path = _index_path.with_suffix(".faiss")
    if faiss_path.exists():
        _faiss_index = faiss.read_index(str(faiss_path))
    else:
        _faiss_index = faiss.IndexFlatIP(embedder.get_embedding_dim())
        
    with open(_index_path, "rb") as f:
        state = pickle.load(f)
        
    if len(state) == 2:
        _bm25_index, _chunks = state
    elif len(state) == 3:
        # Fallback for old broken states
        _, _bm25_index, _chunks = state
        
    print(f"Loaded vector store with {len(_chunks)} chunks.")

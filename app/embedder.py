"""
Embedding module using BAAI/bge-small-en-v1.5
"""
import numpy as np
from sentence_transformers import SentenceTransformer
import warnings

# Suppress sentence_transformers warnings about huggingface
warnings.filterwarnings("ignore", category=UserWarning, module="sentence_transformers")

_model = None

def get_model() -> SentenceTransformer:
    """Returns the singleton embedding model, loading it if necessary."""
    global _model
    if _model is None:
        print("Loading BGE embedding model...")
        _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
    return _model

def embed_documents(texts: list[str]) -> np.ndarray:
    """
    Embeds a list of document chunks. No instruction prefix is added.
    Vectors are L2-normalized.
    """
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
        
    model = get_model()
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False, convert_to_numpy=True)
    
    # Normalize to unit length
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1e-10  # Prevent division by zero
    normalized = embeddings / norms
    
    return normalized.astype(np.float32)

def embed_query(query: str) -> np.ndarray:
    """
    Embeds a single query string, prepending the required BGE instruction prefix.
    Vector is L2-normalized.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")
        
    model = get_model()
    instruction_prefix = "Represent this sentence for searching relevant passages: "
    full_query = instruction_prefix + query
    
    embedding = model.encode([full_query], show_progress_bar=False, convert_to_numpy=True)
    
    # Normalize
    norm = np.linalg.norm(embedding, axis=1, keepdims=True)
    norm[norm == 0] = 1e-10
    normalized = embedding / norm
    
    return normalized.astype(np.float32)

def get_embedding_dim() -> int:
    """Returns the dimension of the embeddings."""
    return 384

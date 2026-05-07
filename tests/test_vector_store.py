import pytest
import numpy as np
from pathlib import Path

from app.ingestion import Chunk
from app import embedder
from app import vector_store

def test_embed_documents_shape():
    docs = ["hello world", "foo bar"]
    emb = embedder.embed_documents(docs)
    assert emb.shape == (2, 384)
    assert emb.dtype == np.float32

def test_embed_documents_normalized():
    docs = ["this is random text one", "second random text", "third", "fourth", "fifth"]
    emb = embedder.embed_documents(docs)
    norms = np.linalg.norm(emb, axis=1)
    for norm in norms:
        assert abs(norm - 1.0) < 1e-5

def test_embed_query_prefix():
    # Behavioral test: should not raise and return correct shape
    emb = embedder.embed_query("test query")
    assert emb.shape == (1, 384)
    assert emb.dtype == np.float32

def test_add_and_search_semantic(tmp_path):
    vector_store.initialize(tmp_path)
    chunks = []
    for i in range(10):
        chunks.append(Chunk(
            chunk_id=f"id_{i}",
            doc_name="test_doc",
            page_number=1,
            text=f"This is the specific semantic chunk number {i}",
            token_count=10
        ))
    vector_store.add_chunks(chunks)
    assert vector_store.get_chunk_count() == 10
    
    query_vec = embedder.embed_query("semantic chunk number 5")
    results = vector_store.search_semantic(query_vec, top_k=3)
    
    # Assert the related chunk appears in top-3
    found = any("number 5" in chunk.text for chunk, score in results)
    assert found

def test_add_and_search_bm25(tmp_path):
    vector_store.initialize(tmp_path)
    chunks = []
    for i in range(10):
        text = f"Ordinary chunk {i}"
        if i == 7:
            text = "This chunk contains a zygomorphic keyword"
            
        chunks.append(Chunk(
            chunk_id=f"id_{i}",
            doc_name="test_doc",
            page_number=1,
            text=text,
            token_count=10
        ))
        
    vector_store.add_chunks(chunks)
    results = vector_store.search_bm25("zygomorphic")
    
    assert len(results) > 0
    assert "zygomorphic" in results[0][0].text

def test_persistence(tmp_path):
    vector_store.initialize(tmp_path)
    chunks = [
        Chunk(chunk_id="id_1", doc_name="doc1", page_number=1, text="text1", token_count=1),
        Chunk(chunk_id="id_2", doc_name="doc2", page_number=2, text="text2", token_count=1)
    ]
    vector_store.add_chunks(chunks)
    vector_store.save()
    
    vector_store.clear()
    assert vector_store.get_chunk_count() == 0
    
    vector_store.initialize(tmp_path)
    assert vector_store.get_chunk_count() == 2

def test_clear(tmp_path):
    vector_store.initialize(tmp_path)
    vector_store.add_chunks([
        Chunk(chunk_id="id_1", doc_name="doc1", page_number=1, text="text1", token_count=1)
    ])
    
    vector_store.clear()
    assert vector_store.get_chunk_count() == 0
    assert not (tmp_path / "store.pkl").exists()

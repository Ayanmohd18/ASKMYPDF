import pytest
from app import vector_store
from app import retriever
from app.retriever import RetrievedChunk, reciprocal_rank_fusion
from app.ingestion import Chunk

@pytest.fixture(scope="module")
def populated_index_dir(tmp_path_factory):
    """
    Module-scoped fixture to build the index once.
    Embeds 20 chunks (10 ML, 10 Legal).
    """
    index_dir = tmp_path_factory.mktemp("index_dir")
    vector_store.initialize(index_dir)
    vector_store.clear()
    
    chunks = []
    # 10 ML chunks
    for i in range(10):
        chunks.append(Chunk(
            chunk_id=f"ml_{i}",
            doc_name="ml_doc",
            page_number=i+1,
            text=f"This is about machine learning, neural networks, and deep learning. Topic {i}.",
            token_count=15
        ))
    
    # 10 Legal chunks
    for i in range(10, 20):
        chunks.append(Chunk(
            chunk_id=f"legal_{i}",
            doc_name="legal_doc",
            page_number=i+1,
            text=f"This describes contract law, jurisdiction, and legal binding agreements. Clause {i}.",
            token_count=15
        ))
        
    vector_store.add_chunks(chunks)
    return index_dir

@pytest.fixture
def use_populated_store(populated_index_dir):
    """
    Function-scoped fixture to ensure the global vector store is 
    pointing to the populated index before the test runs.
    """
    vector_store.initialize(populated_index_dir)
    return populated_index_dir

def test_rrf_merge_correctness():
    # Construct synthetic results
    semantic_results = []
    bm25_results = []
    
    # Both lists contain chunk "A" at rank 1
    chunk_a = Chunk("A", "doc", 1, "text A", 10)
    semantic_results.append((chunk_a, 0.9))
    bm25_results.append((chunk_a, 10.5))
    
    # Chunk "B" only in semantic at rank 2
    chunk_b = Chunk("B", "doc", 1, "text B", 10)
    semantic_results.append((chunk_b, 0.8))
    
    # Chunk "C" only in bm25 at rank 2
    chunk_c = Chunk("C", "doc", 1, "text C", 10)
    bm25_results.append((chunk_c, 9.2))
    
    rrf_results = reciprocal_rank_fusion(semantic_results, bm25_results, k=60)
    
    assert len(rrf_results) == 3
    
    # Chunk A should be first (rank 1 in both)
    assert rrf_results[0].chunk.chunk_id == "A"
    
    # Verify RRF score computation for A
    expected_rrf_a = (1.0 / (60 + 1)) + (1.0 / (60 + 1))
    assert abs(rrf_results[0].rrf_score - expected_rrf_a) < 1e-6
    
    # Verify B and C scores
    expected_rrf_b = (1.0 / (60 + 2)) + (1.0 / (60 + 1001))
    expected_rrf_c = (1.0 / (60 + 1001)) + (1.0 / (60 + 2))
    
    # Find B and C in results
    b_res = next(r for r in rrf_results if r.chunk.chunk_id == "B")
    c_res = next(r for r in rrf_results if r.chunk.chunk_id == "C")
    
    assert abs(b_res.rrf_score - expected_rrf_b) < 1e-6
    assert abs(c_res.rrf_score - expected_rrf_c) < 1e-6

def test_retrieve_returns_reranked_chunks(use_populated_store):
    results = retriever.retrieve("neural network training")
    
    assert isinstance(results, list)
    assert len(results) <= 5
    assert len(results) > 0
    
    for r in results:
        assert isinstance(r, RetrievedChunk)
        assert r.reranker_score != 0.0
        assert "machine learning" in r.chunk.text or "neural network" in r.chunk.text or "deep learning" in r.chunk.text

def test_retrieve_topic_separation(use_populated_store):
    legal_results = retriever.retrieve("contract law")
    assert len(legal_results) > 0
    # Top result should be from legal doc
    assert legal_results[0].chunk.doc_name == "legal_doc"
    
    ml_results = retriever.retrieve("deep learning")
    assert len(ml_results) > 0
    # Top result should be from ml doc
    assert ml_results[0].chunk.doc_name == "ml_doc"

def test_retrieve_empty_store(tmp_path):
    # Initialize fresh empty store
    vector_store.initialize(tmp_path)
    vector_store.clear()
    
    with pytest.raises(ValueError, match="No documents indexed"):
        retriever.retrieve("anything")

def test_retrieved_chunk_fields(use_populated_store):
    results = retriever.retrieve("jurisdiction")
    assert len(results) > 0
    
    for r in results:
        assert r.rrf_score > 0
        assert isinstance(r.reranker_score, float)
        assert isinstance(r.chunk.chunk_id, str)
        assert len(r.chunk.chunk_id) > 0
        assert r.chunk.page_number >= 1

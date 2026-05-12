import os
import json
import re
from dataclasses import dataclass
from typing import List, Optional

from app.retriever import retrieve, RetrievedChunk
from app.generator import call_gemini, call_hf, call_ollama, SYSTEM_PROMPT

@dataclass
class CorpusProfile:
    """Result of the analysis pass."""
    domain: str          # "legal", "medical", "technical", "academic", "business", "financial", "general"
    primary_topics: List[str]   # top 5 themes detected
    doc_names: List[str]        # all source doc names
    has_dates: bool             # timeline-worthy?
    has_numbers: bool           # data-table-worthy?
    has_entities: bool          # people/orgs/places?
    has_contradictions: bool    # multiple conflicting sources?
    recommended_formats: List[str]  # which studio tools fit
    total_chunks: int
    key_terms: List[str]    # top 15 domain-specific terms

def call_llm(system: str, user: str, backend: str) -> str:
    """Routes to call_gemini / call_hf / call_ollama based on the specified backend."""
    backend = backend or os.getenv("LLM_BACKEND", "gemini")
    if backend == "gemini":
        return call_gemini(system, user)
    elif backend == "hf":
        return call_hf(system, user)
    elif backend == "ollama":
        return call_ollama(system, user)
    else:
        raise ValueError(f"Unknown backend: {backend}. Choose: gemini, hf, ollama")

def format_chunks_for_analysis(chunks: List[RetrievedChunk]) -> str:
    """
    Returns chunks formatted as:
    [Source: {doc_name}, p.{page}]
    {text}
    ---
    Truncates each chunk to 600 chars for analysis pass.
    """
    formatted = []
    for rc in chunks:
        doc_name = rc.chunk.doc_name
        page = rc.chunk.page_number
        text = rc.chunk.text[:600]
        formatted.append(f"[Source: {doc_name}, p.{page}]\n{text}\n---")
    return "\n".join(formatted)

def format_chunks_for_generation(chunks: List[RetrievedChunk]) -> str:
    """
    Returns full chunks formatted for high-precision generation:
    SOURCE [{i}]: {doc_name}, Page {page}
    CONTENT: {full text}
    ───────────────────────────────────────
    """
    formatted = []
    for i, rc in enumerate(chunks, start=1):
        doc_name = rc.chunk.doc_name
        page = rc.chunk.page_number
        text = rc.chunk.text
        formatted.append(f"SOURCE [{i}]: {doc_name}, Page {page}\nCONTENT: {text}\n" + "─" * 40)
    return "\n".join(formatted)

def analyze_corpus(
    top_chunks: List[RetrievedChunk],
    llm_backend: str = "gemini"
) -> CorpusProfile:
    """
    The ANALYSIS PASS — runs before any generation to understand the corpus.
    """
    system = """You are a document analyst. 
Analyze the provided text corpus and return a JSON object ONLY — no markdown, no explanation, just JSON."""
    
    user = f"""
Analyze this corpus of text chunks from the user's documents and return ONLY valid JSON:

CHUNKS:
{format_chunks_for_analysis(top_chunks)}

Return exactly this JSON structure:
{{
  "domain": "<one of: legal|medical|technical|academic|business|financial|general>",
  "primary_topics": ["topic1","topic2","topic3","topic4","topic5"],
  "has_dates": <true|false>,
  "has_numbers": <true|false>,
  "has_entities": <true|false>,
  "has_contradictions": <true|false>,
  "recommended_formats": ["<list of: briefing|presentation|mindmap|infographic|datatable>"],
  "key_terms": ["term1",..."term15"]
}}
"""
    
    try:
        response = call_llm(system, user, llm_backend)
        # Strip markdown if present
        clean_json = re.sub(r'```json\s*|\s*```', '', response).strip()
        data = json.loads(clean_json)
        
        # Get all unique doc names for the profile
        doc_names = list(set(rc.chunk.doc_name for rc in top_chunks))
        
        return CorpusProfile(
            domain=data.get("domain", "general"),
            primary_topics=data.get("primary_topics", []),
            doc_names=doc_names,
            has_dates=data.get("has_dates", False),
            has_numbers=data.get("has_numbers", False),
            has_entities=data.get("has_entities", False),
            has_contradictions=data.get("has_contradictions", False),
            recommended_formats=data.get("recommended_formats", ["briefing"]),
            total_chunks=len(top_chunks),
            key_terms=data.get("key_terms", [])
        )
    except Exception as e:
        print(f"Error in analyze_corpus: {e}")
        # Return a sensible default on error
        doc_names = list(set(rc.chunk.doc_name for rc in top_chunks))
        return CorpusProfile(
            domain="general",
            primary_topics=["General Overview"],
            doc_names=doc_names,
            has_dates=False,
            has_numbers=False,
            has_entities=False,
            has_contradictions=False,
            recommended_formats=["briefing"],
            total_chunks=len(top_chunks),
            key_terms=[]
        )

def retrieve_all_for_studio(
    doc_names: Optional[List[str]] = None,
    max_chunks: int = 40
) -> List[RetrievedChunk]:
    """
    Studio features need the FULL corpus, not just query-relevant chunks.
    Retrieves a diverse set of chunks across the entire indexed corpus or specific documents.
    """
    meta_queries = [
        "main topics overview summary",
        "key findings conclusions results",
        "important data numbers statistics",
        "key people entities organizations",
        "process steps methodology timeline"
    ]
    
    all_retrieved = []
    seen_ids = set()
    
    for query in meta_queries:
        # Retrieve top 20 for each broad meta-query
        chunks = retrieve(query, semantic_top_k=20, bm25_top_k=20, reranker_top_k=20)
        for rc in chunks:
            if rc.chunk.chunk_id not in seen_ids:
                # If doc_names is provided, filter here
                if doc_names and rc.chunk.doc_name not in doc_names:
                    continue
                all_retrieved.append(rc)
                seen_ids.add(rc.chunk.chunk_id)
    
    # Diversity strategy: sort by doc_name then page_number to ensure cross-document coverage
    all_retrieved.sort(key=lambda x: (x.chunk.doc_name, x.chunk.page_number))
    
    # Return up to max_chunks
    return all_retrieved[:max_chunks]

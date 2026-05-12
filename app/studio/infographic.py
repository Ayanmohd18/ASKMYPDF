import json
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from app.studio.engine import (
    CorpusProfile, 
    retrieve_all_for_studio, 
    analyze_corpus,
    format_chunks_for_generation, 
    call_llm
)

@dataclass
class InfographicSection:
    section_type: str    # "hero_stat" | "process_steps" | "comparison" | "timeline" | "key_facts" | "hub_spoke" | "quote_highlight" | "pyramid"
    title: str
    data: Dict[str, Any] # type-specific structure
    citation: str

@dataclass
class InfographicData:
    title: str
    subtitle: str
    theme_color: str     # hex, domain-appropriate
    sections: List[InfographicSection]
    footer_note: str     # "Based on {N} documents"

def parse_json(text: str) -> Any:
    """Utility to strip markdown and parse JSON."""
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        return None

def generate_infographic(
    focus: str = None,
    doc_names: List[str] = None,
    llm_backend: str = "gemini"
) -> InfographicData:
    """
    Generates structured infographic data by selecting the best visual layouts for the corpus content.
    """
    
    # STEP 1 — Retrieve + analyze corpus
    chunks = retrieve_all_for_studio(doc_names, max_chunks=40)
    if not chunks:
        raise ValueError("No documents indexed. Please ingest PDFs first.")
    
    profile = analyze_corpus(chunks, llm_backend)

    # STEP 2 — Domain-to-theme color mapping
    domain_colors = {
        "legal": "#1E3A5F",       # deep navy
        "medical": "#0D6E6E",     # clinical teal
        "financial": "#1A4731",   # financial green
        "technical": "#2D3561",   # tech blue
        "academic": "#4A235A",    # academic purple
        "business": "#7B3A10",    # business amber
        "general": "#1A7A6E"      # default teal
    }
    theme_color = domain_colors.get(profile.domain, domain_colors["general"])

    # STEP 3 — Section selection based on profile
    section_types = ["key_facts"] # Always include
    
    if profile.has_numbers:
        section_types.append("hero_stat")
    
    if profile.has_dates:
        section_types.append("timeline")
        
    # If primary_topics has 2 clearly contrasting themes (simplistic heuristic check)
    if len(profile.primary_topics) >= 2:
        section_types.append("comparison")
        
    if profile.domain in ["technical", "medical", "legal"]:
        section_types.append("process_steps")
        
    section_types.append("quote_highlight") # Always end with a quote
    
    # Limit to max 5 sections total, preserving key sections
    section_types = list(dict.fromkeys(section_types)) # Remove duplicates
    if len(section_types) > 5:
        # Keep key_facts, quote_highlight and first 3 others
        base = ["key_facts", "quote_highlight"]
        others = [s for s in section_types if s not in base]
        section_types = base[:1] + others[:3] + base[1:]

    # STEP 4 — Generation prompt
    system = """You are an infographic designer and analyst.
Extract only real, specific, cited content from the provided source materials.
No generic filler. Your output must be structurally perfect according to the specified schemas.
Return JSON only."""

    user_prompt = f"""
Create an infographic from these documents.

FOCUS: {focus or "Key insights and findings"}
DOMAIN: {profile.domain}
SECTIONS TO GENERATE: {section_types}

SOURCE CHUNKS:
{format_chunks_for_generation(chunks)}

DATA STRUCTURES per section type (use these EXACTLY):

"hero_stat":
{{
  "number": "e.g., 47%",
  "label": "short label",
  "context": "one sentence explaining the stat",
  "citation": "DocName, p.N"
}}

"process_steps":
{{
  "steps": [
    {{"number": 1, "title": "Step name", "description": "one sentence", "citation": "DocName, p.N"}}
  ]
}}

"comparison":
{{
  "label_a": "Option/Entity A",
  "label_b": "Option/Entity B",
  "dimensions": [
    {{"aspect": "aspect name", "a": "what A says/does", "b": "what B says/does", "winner": "a|b|tie"}}
  ]
}}

"timeline":
{{
  "events": [
    {{"date": "...", "event": "short description", "significance": "why it matters", "citation": "DocName, p.N"}}
  ]
}}

"key_facts":
{{
  "facts": [
    {{"icon": "⚖️|💊|📊|🔧|📋|💡|⚠️|✅", "fact": "specific factual claim", "citation": "DocName, p.N"}}
  ]
}}

"quote_highlight":
{{
  "quote": "exact impactful sentence from source",
  "source": "DocName, p.N",
  "context": "why this sentence matters"
}}

Return JSON:
{{
  "title": "<infographic title>",
  "subtitle": "<domain> Analysis",
  "sections": [
    {{
      "section_type": "<type>",
      "title": "<section heading>",
      "data": <type-specific dict as defined above>,
      "citation": "<primary source used for this section>"
    }}
  ],
  "footer_note": "Based on {len(chunks)} excerpts from {len(profile.doc_names)} documents"
}}
Return JSON only.
"""

    response = call_llm(system, user_prompt, llm_backend)
    data = parse_json(response)
    
    if not data:
        raise ValueError("Failed to generate infographic data.")

    # STEP 5 — Parse and return InfographicData
    sections = []
    for s_dict in data.get("sections", []):
        sections.append(InfographicSection(
            section_type=s_dict.get("section_type"),
            title=s_dict.get("title"),
            data=s_dict.get("data", {}),
            citation=s_dict.get("citation", "")
        ))
        
    return InfographicData(
        title=data.get("title", "Document Infographic"),
        subtitle=data.get("subtitle", f"{profile.domain.capitalize()} Insights"),
        theme_color=theme_color,
        sections=sections,
        footer_note=data.get("footer_note", f"Based on {len(chunks)} excerpts from {len(profile.doc_names)} documents")
    )

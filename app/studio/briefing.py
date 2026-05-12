import json
import re
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.studio.engine import (
    CorpusProfile, 
    retrieve_all_for_studio, 
    analyze_corpus,
    format_chunks_for_generation, 
    call_llm
)
from app.retriever import RetrievedChunk

def generate_briefing(
    focus_query: Optional[str] = None,
    doc_names: Optional[List[str]] = None,
    llm_backend: str = "gemini",
    audience: str = "executive"  # options: executive | technical | academic | general
) -> Dict[str, Any]:
    """
    Generates a high-quality Briefing Document based on the provided corpus.
    Uses a domain-adaptive strategy with rigorous citations and conflict detection.
    """
    
    # STEP 1 — Retrieve corpus
    chunks = retrieve_all_for_studio(doc_names, max_chunks=40)
    if not chunks:
        raise ValueError("No documents indexed. Please upload and ingest PDFs first.")

    # STEP 2 — Analysis pass
    profile = analyze_corpus(chunks, llm_backend)

    # STEP 3 — Build domain-adaptive system prompt
    domain_instructions = {
        "legal": """
Structure: Legal Summary | Key Obligations | Risk Factors | Open Legal Questions.
Use precise legal language. Flag ambiguous clauses.
Every claim must cite document and page number.""",
        
        "medical": """
Structure: Clinical Summary | Key Findings | Treatment Implications | Evidence Gaps.
Use clinical terminology. Note evidence quality (RCT vs observational). 
Every claim must cite document and page number.""",
        
        "financial": """
Structure: Financial Overview | Key Metrics | Risk Factors | Strategic Implications.
Lead with numbers. Express trends as percentages.
Flag any conflicting figures across sources.""",
        
        "technical": """
Structure: Technical Summary | Architecture/Approach | Key Specifications | Implementation Considerations.
Be precise about technical claims. Distinguish specifications from recommendations.""",
        
        "academic": """
Structure: Research Overview | Key Arguments | Evidence Quality | Methodological Notes | Research Gaps.
Surface contradictions between sources explicitly.""",
        
        "business": """
Structure: Situation | Complication | Resolution | Recommended Actions.
Use McKinsey-style pyramid: conclusion first, then evidence.""",
        
        "general": """
Structure: Overview | Key Points | Implications | Open Questions.
Write clearly for an informed non-specialist."""
    }
    
    audience_instructions = {
        "executive": "Write for a C-level reader. Lead with implications, not details. Max 600 words total. Use crisp, declarative sentences.",
        "technical": "Write for a senior engineer or specialist. Include precise technical detail. Do not simplify terminology.",
        "academic": "Write for a researcher. Surface methodological nuance and conflicting evidence. Use hedged language for contested claims.",
        "general": "Write for an educated non-specialist. Explain jargon on first use. Use examples."
    }

    # Fallback to general if domain not recognized
    domain_instr = domain_instructions.get(profile.domain, domain_instructions["general"])
    audience_instr = audience_instructions.get(audience, audience_instructions["general"])

    # STEP 4 — Generation prompt
    system = f"""You are an expert analyst writing a briefing document. 
{domain_instr}

{audience_instr}

CITATION RULES — MANDATORY:
- After EVERY factual claim, write [DocName, p.N]
- If 2+ sources agree on a point, cite all of them (e.g., [DocA, p.1; DocB, p.5])
- If sources CONTRADICT each other, write: [CONFLICT: DocA says X (DocA, p.N), DocB says Y (DocB, p.N)]
- If a claim has no source in the provided chunks, DO NOT include it

OUTPUT FORMAT — return valid JSON only:
{{
  "title": "<Briefing title based on content>",
  "subtitle": "<domain> Briefing · <date>",
  "executive_summary": "<2-3 sentence TL;DR>",
  "sections": [
    {{
      "heading": "<section heading>",
      "content": "<paragraphs with inline citations>"
    }}
  ],
  "key_facts": [
    {{"fact": "<specific claim>", 
      "source": "<DocName, p.N>"}}
  ],
  "conflicts_detected": [
    {{"topic": "<topic>", 
      "position_a": "<claim + source>",
      "position_b": "<claim + source>"}}
  ],
  "open_questions": [
    "<question the documents don't fully answer>"
  ],
  "sources_used": ["<doc_name>"],
  "word_count": <integer>
}}"""

    user = f"""
FOCUS: {focus_query or "Comprehensive overview of all uploaded documents"}

KEY THEMES DETECTED: {", ".join(profile.primary_topics)}
DOMAIN: {profile.domain}
DATE: {datetime.now().strftime('%Y-%m-%d')}

SOURCE CHUNKS:
{format_chunks_for_generation(chunks)}

Generate the briefing document now. Return JSON only.
"""

    def attempt_parse(resp: str) -> Optional[Dict[str, Any]]:
        try:
            # Strip markdown blocks
            clean_json = re.sub(r'```json\s*|\s*```', '', resp).strip()
            return json.loads(clean_json)
        except Exception:
            return None

    # STEP 5 — Call LLM, parse JSON, return dict
    response = call_llm(system, user, llm_backend)
    parsed = attempt_parse(response)
    
    if parsed is None:
        # Retry once with explicit instruction
        retry_user = "ERROR: Your previous response was not valid JSON. Return ONLY valid JSON, no markdown, no explanation.\n\n" + user
        response = call_llm(system, retry_user, llm_backend)
        parsed = attempt_parse(response)
        
    if parsed is None:
        raise RuntimeError("Failed to generate a valid Briefing JSON after retry.")
        
    return parsed

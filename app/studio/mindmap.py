import json
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union

from app.studio.engine import (
    CorpusProfile, 
    retrieve_all_for_studio, 
    analyze_corpus,
    format_chunks_for_generation, 
    call_llm
)
from app.retriever import retrieve, RetrievedChunk

@dataclass
class MindmapNode:
    id: str                    # unique slug e.g. "payment-terms"
    label: str                 # short display label (≤4 words)
    summary: str               # 2-3 sentence explanation
    citations: List[str]       # ["DocName, p.N"]
    children: List["MindmapNode"] = field(default_factory=list)  # empty for leaf nodes
    color: str = ""            # hex, assigned by level

@dataclass  
class CrossConnection:
    source_id: str             # node id
    target_id: str             # node id
    relationship: str          # "supports" | "contradicts" | "requires" | "extends" | "contrasts_with"
    explanation: str           # one sentence why

@dataclass
class MindmapData:
    root: MindmapNode
    cross_connections: List[CrossConnection]
    profile: CorpusProfile

def parse_json(text: str) -> Any:
    """Utility to strip markdown and parse JSON."""
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        return None

def format_nodes_flat(node: Dict[str, Any], level: int = 1) -> str:
    """Recursively flattens the node structure into a list string for LLM analysis."""
    lines = [f"- ID: {node['id']}, Label: {node['label']}, Level: {level}, Summary: {node['summary'][:50]}..."]
    for child in node.get("children", []):
        lines.append(format_nodes_flat(child, level + 1))
    return "\n".join(lines)

def generate_mindmap(
    doc_names: List[str] = None,
    llm_backend: str = "gemini"
) -> MindmapData:
    """
    Generates a 3-level interactive mindmap structure with cross-connections.
    """
    
    # STEP 1 — Retrieve + analyze corpus
    chunks = retrieve_all_for_studio(doc_names, max_chunks=40)
    if not chunks:
        raise ValueError("No documents indexed. Please ingest PDFs first.")
    
    profile = analyze_corpus(chunks, llm_backend)

    # STEP 2 — Generate mindmap structure in TWO passes

    # PASS 1 — Tree structure
    system = "You are a knowledge architect building a concept map. Return JSON only."
    user_tree = f"""
Build a 3-level concept map from these document chunks.

DOMAIN: {profile.domain}
PRIMARY TOPICS: {", ".join(profile.primary_topics)}
KEY TERMS: {", ".join(profile.key_terms)}

STRUCTURE RULES:
- root: The single unifying theme of ALL documents (not a document title — a conceptual theme)
- Level 2 nodes (branches): 4-6 major subtopics. Each must be meaningfully DIFFERENT, not overlapping.
- Level 3 nodes (leaves): 3-4 specific concepts, terms, findings, or entities per branch. 
  Must be concrete and source-specific, not generic.

QUALITY RULES:
- Labels: max 4 words, noun phrases preferred.
- Summaries: must cite specific evidence from chunks.
- No branch should be called "Introduction", "Overview", "Conclusion".
- Legal domain: use clause/obligation structure.
- Medical domain: use condition/treatment/evidence.
- Technical: use component/function/dependency.

SOURCE CHUNKS:
{format_chunks_for_generation(chunks)}

Return JSON:
{{
  "root": {{
    "id": "root",
    "label": "<central theme>",
    "summary": "<2-3 sentences>",
    "citations": [],
    "children": [
      {{
        "id": "<slug>",
        "label": "<branch label>",
        "summary": "<2-3 sentences with citations>",
        "citations": ["DocName, p.N"],
        "children": [
          {{
            "id": "<slug>",
            "label": "<leaf label>",
            "summary": "<1-2 sentences with citation>",
            "citations": ["DocName, p.N"],
            "children": []
          }}
        ]
      }}
    ]
  }}
}}
Return JSON only.
"""
    tree_resp = call_llm(system, user_tree, llm_backend)
    tree_result = parse_json(tree_resp)
    if not tree_result or "root" not in tree_result:
        raise ValueError("Failed to generate mindmap tree structure.")

    # PASS 2 — Cross-connections
    cross_prompt = f"""
Given this mindmap structure, identify 4-8 CROSS-CONNECTIONS between nodes in DIFFERENT branches.

MINDMAP NODES:
{format_nodes_flat(tree_result["root"])}

A cross-connection is a meaningful relationship between two concepts that are in different branches of the map.
Only include connections that are genuinely surprising or illuminating.

Relationship types:
- "supports": Node A provides evidence for Node B
- "contradicts": Node A conflicts with Node B
- "requires": Node A depends on Node B
- "extends": Node A builds on Node B
- "contrasts_with": Node A and B take different approaches

Return JSON array:
[
  {{
    "source_id": "<node_id>",
    "target_id": "<node_id>",
    "relationship": "<type>",
    "explanation": "<one sentence why this link matters>"
  }}
]
Return JSON only.
"""
    cross_resp = call_llm(system, cross_prompt, llm_backend)
    cross_result = parse_json(cross_resp) or []

    # STEP 3 — Assign colors by level and convert to Dataclasses
    colors = ["#2DA89A", "#D4825A", "#7B61A8", "#4A90B8", "#8B6914", "#5C9E6A"]
    
    def process_node(node_dict: Dict[str, Any], level: int, branch_idx: int = 0, parent_color: str = "") -> MindmapNode:
        if level == 1:
            color = "#1A7A6E" # Root teal
        elif level == 2:
            color = colors[branch_idx % len(colors)]
        else:
            # Level 3: 70% opacity of parent color (simulated here as the same color for logic)
            # In a real UI this might be handled via CSS or hex adjustment
            color = parent_color
            
        children = []
        for i, child_dict in enumerate(node_dict.get("children", [])):
            children.append(process_node(child_dict, level + 1, i if level == 1 else branch_idx, color))
            
        return MindmapNode(
            id=node_dict.get("id", f"node_{level}_{branch_idx}"),
            label=node_dict.get("label", "Unknown"),
            summary=node_dict.get("summary", ""),
            citations=node_dict.get("citations", []),
            children=children,
            color=color
        )

    root_node = process_node(tree_result["root"], 1)
    
    connections = [
        CrossConnection(
            source_id=c.get("source_id"),
            target_id=c.get("target_id"),
            relationship=c.get("relationship", "supports"),
            explanation=c.get("explanation", "")
        ) for c in cross_result if c.get("source_id") and c.get("target_id")
    ]

    return MindmapData(root=root_node, cross_connections=connections, profile=profile)

def find_node_by_id(node: MindmapNode, node_id: str) -> Optional[MindmapNode]:
    """Recursively searches for a node by ID."""
    if node.id == node_id:
        return node
    for child in node.children:
        found = find_node_by_id(child, node_id)
        if found:
            return found
    return None

def node_drill_down(
    node_id: str,
    mindmap: MindmapData,
    llm_backend: str = "gemini"
) -> str:
    """
    Generates a focused 3-paragraph explanation of a specific node.
    """
    node = find_node_by_id(mindmap.root, node_id)
    if not node:
        return f"Node with ID {node_id} not found."
    
    # Retrieve targeted chunks
    search_query = f"{node.label} {node.summary}"
    chunks = retrieve(search_query, reranker_top_k=8)
    
    system_prompt = "You are an expert analyst. Provide a clear, focused explanation based on the context."
    user_prompt = f"""
Write a focused 3-paragraph explanation of '{node.label}' as it appears in the source documents.
Include: what it is, why it matters in this context, and how it relates to the broader document themes.

DOCUMENTS: {", ".join(mindmap.profile.doc_names)}
CONTEXT:
{format_chunks_for_generation(chunks)}

Cite every claim using [DocName, p.N]. 
Return plain text, no JSON, no markdown headers.
"""
    
    return call_llm(system_prompt, user_prompt, llm_backend)

import json
import re
import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.studio.engine import (
    CorpusProfile, 
    retrieve_all_for_studio, 
    analyze_corpus,
    format_chunks_for_analysis,
    format_chunks_for_generation, 
    call_llm
)
from app.retriever import RetrievedChunk

@dataclass
class TableCell:
    value: str          # the extracted value
    citation: str       # "DocName, p.N" or "Not found"
    confidence: str     # "high" | "medium" | "low"
    conflict: bool      # True if sources disagree

@dataclass
class TableRow:
    entity: str              # row identifier (e.g., project name, person, drug)
    cells: Dict[str, TableCell]  # column_name -> cell

@dataclass  
class ExtractedTable:
    title: str
    columns: List[str]
    rows: List[TableRow]
    extraction_notes: str   # what couldn't be extracted
    doc_coverage: Dict[str, int]  # doc_name -> rows found

def parse_json(text: str) -> Any:
    """Utility to strip markdown and parse JSON."""
    try:
        clean = re.sub(r'```json\s*|\s*```', '', text).strip()
        return json.loads(clean)
    except Exception as e:
        print(f"JSON Parse Error: {e}")
        return None

def auto_detect_schema(
    chunks: List[RetrievedChunk],
    profile: CorpusProfile,
    llm_backend: str = "gemini"
) -> Dict[str, Any]:
    """
    Detects the best table schema to extract from the corpus based on domain and content.
    """
    system = "You are a data analyst. Return JSON only."

    user_prompt = f"""
These documents contain structured information.
Determine the best table schema to extract.

DOMAIN: {profile.domain}
HAS NUMBERS: {profile.has_numbers}
HAS ENTITIES: {profile.has_entities}

DOMAIN SCHEMA SUGGESTIONS:
- legal: entity|obligation|deadline|penalty|jurisdiction
- medical: study|sample_size|intervention|outcome|evidence_level
- financial: metric|value|period|change|source
- business: initiative|owner|status|deadline|impact
- technical: component|version|specification|dependency|status

Look at these chunks and suggest the BEST schema:
{format_chunks_for_analysis(chunks[:15])}

Return JSON:
{{
  "table_title": "<what this table captures>",
  "row_entity": "<what each row represents>",
  "columns": ["col1", "col2", "col3", ...],
  "rationale": "<why this schema fits the content>"
}}
"""
    response = call_llm(system, user_prompt, llm_backend)
    return parse_json(response) or {
        "table_title": "Document Overview",
        "row_entity": "Key Concept",
        "columns": ["Concept", "Description", "Significance"],
        "rationale": "Generic fallback schema."
    }

def extract_table(
    columns: List[str] = None,
    row_entity: str = None,
    doc_names: List[str] = None,
    llm_backend: str = "gemini"
) -> ExtractedTable:
    """
    Main entrypoint for structured data extraction.
    Produces a table with citations and conflict detection.
    """
    
    # STEP 1 — Retrieve corpus
    chunks = retrieve_all_for_studio(doc_names, max_chunks=40)
    if not chunks:
        raise ValueError("No documents indexed. Please ingest PDFs first.")
    
    # STEP 2 — Analyze corpus
    profile = analyze_corpus(chunks, llm_backend)

    # STEP 3 — Schema detection if needed
    table_title = "Extracted Data"
    if not columns or not row_entity:
        schema = auto_detect_schema(chunks, profile, llm_backend)
        columns = columns or schema.get("columns", ["Key Entity", "Details"])
        row_entity = row_entity or schema.get("row_entity", "Entity")
        table_title = schema.get("table_title", "Document Data Table")

    # STEP 4 — Extraction prompt (the core pass)
    system = """You are a precise data extractor.
Extract ONLY values that are explicitly stated in the source chunks. 
If a value is not present: use "Not found".
If sources conflict: use "CONFLICT: [valA] vs [valB]".
Return JSON only. No hallucination."""

    user_prompt = f"""
Extract a structured table from these documents.

TABLE TITLE: {table_title}
EACH ROW REPRESENTS: {row_entity}
COLUMNS TO EXTRACT: {columns}

EXTRACTION RULES:
1. Each row = one distinct {row_entity} found in sources.
2. For each cell: extract the value AND cite its source [DocName, p.N].
3. "Not found" is correct and honest — do not invent.
4. If two chunks give different values for the same cell: mark as CONFLICT and show both values.
5. confidence:
   - "high": directly stated verbatim in source
   - "medium": implied or calculated from source
   - "low": inferred, may need verification

SOURCE CHUNKS:
{format_chunks_for_generation(chunks)}

Return JSON:
{{
  "title": "{table_title}",
  "columns": {json.dumps(columns)},
  "rows": [
    {{
      "entity": "<row identifier>",
      "cells": {{
        "<column_name>": {{
          "value": "<extracted value or Not found>",
          "citation": "<DocName, p.N or Not found>",
          "confidence": "<high|medium|low>",
          "conflict": <true|false>
        }}
      }}
    }}
  ],
  "extraction_notes": "<what was hard to extract or missing>",
  "doc_coverage": {{
    "<doc_name>": <number of rows this doc contributed>
  }}
}}
Return JSON only.
"""
    response = call_llm(system, user_prompt, llm_backend)
    data = parse_json(response)
    
    if not data:
        raise ValueError("Failed to extract table data.")

    # STEP 5 — Parse and return ExtractedTable
    rows = []
    for r_dict in data.get("rows", []):
        cells = {}
        for col, c_dict in r_dict.get("cells", {}).items():
            cells[col] = TableCell(
                value=c_dict.get("value", "Not found"),
                citation=c_dict.get("citation", "Not found"),
                confidence=c_dict.get("confidence", "low"),
                conflict=c_dict.get("conflict", False)
            )
        rows.append(TableRow(entity=r_dict.get("entity", "Unknown"), cells=cells))

    return ExtractedTable(
        title=data.get("title", table_title),
        columns=data.get("columns", columns),
        rows=rows,
        extraction_notes=data.get("extraction_notes", ""),
        doc_coverage=data.get("doc_coverage", {})
    )

def export_to_csv(
    table: ExtractedTable, 
    path: Path
) -> Path:
    """
    Exports an ExtractedTable to a CSV file formatted for easy consumption.
    """
    with open(path, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header Row
        header = ["Entity"] + table.columns + ["Citations"]
        writer.writerow(header)
        
        # Data Rows
        any_conflicts = False
        for row in table.rows:
            row_data = [row.entity]
            citations = []
            
            for col in table.columns:
                cell = row.cells.get(col)
                if cell:
                    val = cell.value
                    if cell.conflict:
                        val += "*"
                        any_conflicts = True
                    row_data.append(val)
                    if cell.citation and cell.citation != "Not found":
                        citations.append(f"{col}: {cell.citation}")
                else:
                    row_data.append("Not found")
            
            row_data.append("; ".join(citations))
            writer.writerow(row_data)
            
        # Footer for conflicts
        if any_conflicts:
            writer.writerow([])
            writer.writerow(["* = conflicting sources detected for this value"])
            
    return path

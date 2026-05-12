"""
app/studio/audio.py

Three-pass podcast script generation engine for the
AskMyPDF Audio Overview Studio feature.

Hosts:
  Alex   — warm, curious, accessible, loves analogies
  Jordan — analytical, precise, evidence-focused, skeptical

Backend: uses LLM_BACKEND env var (ollama / hf / gemini)
"""
import os
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from app.studio.engine import (
    retrieve_all_for_studio,
    analyze_corpus,
    format_chunks_for_generation,
    call_llm,
    CorpusProfile,
)
from app.retriever import retrieve, RetrievedChunk


# ─────────────────────────────────────────────────────────
# DATACLASSES
# ─────────────────────────────────────────────────────────

@dataclass
class DialogueTurn:
    speaker: str          # "Alex" or "Jordan"
    text: str             # what they say
    tone: str             # see tone options below
    pause_before_ms: int  # 0 = normal, 400 = topic shift,
                          # 800 = dramatic pause

@dataclass
class PodcastScript:
    title: str
    episode_tagline: str
    host_a: str                  # "Alex"
    host_b: str                  # "Jordan"
    turns: List[DialogueTurn]
    duration_estimate_mins: float
    chapters: List[Dict[str, Any]]   # [{title, start_turn_index}]
    sources_cited: List[str]


# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

def call_and_parse_json(
    system: str, user: str, backend: str
) -> Any:
    """Call LLM and parse JSON response. Retries once on failure."""
    response = call_llm(system, user, backend)
    try:
        clean = re.sub(r'```json\s*|\s*```', '', response).strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        retry_user = (
            "IMPORTANT: Return ONLY valid JSON — no prose, "
            "no markdown fences, no explanation.\n\n" + user
        )
        response2 = call_llm(system, retry_user, backend)
        clean2 = re.sub(r'```json\s*|\s*```', '', response2).strip()
        try:
            return json.loads(clean2)
        except json.JSONDecodeError as e:
            print(f"[audio.py] JSON parse failed twice: {e}\nRaw: {response2[:500]}")
            return None


def format_turns_for_review(turns: List[Dict]) -> str:
    """Format turns as a readable script block."""
    lines = []
    for i, t in enumerate(turns):
        speaker = t.get("speaker", "?")
        tone = t.get("tone", "neutral")
        text = t.get("text", "")
        lines.append(f"[{i}] {speaker.upper()} ({tone}): {text}")
    return "\n".join(lines)


def estimate_duration(turns: List[DialogueTurn]) -> float:
    """Estimate podcast duration in minutes (140 wpm speaking pace)."""
    total_words = sum(len(t.text.split()) for t in turns)
    total_pause_ms = sum(t.pause_before_ms for t in turns)
    return round((total_words / 140) + (total_pause_ms / 60000), 1)


def _build_turns(raw: Any) -> List[DialogueTurn]:
    """Safely convert raw JSON list to DialogueTurn objects."""
    if not isinstance(raw, list):
        return []
    turns = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        turns.append(DialogueTurn(
            speaker=item.get("speaker", "Alex"),
            text=item.get("text", ""),
            tone=item.get("tone", "thoughtful"),
            pause_before_ms=int(item.get("pause_before_ms", 0)),
        ))
    return turns


# ─────────────────────────────────────────────────────────
# MAIN GENERATION FUNCTION
# ─────────────────────────────────────────────────────────

def generate_podcast_script(
    doc_names: Optional[List[str]] = None,
    focus: Optional[str] = None,
    duration_mins: int = 8,
    llm_backend: str = "gemini",
) -> PodcastScript:
    """
    Three-pass podcast script generation:
      Pass 1 — Corpus analysis + story arc planning
      Pass 2 — Chapter-by-chapter dialogue generation
      Pass 3 — Quality/continuity polish pass
    """

    # ── PASS 1: Corpus Analysis & Arc Planning ────────────
    chunks = retrieve_all_for_studio(doc_names, max_chunks=40)
    if not chunks:
        raise ValueError("No documents indexed. Please ingest PDFs first.")

    profile = analyze_corpus(chunks, llm_backend)

    # Duration → turn count (≈ 8 sec avg per turn)
    target_turns = int((duration_mins * 60) / 8)

    arc_system = (
        "You are a podcast producer planning an episode structure. "
        "Return JSON only — no markdown, no prose."
    )
    arc_user = f"""
Plan a {duration_mins}-minute podcast episode about these documents.

HOSTS:
ALEX: Warm, intellectually curious, makes complex ideas accessible.
  Opens with "what's the big picture?" questions.
  Says things like "wait, that's fascinating" or "okay so help me understand..."
  Uses everyday analogies to explain technical concepts.

JORDAN: Analytically rigorous, gently skeptical, loves specific evidence.
  Asks "but what about..." and "so what does that actually mean for..."
  Cites specific page numbers and document names.
  Never lets vague claims slide without evidence.

DOCUMENT CONTENT:
Domain: {profile.domain}
Primary topics: {", ".join(profile.primary_topics)}
Has statistics: {profile.has_numbers}
Has timeline: {profile.has_dates}
Key terms: {", ".join(profile.key_terms[:10])}
Has conflicting sources: {profile.has_contradictions}

STRUCTURAL RULES:
- Target {target_turns} total turns
- Exactly 3-4 chapters/segments
- Chapter 1 (20%): Hook + orientation — "What are we even looking at?"
- Chapter 2 (35%): Deep dive — the most interesting finding or theme
- Chapter 3 (30%): Surprises, tensions, implications
- Chapter 4 (15%): Synthesis + open questions

MANDATORY MOMENTS (plan approximate turn index for each):
- wow_moment: one host shares a genuinely surprising finding
- pushback_turn: Jordan challenges Alex with specific evidence
- callback_turn: reference something said earlier in the episode
- analogy_turn: Alex explains something abstract with an everyday comparison
{"- contradiction_turn: the documents disagree on this point" if profile.has_contradictions else ""}

FOCUS: {focus or "the most compelling aspects of the uploaded documents"}

Return JSON only:
{{
  "episode_title": "<punchy title, not generic>",
  "episode_tagline": "<one sentence that would make someone want to listen>",
  "chapters": [
    {{
      "title": "<chapter name>",
      "purpose": "<what this chapter accomplishes narratively>",
      "turn_count": <int>,
      "start_turn_index": <int>,
      "key_points_to_cover": ["specific point 1", "specific point 2", "specific point 3"]
    }}
  ],
  "planned_moments": {{
    "wow_moment_turn": <int>,
    "pushback_turn": <int>,
    "callback_turn": <int>,
    "analogy_turn": <int>
  }},
  "sources_to_cite": ["doc_name_1", "doc_name_2"],
  "total_target_turns": {target_turns}
}}
"""

    arc = call_and_parse_json(arc_system, arc_user, llm_backend)
    if not arc:
        # Minimal fallback arc
        _fallback_chapters = [
            {"title": "What Are We Looking At?", "purpose": "Orient listeners", "turn_count": 12,
             "start_turn_index": 0, "key_points_to_cover": profile.primary_topics[:3]},
            {"title": "The Key Finding", "purpose": "Deep dive", "turn_count": 20,
             "start_turn_index": 12, "key_points_to_cover": profile.primary_topics[1:4]},
            {"title": "What This Means", "purpose": "Implications", "turn_count": 15,
             "start_turn_index": 32, "key_points_to_cover": ["implications", "open questions"]},
        ]
        arc = {
            "episode_title": "Inside the Documents",
            "episode_tagline": "A deep dive into what these documents actually say.",
            "chapters": _fallback_chapters,
            "planned_moments": {"wow_moment_turn": 15, "pushback_turn": 22,
                                "callback_turn": 35, "analogy_turn": 10},
            "sources_to_cite": profile.doc_names[:3],
            "total_target_turns": target_turns,
        }

    # ── PASS 2: Chapter-by-chapter dialogue generation ────
    all_turns_raw: List[Dict] = []
    prev_chapter_summary = ""

    dialogue_system = (
        "You are writing a natural podcast dialogue between two hosts. "
        "Write flowing conversation — NOT a script with stage directions. "
        "Return a JSON array only — no markdown fences, no prose."
    )

    for i, chapter in enumerate(arc.get("chapters", [])):
        # Targeted retrieval for this chapter's topics
        chapter_query = " ".join(chapter.get("key_points_to_cover", ["overview"]))
        chapter_chunks = retrieve(chapter_query, reranker_top_k=8)
        chapter_chunks = chapter_chunks or chunks[:8]

        # Which planned moments fall in this chapter?
        c_start = chapter.get("start_turn_index", 0)
        c_count = chapter.get("turn_count", 15)
        c_end = c_start + c_count
        moments_in_chapter = {
            k: v for k, v in arc.get("planned_moments", {}).items()
            if c_start <= v < c_end
        }

        dialogue_user = f"""
Write Chapter {i+1} of this podcast episode: "{chapter['title']}"

PURPOSE: {chapter['purpose']}
TARGET TURNS: {chapter['turn_count']} (aim for this, ±3 is fine)

HOSTS:
ALEX — warm, curious, uses analogies, accessible language.
  Opening moves: "Okay so I want to start with...", "What really got me was...",
  "It's almost like..."
  Acknowledgments: "Right,", "Yeah,", "Wow,", "Huh."
  Can leave sentences unfinished for Jordan to complete.

JORDAN — analytical, precise, evidence-focused.
  Opening moves: "But here's the thing —", "What the document actually says is...",
  "I want to push back a little on that because..."
  Acknowledgments: "Mm,", "Exactly.", "So,", "Right."
  Must cite specific page numbers and document names at least 2-3 times.

PREVIOUS CHAPTER ENDING (maintain continuity):
{prev_chapter_summary or "This is the opening chapter — hook the listener immediately."}

SOURCE EVIDENCE TO DRAW FROM:
{format_chunks_for_generation(chapter_chunks)}

SPECIAL MOMENTS TO INCLUDE IN THIS CHAPTER:
{json.dumps(moments_in_chapter, indent=2) if moments_in_chapter else "None specifically planned — keep it natural."}

CONVERSATION RULES:
1. Turns alternate A→B→A→B but 2 consecutive turns from one host is fine when on a roll
2. Average turn: 1-3 sentences. Short turns ("Right." "Wait, really?") are encouraged.
3. Reference sources naturally: "According to the [doc name]..." or "On page [N] it says..."
   NOT: "As cited in SOURCE [1]..."
4. Natural speech: incomplete sentences the other host finishes are ALLOWED
5. Hosts must express genuine emotion — surprise, concern, delight, skepticism —
   anchored to SPECIFIC content, not generic reactions
6. Include at least one verbal interruption or sentence-completion between hosts
7. This chapter must END with a natural pivot line that leads into the next topic

DOC NAMES AVAILABLE: {", ".join(profile.doc_names)}

Return a JSON array of turns (no other text):
[
  {{
    "speaker": "Alex",
    "text": "what they say — complete natural speech",
    "tone": "curious",
    "pause_before_ms": 0
  }},
  ...
]
Valid tone values: curious | excited | thoughtful | surprised | analytical | warm | skeptical | explanatory
Valid pause_before_ms values: 0 (normal), 400 (topic shift), 800 (dramatic pause)
"""

        chapter_raw = call_and_parse_json(dialogue_system, dialogue_user, llm_backend)
        if isinstance(chapter_raw, list):
            all_turns_raw.extend(chapter_raw)
            # Build prev_chapter_summary from last 5 turns
            last_five = chapter_raw[-5:]
            prev_chapter_summary = "\n".join(
                f"{t.get('speaker','?')}: {t.get('text','')}"
                for t in last_five
            )

    if not all_turns_raw:
        raise ValueError("Script generation produced no dialogue turns.")

    # ── PASS 3: Quality polish pass ───────────────────────
    polish_system = (
        "You are a senior podcast editor reviewing a script for quality and naturalness. "
        "Return ONLY the complete edited JSON array — no prose, no markdown."
    )
    polish_user = f"""
Review and polish this {len(all_turns_raw)}-turn podcast script.

FULL SCRIPT:
{format_turns_for_review(all_turns_raw)}

QUALITY CHECKS — apply ALL of these:
1. Does turn 0 hook the listener immediately? If not, rewrite it to open with a compelling question or surprising statement.
2. Do the last 3 turns synthesize well and end satisfyingly? If not, rewrite them.
3. Are there 3+ consecutive turns from the same speaker? Fix by inserting a short acknowledgment.
4. Does any single turn exceed 5 sentences? Split it into 2 turns.
5. Does each chapter feel like a distinct segment? Add a brief pivot line between chapters if needed.
6. Are there at least 3 specific document/page citations from Jordan across the whole script? Add them if missing.
7. Does Alex use at least one everyday analogy to explain something? Add one if missing.
8. Do the hosts express at least 3 distinct emotional reactions (surprise, concern, delight, etc.) anchored to specific content?

Return the COMPLETE edited script as a JSON array with ALL turns (same structure).
Do NOT truncate. Include all {len(all_turns_raw)} turns or more if you added transitions.

[
  {{"speaker": "Alex"|"Jordan", "text": "...", "tone": "...", "pause_before_ms": 0|400|800}},
  ...
]
"""

    final_raw = call_and_parse_json(polish_system, polish_user, llm_backend)

    # Fall back to unpolished if polish pass fails
    if not isinstance(final_raw, list) or len(final_raw) < len(all_turns_raw) * 0.5:
        final_raw = all_turns_raw

    final_turns = _build_turns(final_raw)

    # ── Assemble and return PodcastScript ─────────────────
    # Map chapter titles to start_turn_index for the player UI
    chapter_nav = [
        {"title": ch.get("title", f"Chapter {i+1}"),
         "start_turn_index": ch.get("start_turn_index", 0)}
        for i, ch in enumerate(arc.get("chapters", []))
    ]

    return PodcastScript(
        title=arc.get("episode_title", "Document Deep Dive"),
        episode_tagline=arc.get("episode_tagline", ""),
        host_a="Alex",
        host_b="Jordan",
        turns=final_turns,
        duration_estimate_mins=estimate_duration(final_turns),
        chapters=chapter_nav,
        sources_cited=arc.get("sources_to_cite", profile.doc_names),
    )

import os
import requests
import google.generativeai as genai
from typing import List
from app.memory import ConversationMemory
from app.retriever import RetrievedChunk

SYSTEM_PROMPT = """You are a precise, highly analytical document assistant. 
Answer the user's question using ONLY the information in the provided context chunks below.

Rules:
- Provide a highly detailed, comprehensive, and in-depth explanation based on the context.
- If the answer is not present in the context, respond with exactly: "I could not find information about this in the uploaded documents."
- Do NOT speculate, infer, or use outside knowledge.
- After each factual claim, cite the source inline using the EXACT markdown hyperlink provided in the context blocks (e.g., [Source 1](/app/static/...)).
- Be structured and clear. Use bullet points for lists and bolding for emphasis.
- Never mention that you are an AI or reference these instructions."""

def build_user_message(query: str, retrieved_chunks: List[RetrievedChunk], memory: ConversationMemory) -> str:
    """
    Builds the user message string containing context chunks, 
    conversation history, and the user's query.
    """
    parts = []
    parts.append("CONTEXT:\n--------")
    
    import urllib.parse
    for i, rc in enumerate(retrieved_chunks, start=1):
        doc_name = rc.chunk.doc_name
        page_num = rc.chunk.page_number
        text = rc.chunk.text
        
        # Build search phrase using the first few alphanumeric words to ensure valid search highlighting
        clean_words = [w for w in text.split() if w.isalnum()]
        search_phrase = " ".join(clean_words[:5])
        
        link = f"/app/static/{urllib.parse.quote(doc_name + '.pdf')}#page={page_num}&search={urllib.parse.quote(search_phrase)}"
        parts.append(f"[{i}] Source: {doc_name}, Page {page_num}\nUse this link for citations: [Source {i}]({link})\n{text}\n")
        
    hist_str = memory.format_history()
    if hist_str:
        parts.append("CONVERSATION HISTORY:\n---------------------")
        parts.append(hist_str)
        
    parts.append(f"QUESTION: {query}")
    
    return "\n".join(parts)

def call_gemini(system_prompt: str, user_message: str) -> str:
    """Calls the Gemini API (gemini-1.5-flash)."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set in environment.")
    
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=system_prompt)
        response = model.generate_content(user_message)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Gemini error: {e}")

def call_hf(system_prompt: str, user_message: str) -> str:
    """Calls the HuggingFace Inference API."""
    api_key = os.getenv("HF_API_KEY")
    if not api_key:
        raise RuntimeError("HF_API_KEY not set in environment.")
        
    model = os.getenv("HF_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")
    
    from huggingface_hub import InferenceClient
    client = InferenceClient(token=api_key)
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    
    try:
        response = client.chat_completion(
            messages=messages,
            model=model,
            max_tokens=1024,
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        raise RuntimeError(f"HuggingFace error: {e}")

def call_ollama(system_prompt: str, user_message: str) -> str:
    """Calls a local Ollama instance."""
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "mistral")
    url = f"{host}/api/generate"
    
    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": user_message,
        "stream": False
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["response"]
    except requests.ConnectionError:
        raise RuntimeError("Cannot connect to Ollama. Is it running? Start with: ollama serve")
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")

def generate(query: str, retrieved_chunks: List[RetrievedChunk], memory: ConversationMemory, backend: str = None) -> str:
    """
    Main entrypoint for answer generation. Routes to the appropriate LLM backend.
    """
    backend = backend or os.getenv("LLM_BACKEND", "gemini")
    user_message = build_user_message(query, retrieved_chunks, memory)
    
    if backend == "gemini":
        return call_gemini(SYSTEM_PROMPT, user_message)
    elif backend == "hf":
        return call_hf(SYSTEM_PROMPT, user_message)
    elif backend == "ollama":
        return call_ollama(SYSTEM_PROMPT, user_message)
    else:
        raise ValueError(f"Unknown backend: {backend}. Choose: gemini, hf, ollama")

def generate_custom(system_prompt: str, user_message: str, backend: str = None) -> str:
    """Raw generation endpoint for specialized tasks."""
    backend = backend or os.getenv("LLM_BACKEND", "gemini")
    if backend == "gemini":
        return call_gemini(system_prompt, user_message)
    elif backend == "hf":
        return call_hf(system_prompt, user_message)
    elif backend == "ollama":
        return call_ollama(system_prompt, user_message)
    else:
        raise ValueError(f"Unknown backend: {backend}. Choose: gemini, hf, ollama")

def generate_quiz(retrieved_chunks: List[RetrievedChunk], backend: str, difficulty: str) -> str:
    if not retrieved_chunks:
        return "[]"
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    diff_focus = {
        "Beginner": "Focus on explicit definitions and facts.",
        "Intermediate": "Focus on relationships between concepts.",
        "Advanced": "Focus on synthesis and scenario application."
    }.get(difficulty, "Focus on general facts.")
    
    sys_prompt = "You are an expert educator. Return ONLY valid JSON array with NO markdown blocks."
    user_msg = f"""{diff_focus} Based ONLY on the following context, generate 3 multiple-choice questions.
Schema required: [{{ "question": "...", "options": ["A", "B", "C", "D"], "answer": "correct option", "explanation": "..." }}]
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def generate_flashcards(retrieved_chunks: List[RetrievedChunk], backend: str) -> str:
    if not retrieved_chunks:
        return "[]"
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are an expert tutor. Return ONLY a valid JSON array with NO markdown blocks."
    user_msg = f"""Extract 5 to 10 key terms from the context.
Schema required: [{{ "front": "term", "back": "definition" }}]
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def generate_report(retrieved_chunks: List[RetrievedChunk], backend: str) -> str:
    if not retrieved_chunks:
        return "No context available."
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are an executive analyst."
    user_msg = f"""Synthesize the provided context into a structured markdown report.
MUST include exactly these headers:
# Executive Summary
# Key Findings
# Conclusion
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def generate_data_table(retrieved_chunks: List[RetrievedChunk], backend: str) -> str:
    if not retrieved_chunks:
        return "No data available."
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are a data extraction bot."
    user_msg = f"""Extract all quantitative data, metrics, and relationships from the context into a structured markdown table.
Return ONLY the markdown table. If no quantitative data is found, return exactly 'No quantitative data found'.
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def generate_slides_json(retrieved_chunks: List[RetrievedChunk], backend: str, num_slides: int) -> str:
    if not retrieved_chunks:
        return "[]"
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are a professional presentation designer."
    user_msg = f"""Based on the context, generate exactly {num_slides} presentation slides.
Return ONLY a valid JSON array of objects. Do not include markdown blocks.
Schema required: [{{ "title": "...", "subtitle": "...", "bullets": ["...", "...", "..."], "visual_suggestion": "..." }}]
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def generate_mindmap_json(retrieved_chunks: List[RetrievedChunk], backend: str) -> str:
    if not retrieved_chunks:
        return "{}"
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are an expert knowledge graph extractor."
    user_msg = f"""Extract a hierarchical tree of core concepts from the context.
Return ONLY a valid JSON object with NO markdown formatting.
Schema required: 
{{
  "nodes": [{{ "id": "1", "label": "Concept", "title": "Details on hover" }}],
  "edges": [{{ "source": "1", "target": "2", "label": "relationship" }}]
}}
Limit to exactly 15 nodes and their critical edges.
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def generate_hyde_document(query: str, backend: str = None) -> str:
    """Generates a hypothetical document (answer) to improve semantic retrieval recall."""
    sys_prompt = "You are a knowledgeable assistant. Provide a direct, factual hypothetical answer."
    user_msg = f"Write a short, factual passage that directly answers this question. Do not include introductory filler. Write it as if it were an excerpt from a textbook or professional document.\\nQuestion: {query}"
    return generate_custom(sys_prompt, user_msg, backend)

def decompose_query(query: str, backend: str = None) -> List[str]:
    """Decomposes a complex query into simpler sub-queries for broader retrieval."""
    sys_prompt = "You are a query analysis agent. Return ONLY a valid JSON array of strings, no markdown blocks."
    user_msg = f"""Analyze this query. If it asks multiple distinct questions or requires retrieving from different conceptual areas, break it down into 2 to 4 simple, independent sub-queries.
If it is a simple single question, just return the original query in the array.
Schema required: ["query 1", "query 2"]
Query: {query}"""
    try:
        import json
        resp = generate_custom(sys_prompt, user_msg, backend)
        parsed = json.loads(resp.replace('```json', '').replace('```', '').strip())
        if isinstance(parsed, list) and len(parsed) > 0:
            return [str(q) for q in parsed[:4]]
        return [query]
    except Exception as e:
        print(f"Query decomposition failed: {e}")
        return [query]

def generate_podcast_script(retrieved_chunks: List[RetrievedChunk], backend: str, length_type: str) -> str:
    if not retrieved_chunks:
        return "[]"
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are a professional podcast playwright. Return ONLY a valid JSON array with NO markdown blocks."
    user_msg = f"""Write a conversational podcast transcript based ONLY on the following context.
There are two hosts:
Host 1: enthusiastic explainer
Host 2: curious skeptic

The podcast should be '{length_type}' length.
Limit the script STRICTLY to the uploaded document content.
Schema required: [{{"host": "1", "text": "..."}}, {{"host": "2", "text": "..."}}]
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def synthesize_audio(script_json: str) -> bytes:
    import json
    import os
    import io
    import tempfile
    import subprocess
    from pydub import AudioSegment

    try:
        dialogues = json.loads(script_json.replace('```json', '').replace('```', '').strip())
    except Exception:
        dialogues = []

    # Voice mapping for Edge TTS (100% Free, no API key needed)
    # Host 1: Christopher (Male, American), Host 2: Jenny (Female, American)
    voice_map = {
        "1": "en-US-ChristopherNeural",
        "2": "en-US-JennyNeural"
    }
    
    combined_audio = AudioSegment.empty()
    
    for line in dialogues:
        text = line.get("text", "")
        if not text.strip():
            continue
            
        voice_id = voice_map.get(str(line.get("host")), "en-US-ChristopherNeural")
        
        # edge-tts saves to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
            tmp_path = tmp_file.name
            
        try:
            # Call edge-tts CLI synchronously (avoids Streamlit asyncio loop issues)
            subprocess.run([
                "edge-tts", 
                "--voice", voice_id, 
                "--text", text, 
                "--write-media", tmp_path
            ], check=True, capture_output=True)
            
            audio_segment = AudioSegment.from_file(tmp_path, format="mp3")
            combined_audio += audio_segment
        except subprocess.CalledProcessError as e:
            raise ValueError(f"Edge-TTS failed. Please make sure edge-tts is installed. Error: {e.stderr.decode()}")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            
    out_f = io.BytesIO()
    if len(combined_audio) > 0:
        combined_audio.export(out_f, format="mp3")
    return out_f.getvalue()

def generate_video_script(retrieved_chunks: List[RetrievedChunk], backend: str) -> str:
    if not retrieved_chunks:
        return "No script."
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are a concise video scriptwriter."
    user_msg = f"""Write a 60-second video script with scene descriptions based ONLY on the context.
Provide the spoken text. Return ONLY the spoken script text without any scene directions so it can be passed directly to an avatar API.
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def generate_video(script_text: str, avatar_style: str) -> str:
    import requests
    import os
    import time
    
    api_key = os.getenv("HEYGEN_API_KEY")
    if not api_key:
        raise ValueError("HEYGEN_API_KEY is not set.")
        
    headers = {
        "X-Api-Key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "video_inputs": [
            {
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_style,
                    "avatar_style": "normal"
                },
                "voice": {
                    "type": "text",
                    "input_text": script_text,
                    "voice_id": "1bd001e7e50f421d891986aad5158bc8"
                }
            }
        ],
        "test": True
    }
    resp = requests.post("https://api.heygen.com/v2/video/generate", json=payload, headers=headers)
    if resp.status_code != 200:
        raise ValueError(f"HeyGen generate error: {resp.text}")
        
    video_id = resp.json()["data"]["video_id"]
    
    while True:
        status_resp = requests.get(f"https://api.heygen.com/v1/video_status.get?video_id={video_id}", headers=headers)
        if status_resp.status_code == 200:
            status_data = status_resp.json()["data"]
            if status_data["status"] == "completed":
                return status_data["video_url"]
            elif status_data["status"] in ["failed", "error"]:
                raise ValueError("Video generation failed.")
        time.sleep(5)

def generate_infographic_concepts(retrieved_chunks: List[RetrievedChunk], backend: str) -> str:
    if not retrieved_chunks:
        return "[]"
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are a data visualization expert. Return ONLY a valid JSON array of strings."
    user_msg = f"""Distill the following context into 5 distinct "Infographic Concepts" (e.g., Timeline, Process Flow, Comparison).
Schema required: ["Concept 1", "Concept 2", "Concept 3", "Concept 4", "Concept 5"]
Context:
{context}"""
    return generate_custom(sys_prompt, user_msg, backend)

def generate_svg(concept: str, retrieved_chunks: List[RetrievedChunk], backend: str) -> str:
    context = "\\n".join([rc.chunk.text for rc in retrieved_chunks])
    sys_prompt = "You are an expert SVG designer. Return ONLY the raw SVG code, with NO markdown formatting, NO html tags around it."
    user_msg = f"""Generate the raw SVG markup for the following infographic concept: '{concept}'
Make it visually appealing, with a viewBox and standard colors. Include the relevant text from the context. Do not wrap in markdown or ```svg.
Context:
{context}"""
    svg_code = generate_custom(sys_prompt, user_msg, backend)
    return svg_code.replace("```xml", "").replace("```svg", "").replace("```html", "").replace("```", "").strip()

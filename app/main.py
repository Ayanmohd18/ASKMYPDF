import streamlit as st
import os
from pathlib import Path
from dotenv import load_dotenv
from app.styles import get_css
from app.ingestion import ingest_file as ingest_pdf
from app.vector_store import (initialize, add_chunks, 
  get_all_doc_names, get_chunk_count, clear)
from app.retriever import retrieve
from app.generator import generate
from app.memory import ConversationMemory
from app.monitor import get_stats, get_tracker
import tempfile
import datetime

load_dotenv()

# ─── PAGE CONFIG (MUST BE FIRST ST CALL) ────────────────

st.set_page_config(
    page_title="AskMyPDF",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── SESSION STATE INITIALIZATION ───────────────────────

if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False
if "messages" not in st.session_state:
    st.session_state.messages = []
if "memory" not in st.session_state:
    st.session_state.memory = ConversationMemory()
if "backend" not in st.session_state:
    st.session_state.backend = os.getenv("LLM_BACKEND", "gemini")
if "ingested_docs" not in st.session_state:
    st.session_state.ingested_docs = {}
    for doc in get_all_doc_names():
        st.session_state.ingested_docs[doc] = {
            "chunks": "Disk",
            "timestamp": "Pre-existing"
        }
if "last_latency" not in st.session_state:
    st.session_state.last_latency = 0.0
if "index_initialized" not in st.session_state:
    st.session_state.index_initialized = False

# ─── INJECT CSS ─────────────────────────────────────────

st.markdown(
  f"<style>{get_css(st.session_state.dark_mode)}</style>",
  unsafe_allow_html=True
)

# ─── INITIALIZE VECTOR STORE ────────────────────────────

if not st.session_state.index_initialized:
    index_dir = Path(os.getenv("INDEX_DIR","data/indexes"))
    index_dir.mkdir(parents=True, exist_ok=True)
    initialize(index_dir)
    st.session_state.index_initialized = True

# ═══════════════════════════════════
# SIDEBAR LAYOUT
# ═══════════════════════════════════

# ─── TOP: LOGO + DARK MODE TOGGLE ───────────────────────

st.sidebar.markdown("""
<div style="
  background: linear-gradient(135deg, 
    var(--accent-primary), var(--accent-secondary));
  padding: 20px 20px 16px;
  margin: -1rem -1rem 0;
">
  <div style="
    font-family: 'DM Serif Display', serif;
    font-size: 22px;
    color: white;
    letter-spacing: -0.3px;
  ">AskMyPDF</div>
  <div style="
    font-size: 11px;
    color: rgba(255,255,255,0.75);
    margin-top: 2px;
    font-family: 'DM Sans', sans-serif;
  ">Your documents. Your answers.</div>
</div>
""", unsafe_allow_html=True)

col1, col2 = st.sidebar.columns([3,1])
col1.markdown('<div class="sidebar-label" style="margin-top:16px;">APPEARANCE</div>', unsafe_allow_html=True)
dark_toggle = col2.toggle("🌙", 
  value=st.session_state.dark_mode,
  key="dark_toggle",
  label_visibility="collapsed")

if dark_toggle != st.session_state.dark_mode:
    st.session_state.dark_mode = dark_toggle
    st.rerun()

# ─── SECTION: UPLOAD ────────────────────────────────────

st.sidebar.markdown(
  '<div class="sidebar-label" style="margin-top:16px;">DOCUMENTS</div>',
  unsafe_allow_html=True
)

uploaded_files = st.sidebar.file_uploader(
  "Upload PDFs",
  type=["pdf", "docx", "txt"],
  accept_multiple_files=True,
  label_visibility="collapsed"
)

ingest_btn = st.sidebar.button(
  "⚙️  Ingest Documents",
  use_container_width=True,
  type="primary",
  disabled=(not uploaded_files)
)

if ingest_btn and uploaded_files:
    progress = st.sidebar.progress(0, "Starting...")
    all_new_chunks = []
    for i, f in enumerate(uploaded_files):
        doc_name = Path(f.name).stem
        progress.progress(
          (i / len(uploaded_files)),
          f"Processing {doc_name}..."
        )
        suffix = Path(f.name).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(f.read())
            tmp_path = Path(tmp.name)
        try:
            chunks = ingest_pdf(tmp_path)
            all_new_chunks.extend(chunks)
            st.session_state.ingested_docs[doc_name] = {
                "chunks": len(chunks),
                "timestamp": datetime.datetime.now().strftime("%H:%M %d %b")
            }
        except Exception as e:
            st.sidebar.error(f"Failed: {doc_name} — {e}")
        finally:
            tmp_path.unlink(missing_ok=True)
  
    if all_new_chunks:
        add_chunks(all_new_chunks)
        progress.progress(1.0, "Complete!")
        st.sidebar.success(
            f"✓ {len(all_new_chunks)} chunks indexed "
            f"from {len(uploaded_files)} file(s)"
        )
        st.rerun()

# ─── SECTION: INDEXED DOCS ──────────────────────────────

if st.session_state.ingested_docs:
    st.sidebar.markdown(
      '<div class="sidebar-label" style="margin-top:16px;">INDEXED</div>',
      unsafe_allow_html=True
    )
  
    for doc_name, info in st.session_state.ingested_docs.items():
        st.sidebar.markdown(f"""
        <div class="doc-card fade-in">
          <div class="doc-card-title">📄 {doc_name}</div>
          <div class="doc-card-meta">
            {info['chunks']} chunks · {info['timestamp']}
          </div>
        </div>
        """, unsafe_allow_html=True)
  
    if len(st.session_state.ingested_docs) > 0:
        clear_btn = st.sidebar.button(
          "🗑️  Clear All",
          use_container_width=True,
          type="secondary"
        )
        if clear_btn:
            clear()
            st.session_state.ingested_docs = {}
            st.session_state.messages = []
            st.session_state.memory.clear()
            st.rerun()

# ─── SECTION: BACKEND ───────────────────────────────────

st.sidebar.divider()
st.sidebar.markdown(
  '<div class="sidebar-label">LLM BACKEND</div>',
  unsafe_allow_html=True
)

backend_icons = {
  "gemini": "✦ Gemini Flash",
  "hf": "🤗 HuggingFace",
  "ollama": "⬡ Ollama (Offline)"
}

selected = st.sidebar.radio(
  "Backend",
  options=list(backend_icons.keys()),
  format_func=lambda x: backend_icons[x],
  index=["gemini","hf","ollama"].index(st.session_state.backend) if st.session_state.backend in ["gemini","hf","ollama"] else 0,
  label_visibility="collapsed"
)
st.session_state.backend = selected

# ─── SECTION: SYSTEM MONITOR ────────────────────────────

st.sidebar.divider()
st.sidebar.markdown(
  '<div class="sidebar-label">SYSTEM</div>',
  unsafe_allow_html=True
)

stats = get_stats()
c1, c2, c3 = st.sidebar.columns(3)
c1.metric("CPU", f"{stats.cpu_percent:.0f}%")
c2.metric("RAM", f"{stats.ram_used_mb:.0f}m")
c3.metric("⏱", f"{st.session_state.last_latency:.1f}s")

# ═══════════════════════════════════
# MAIN AREA LAYOUT
# ═══════════════════════════════════

# ─── TOP BAR ────────────────────────────────────────────

top_left, top_right = st.columns([5, 1])

with top_left:
    if get_chunk_count() > 0:
        st.markdown(
          f'<div style="font-family:\'DM Serif Display\',serif;'
          f'font-size:28px;color:var(--text-primary);">'
          f'Research Workspace</div>'
          f'<div style="font-size:13px;color:var(--text-muted);'
          f'margin-top:2px;">'
          f'{len(st.session_state.ingested_docs)} document(s) · '
          f'{get_chunk_count()} indexed chunks</div>',
          unsafe_allow_html=True
        )
    else:
        st.markdown(
          '<div style="font-family:\'DM Serif Display\',serif;'
          'font-size:28px;color:var(--text-primary);">'
          'AskMyPDF</div>',
          unsafe_allow_html=True
        )

with top_right:
    if st.session_state.messages:
        clear_btn = st.button("Clear chat", type="secondary")
        if clear_btn:
            st.session_state.messages = []
            st.session_state.memory.clear()
            st.rerun()

# ─── EMPTY STATE ────────────────────────────────────────

if get_chunk_count() == 0 and not st.session_state.messages:
  
    st.markdown("""
    <div class="empty-state fade-in">
      <div class="empty-state-icon">📄</div>
      <div class="empty-state-title">
        No documents yet
      </div>
      <div class="empty-state-body">
        Upload PDFs using the sidebar to get started. 
        Ask questions, get cited answers, and explore 
        your documents in conversation.
      </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show 3 example query chips as inspiration
    st.markdown('<div style="text-align:center;'
      'margin-top:24px;">', unsafe_allow_html=True)
    
    example_queries = [
      "What are the key payment terms?",
      "Summarize the liability clauses",
      "When does this agreement terminate?"
    ]
    
    cols = st.columns(3)
    for i, q in enumerate(example_queries):
        with cols[i]:
            st.markdown(
              f'<div style="background:var(--bg-card);'
              f'border:1px solid var(--border);'
              f'border-radius:10px;padding:12px 14px;'
              f'text-align:center;font-size:13px;'
              f'color:var(--text-secondary);'
              f'font-style:italic;">"{q}"</div>',
              unsafe_allow_html=True
            )
    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════
# HELPER — render_source_cards()
# ═══════════════════════════════════

def render_source_cards(results: list):
    if not results: return
    
    st.markdown(
      '<div style="margin-top:12px;margin-bottom:4px;'
      'font-size:11px;text-transform:uppercase;'
      'letter-spacing:0.08em;color:var(--text-muted);'
      'font-family:\'DM Sans\',sans-serif;">'
      '📎 Sources</div>',
      unsafe_allow_html=True
    )
    
    for i, result in enumerate(results):
        chunk = result.chunk
        excerpt = chunk.text[:280].replace('"', '\\"')
        if len(chunk.text) > 280:
            excerpt += "..."
        
        # Relevance bar: convert reranker score to 0-100%
        # reranker scores typically -5 to +5, sigmoid-ish
        # Clamp to 0-1: rel = max(0, min(1, (score+3)/6))
        rel = max(0, min(1, (result.reranker_score + 3) / 6))
        rel_pct = int(rel * 100)
        rel_color = ("#1A7A6E" if rel > 0.6 
                     else "#D4825A" if rel > 0.3 
                     else "#9E9893")
        
        card_html = f"""
        <div class="source-card fade-in">
          <div class="source-card-header">
            <span class="score-pill">{rel_pct}%</span>
            {chunk.doc_name}
            <span style="color:var(--text-muted);
              margin-left:6px;">· p.{chunk.page_number}</span>
          </div>
          <div style="
            display:flex;
            align-items:center;
            gap:8px;
            margin:8px 0 10px;
            font-size:11px;
            font-family:'JetBrains Mono',monospace;
            color:var(--text-muted);
          ">
            <span>FAISS {result.faiss_score:.3f}</span>
            <span>·</span>
            <span>BM25 {result.bm25_score:.3f}</span>
            <span>·</span>
            <span>Rerank {result.reranker_score:.3f}</span>
          </div>
          <div style="
            height:3px;
            background:var(--border);
            border-radius:2px;
            margin-bottom:10px;
          ">
            <div style="
              height:100%;
              width:{rel_pct}%;
              background:{rel_color};
              border-radius:2px;
              transition:width 0.4s ease;
            "></div>
          </div>
          <div class="source-excerpt">
            {excerpt}
          </div>
        </div>
        """
        
        st.markdown(card_html, unsafe_allow_html=True)

col_chat, col_studio = st.columns([5, 3])

with col_chat:
    # ─── CHAT HISTORY ───────────────────────────────────────

    chat_container = st.container()

    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
                if msg["role"] == "assistant" and msg.get("sources"):
                    render_source_cards(msg["sources"])

    # ─── CHAT INPUT ─────────────────────────────────────────

    if get_chunk_count() > 0:
        query = st.chat_input("Ask anything about your documents...")
    else:
        query = st.chat_input("Upload documents first to begin...", disabled=True)

    if query:
        st.session_state.messages.append({
            "role": "user", "content": query, "sources": []
        })
        
        with st.chat_message("user"):
            st.markdown(query)
        
        with st.chat_message("assistant"):
            with st.spinner(""):
                tracker = get_tracker()
                tracker.start()
                try:
                    results = retrieve(
                        query,
                        reranker_top_k=int(os.getenv("RERANKER_TOP_K", 5))
                    )
                    answer = generate(
                        query, results,
                        st.session_state.memory,
                        backend=st.session_state.backend
                    )
                    latency = tracker.stop()
                    st.session_state.last_latency = latency
                    
                    st.session_state.memory.add_user(query)
                    st.session_state.memory.add_assistant(answer)
                    
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": answer,
                        "sources": results
                    })
                    
                    st.markdown(answer)
                    render_source_cards(results)
                    
                except ValueError as e:
                    st.warning(str(e))
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": str(e),
                        "sources": []
                    })
                except Exception as e:
                    st.error(f"Something went wrong: {e}")
        
        st.rerun()


with col_studio:
    st.markdown(
      f'<div style="font-family:\'DM Serif Display\',serif;'
      f'font-size:28px;color:var(--text-primary);">'
      f'Studio</div>'
      f'<div style="font-size:13px;color:var(--text-muted);'
      f'margin-top:2px;">'
      f'AI Generated Assets</div>',
      unsafe_allow_html=True
    )
    
    tab_audio, tab_slide, tab_mindmap, tab_report, tab_flashcard, tab_quiz, tab_info, tab_data = st.tabs([
        "Audio", "Slides", "Mind Map", "Reports", "Flashcards", "Quiz", "Infographics", "Data"
    ])
    
    with tab_audio:
        st.subheader("Podcast Generation")
        col1, col2 = st.columns(2)
        podcast_length = None
        if col1.button("🎙️ Crispy Response (3-10 mins)"):
            podcast_length = "Crispy Response"
        if col2.button("🎙️ In-Depth Response (5-15 mins)"):
            podcast_length = "In-Depth Response"
            
        if podcast_length:
            if not st.session_state.ingested_docs:
                st.warning("Please index documents first.")
            else:
                with st.spinner(f"Generating {podcast_length} podcast script..."):
                    try:
                        results = retrieve("Extract main topics for a comprehensive podcast.", reranker_top_k=20)
                        script_json = generator.generate_podcast_script(results, st.session_state.backend, podcast_length)
                        
                        st.info("Script generated. Synthesizing audio via ElevenLabs...")
                        audio_bytes = generator.synthesize_audio(script_json)
                        st.session_state["podcast_audio"] = audio_bytes
                        st.success("Podcast ready!")
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
        if "podcast_audio" in st.session_state:
            st.audio(st.session_state["podcast_audio"], format="audio/mp3")
    with tab_slide:
        st.subheader("Presentation Generator")
        num_slides = st.radio("Number of Slides:", [10, 15, 20], horizontal=True)
        template = st.selectbox("Aesthetic Template:", ["Corporate", "Creative", "Minimalist", "Dark Mode"])
        color_palette = st.color_picker("Primary Accent Color", "#0052cc")
        
        if st.button("Generate Slide Deck"):
            if not st.session_state.ingested_docs:
                st.warning("Please index documents first.")
            else:
                with st.spinner("Designing presentation..."):
                    try:
                        results = retrieve("Extract main topics for a comprehensive presentation.", reranker_top_k=20)
                        import json
                        slides_json_str = generator.generate_slides_json(results, st.session_state.backend, num_slides)
                        slides_data = json.loads(slides_json_str.replace('```json', '').replace('```', '').strip())
                        
                        from pptx import Presentation
                        from pptx.util import Inches, Pt
                        from pptx.dml.color import RGBColor
                        
                        prs = Presentation()
                        
                        hex_color = color_palette.lstrip('#')
                        rgb_accent = RGBColor(int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
                        
                        for slide_data in slides_data:
                            slide_layout = prs.slide_layouts[1]
                            slide = prs.slides.add_slide(slide_layout)
                            
                            if template == "Dark Mode":
                                background = slide.background
                                fill = background.fill
                                fill.solid()
                                fill.fore_color.rgb = RGBColor(30, 30, 30)
                                
                            title_shape = slide.shapes.title
                            body_shape = slide.placeholders[1]
                            
                            title_shape.text = slide_data.get("title", "")
                            for p in title_shape.text_frame.paragraphs:
                                p.font.color.rgb = rgb_accent
                                if template == "Dark Mode":
                                    p.font.color.rgb = RGBColor(255, 255, 255)
                                    
                            tf = body_shape.text_frame
                            tf.text = slide_data.get("subtitle", "")
                            
                            for bullet in slide_data.get("bullets", []):
                                p = tf.add_paragraph()
                                p.text = bullet
                                p.level = 1
                                if template == "Dark Mode":
                                    p.font.color.rgb = RGBColor(200, 200, 200)
                                    
                            vs = slide_data.get("visual_suggestion", "")
                            if vs:
                                txBox = slide.shapes.add_textbox(Inches(0.5), Inches(6.5), Inches(9), Inches(1))
                                tf2 = txBox.text_frame
                                p2 = tf2.add_paragraph()
                                p2.text = f"[Visual: {vs}]"
                                p2.font.size = Pt(12)
                                p2.font.italic = True
                                p2.font.color.rgb = RGBColor(128, 128, 128)
                        
                        import io
                        pptx_io = io.BytesIO()
                        prs.save(pptx_io)
                        st.session_state["pptx_io"] = pptx_io.getvalue()
                        st.success("Slide deck generated!")
                    except Exception as e:
                        st.error(f"Error generating slides: {e}")
                        
        if "pptx_io" in st.session_state:
            st.download_button("📥 Download Presentation (.pptx)", data=st.session_state["pptx_io"], file_name="AskMyPDF_Deck.pptx", mime="application/vnd.openxmlformats-officedocument.presentationml.presentation")
        
    with tab_mindmap:
        st.subheader("Interactive Knowledge Graph")
        if st.button("Generate Mind Map"):
            if not st.session_state.ingested_docs:
                st.warning("Please index documents first.")
            else:
                with st.spinner("Extracting graph relationships..."):
                    try:
                        results = retrieve("Extract main entities and their relationships.", reranker_top_k=20)
                        import json
                        map_json_str = generator.generate_mindmap_json(results, st.session_state.backend)
                        map_data = json.loads(map_json_str.replace('```json', '').replace('```', '').strip())
                        st.session_state["mindmap_data"] = map_data
                    except Exception as e:
                        st.error(f"Error extracting graph: {e}")
                        
        if "mindmap_data" in st.session_state:
            try:
                from streamlit_agraph import agraph, Node, Edge, Config
                map_data = st.session_state["mindmap_data"]
                nodes = []
                edges = []
                
                for n in map_data.get("nodes", []):
                    nodes.append(Node(id=str(n.get("id")), label=n.get("label", ""), title=n.get("title", ""), size=25))
                for e in map_data.get("edges", []):
                    edges.append(Edge(source=str(e.get("source")), target=str(e.get("target")), label=e.get("label", "")))
                    
                config = Config(width=600, height=400, directed=True, nodeHighlightBehavior=True, highlightColor="#F7A7A6", collapsible=True)
                agraph(nodes=nodes, edges=edges, config=config)
            except Exception as e:
                st.error(f"Error rendering mind map: {e}")
        
    with tab_report:
        st.subheader("Executive Report")
        if st.button("Generate Summary Report"):
            if not st.session_state.ingested_docs:
                st.warning("Please index documents first.")
            else:
                with st.spinner("Synthesizing report..."):
                    try:
                        results = retrieve("Summarize the main topics and key findings.", reranker_top_k=20)
                        st.session_state["report_md"] = generator.generate_report(results, st.session_state.backend)
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        if "report_md" in st.session_state:
            st.markdown(st.session_state["report_md"])
            import markdown
            from xhtml2pdf import pisa
            import io
            html = markdown.markdown(st.session_state["report_md"])
            pdf_bytes = io.BytesIO()
            pisa.CreatePDF(io.StringIO(html), dest=pdf_bytes)
            st.download_button("📥 Download as PDF", data=pdf_bytes.getvalue(), file_name="Report.pdf", mime="application/pdf")

    with tab_flashcard:
        st.subheader("Key Terms")
        if st.button("Generate Flashcards"):
            if not st.session_state.ingested_docs:
                st.warning("Please index documents first.")
            else:
                with st.spinner("Extracting terminology..."):
                    try:
                        results = retrieve("Key terms and definitions", reranker_top_k=15)
                        import json
                        fc_json = generator.generate_flashcards(results, st.session_state.backend)
                        st.session_state["flashcards"] = json.loads(fc_json.replace('```json', '').replace('```', '').strip())
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        if "flashcards" in st.session_state:
            for fc in st.session_state["flashcards"]:
                html_code = f'''
                <div class="flashcard">
                    <div class="flashcard-inner">
                        <div class="flashcard-front">{fc.get("front", "")}</div>
                        <div class="flashcard-back">{fc.get("back", "")}</div>
                    </div>
                </div>
                '''
                st.markdown(html_code, unsafe_allow_html=True)

    with tab_quiz:
        st.subheader("Knowledge Check")
        difficulty = st.selectbox("Difficulty:", ["Beginner", "Intermediate", "Advanced"])
        if st.button("Generate Quiz"):
            if not st.session_state.ingested_docs:
                st.warning("Please index documents first.")
            else:
                with st.spinner("Formulating questions..."):
                    try:
                        results = retrieve(f"Provide context to create a {difficulty} level quiz.", reranker_top_k=15)
                        import json
                        quiz_json = generator.generate_quiz(results, st.session_state.backend, difficulty)
                        st.session_state["quiz"] = json.loads(quiz_json.replace('```json', '').replace('```', '').strip())
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
        if "quiz" in st.session_state:
            for i, q in enumerate(st.session_state["quiz"]):
                st.markdown(f"**Q{i+1}: {q.get('question','')}**")
                choice = st.radio("Select answer:", q.get('options',[]), key=f"quiz_q_{i}")
                if st.button(f"Check Answer", key=f"check_{i}"):
                    if choice == q.get("answer"):
                        st.success("Correct!")
                    else:
                        st.error(f"Incorrect. The correct answer was: {q.get('answer')}")
                    st.info(f"Explanation: {q.get('explanation', '')}")

    with tab_info:
        st.subheader("High-Quality Infographics")
        if st.button("Generate Infographic Concepts"):
            if not st.session_state.ingested_docs:
                st.warning("Please index documents first.")
            else:
                with st.spinner("Distilling concepts..."):
                    try:
                        results = retrieve("Summarize key concepts for infographics.", reranker_top_k=20)
                        import json
                        concepts_json = generator.generate_infographic_concepts(results, st.session_state.backend)
                        st.session_state["info_concepts"] = json.loads(concepts_json.replace('```json', '').replace('```', '').strip())
                        st.session_state["info_results"] = results
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
        if "info_concepts" in st.session_state:
            selected_concept = st.radio("Select an Infographic Concept:", st.session_state["info_concepts"])
            if st.button("🎨 Render Infographic"):
                with st.spinner("Generating SVG..."):
                    try:
                        svg_code = generator.generate_svg(selected_concept, st.session_state["info_results"], st.session_state.backend)
                        st.session_state["current_svg"] = svg_code
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
        if "current_svg" in st.session_state:
            svg = st.session_state["current_svg"]
            import base64
            b64 = base64.b64encode(svg.encode('utf-8')).decode("utf-8")
            html = f'<img src="data:image/svg+xml;base64,{b64}"/>'
            st.markdown(html, unsafe_allow_html=True)
            
            col_svg, col_png = st.columns(2)
            col_svg.download_button("📥 Download SVG", data=svg, file_name="infographic.svg", mime="image/svg+xml")
            
            try:
                import cairosvg
                png_data = cairosvg.svg2png(bytestring=svg.encode('utf-8'))
                col_png.download_button("📥 Download PNG", data=png_data, file_name="infographic.png", mime="image/png")
            except Exception as e:
                col_png.error(f"CairoSVG missing or error: {e}")
        
    with tab_data:
        st.subheader("Data Table")
        if st.button("Extract Data"):
            if not st.session_state.ingested_docs:
                st.warning("Please index documents first.")
            else:
                with st.spinner("Mining quantitative data..."):
                    try:
                        results = retrieve("Extract metrics, numbers, and quantitative data.", reranker_top_k=20)
                        st.session_state["data_table_md"] = generator.generate_data_table(results, st.session_state.backend)
                    except Exception as e:
                        st.error(f"Error: {e}")
                        
        if "data_table_md" in st.session_state:
            md_text = st.session_state["data_table_md"]
            lines = [l.strip() for l in md_text.split('\\n') if '|' in l]
            if len(lines) >= 3:
                import pandas as pd
                headers = [c.strip() for c in lines[0].split('|') if c.strip()]
                data = []
                for line in lines[2:]:
                    cells = [c.strip() for c in line.split('|') if c.strip()]
                    if len(cells) == len(headers):
                        data.append(cells)
                    elif cells:
                        data.append(cells + [""] * (len(headers) - len(cells)))
                if headers and data:
                    df = pd.DataFrame(data, columns=headers)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.markdown(md_text)
            else:
                st.markdown(md_text)

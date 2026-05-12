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
from app.studio.renderer import render_studio_panel
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
    
    doc_names = list(st.session_state.ingested_docs.keys())
    render_studio_panel(doc_names, st.session_state.backend)

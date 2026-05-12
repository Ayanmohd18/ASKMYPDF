import streamlit as st
import json
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

from app.studio.briefing import generate_briefing
from app.studio.presentation import generate_presentation, export_to_pptx, Slide
from app.studio.mindmap import generate_mindmap, node_drill_down, MindmapData
from app.studio.infographic import generate_infographic, InfographicData
from app.studio.datatable import extract_table, export_to_csv, ExtractedTable

def lighten(hex_color: str, amount: float = 0.2) -> str:
    """Lightens a hex color by a given amount."""
    hex_color = hex_color.lstrip('#')
    rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    new_rgb = tuple(min(255, int(c + (255 - c) * amount)) for c in rgb)
    return '#{:02x}{:02x}{:02x}'.format(*new_rgb)

def format_briefing_as_markdown(data: Dict[str, Any]) -> str:
    """Formats briefing data into a clean markdown string for download."""
    md = [f"# {data['title']}", f"**{data['subtitle']}**\n", f"> {data['executive_summary']}\n"]
    for section in data['sections']:
        md.append(f"## {section['heading']}")
        md.append(f"{section['content']}\n")
    if data.get('key_facts'):
        md.append("## Key Facts")
        for f in data['key_facts']:
            md.append(f"- {f['fact']} ({f['source']})")
    if data.get('open_questions'):
        md.append("\n## Open Questions")
        for q in data['open_questions']:
            md.append(f"- {q}")
    return "\n".join(md)

def build_slide_html(slide: Slide, n: int) -> str:
    """Returns HTML for a slide preview card based on NotebookLM aesthetic."""
    slide_type = slide.slide_type.upper()
    
    content_html = ""
    if slide.slide_type == "stat":
        content_html = f"""
        <div class="slide-stat-number">{slide.emphasis}</div>
        <div class="slide-stat-label">{slide.title}</div>
        <div class="slide-stat-context">{slide.content}</div>
        """
    elif slide.slide_type == "quote":
        citation = slide.citations[0] if slide.citations else ""
        content_html = f"""
        <div class="slide-quote-mark">"</div>
        <div class="slide-quote-text">{slide.content}</div>
        <div class="slide-quote-source">— {citation}</div>
        """
    elif slide.slide_type == "compare":
        items = slide.content if isinstance(slide.content, list) else []
        col_html = ""
        for group in items:
            points = "".join([f"<li>{p}</li>" for p in group.get("points", [])])
            col_html += f"""
            <div style="flex:1; padding:10px;">
                <div style="color:var(--accent-primary); font-weight:600; font-size:14px; margin-bottom:8px;">{group.get('label')}</div>
                <ul style="font-size:12px; padding-left:15px; color:var(--text-secondary);">{points}</ul>
            </div>
            """
        content_html = f'<div style="display:flex;">{col_html}</div>'
    elif slide.slide_type == "process":
        steps = slide.content if isinstance(slide.content, list) else []
        steps_html = "".join([f'<div style="margin-bottom:8px;"><span style="color:var(--accent-primary); font-weight:bold; margin-right:8px;">{i+1}.</span> <span style="font-size:13px;">{s}</span></div>' for i, s in enumerate(steps)])
        content_html = f'<div style="padding-top:10px;">{steps_html}</div>'
    else: # insight, agenda, summary
        bullets = slide.content if isinstance(slide.content, list) else [slide.content]
        bullets_html = "".join([f'<li style="margin-bottom:10px;">{b}</li>' for b in bullets])
        content_html = f'<ul style="font-size:15px; line-height:1.4; color:var(--text-primary);">{bullets_html}</ul>'

    return f"""
    <div class="slide-card fade-in">
        <div class="slide-header" style="background: var(--accent-primary);">
            <span class="slide-number">{n}</span>
            <span class="slide-type-badge">{slide_type}</span>
        </div>
        <div class="slide-body">
            {content_html}
        </div>
    </div>
    """

def render_briefing(data: Dict[str, Any]):
    """Renders a polished briefing document."""
    st.markdown(f"""
    <div class="studio-doc-title">{data['title']}</div>
    <div class="studio-doc-subtitle">{data['subtitle']}</div>
    """, unsafe_allow_html=True)
    
    st.markdown(f"""
    <div class="exec-summary-box">
        <div class="exec-summary-label">EXECUTIVE SUMMARY</div>
        <div class="exec-summary-text">{data['executive_summary']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    for section in data['sections']:
        st.markdown(f"### {section['heading']}")
        st.markdown(section['content'])
        st.divider()
    
    if data.get('key_facts'):
        st.markdown("#### 📌 Key Facts")
        cols = st.columns(3)
        for i, fact in enumerate(data['key_facts']):
            with cols[i % 3]:
                st.markdown(f"""
                <div class="key-fact-card">
                    <div class="key-fact-text">{fact['fact']}</div>
                    <div class="key-fact-source">{fact['source']}</div>
                </div>
                """, unsafe_allow_html=True)
    
    if data.get('conflicts_detected'):
        st.markdown("#### ⚠️ Source Conflicts Detected")
        for c in data['conflicts_detected']:
            st.markdown(f"""
            <div class="conflict-card">
                <strong>{c['topic']}</strong><br/>
                🔴 {c['position_a']}<br/>
                🔵 {c['position_b']}
            </div>
            """, unsafe_allow_html=True)
            
    if data.get('open_questions'):
        st.markdown("#### ❓ Open Questions")
        for q in data['open_questions']:
            st.markdown(f"- {q}")
            
    briefing_text = format_briefing_as_markdown(data)
    st.download_button("⬇️ Download as Markdown", briefing_text, file_name="briefing.md", mime="text/markdown")

def render_slide_preview(slides: List[Slide]):
    """Renders scrollable slide deck with speaker notes."""
    st.caption(f"{len(slides)} slides generated")
    
    for i, slide in enumerate(slides, start=1):
        st.markdown(build_slide_html(slide, i), unsafe_allow_html=True)
        with st.expander(f"🎙️ Speaker Notes — Slide {i}"):
            st.markdown(slide.speaker_notes)
            if slide.citations:
                st.caption("Sources: " + ", ".join(slide.citations))
                
    pptx_path = export_to_pptx(slides, Path("temp.pptx"))
    with open(pptx_path, "rb") as f:
        st.download_button("⬇️ Download .pptx", f, "presentation.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation")

def render_mindmap_interactive(mindmap: MindmapData, llm_backend: str):
    """Renders interactive knowledge graph using vis.js."""
    nodes_js = []
    edges_js = []
    
    def flatten_nodes(node, level=0, parent_id=None):
        size = [50, 35, 22][min(level, 2)]
        nodes_js.append({
            "id": node.id,
            "label": node.label,
            "title": node.summary,
            "color": node.color,
            "size": size,
            "font": {"size": [16, 13, 11][min(level, 2)], "color": "#F2EFE9" if st.session_state.get('dark_mode', True) else "#1C1A18"}
        })
        if parent_id:
            edges_js.append({"from": parent_id, "to": node.id, "color": {"color": node.color}})
        for child in node.children:
            flatten_nodes(child, level+1, node.id)
            
    flatten_nodes(mindmap.root)
    
    rel_colors = {"supports": "#2DA89A", "contradicts": "#E53E3E", "requires": "#D4825A", "extends": "#7B61A8", "contrasts_with": "#4A90B8"}
    for cc in mindmap.cross_connections:
        edges_js.append({
            "from": cc.source_id, "to": cc.target_id, "dashes": True, "label": cc.relationship, "title": cc.explanation, "color": rel_colors.get(cc.relationship, "#888")
        })
        
    html = f"""
    <div id="mindmap" style="height:600px; border-radius:12px; background:var(--bg-card,#2A2724);"></div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.js"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/vis/4.21.0/vis.min.css" rel="stylesheet"/>
    <script>
        var nodes = new vis.DataSet({json.dumps(nodes_js)});
        var edges = new vis.DataSet({json.dumps(edges_js)});
        var network = new vis.Network(document.getElementById('mindmap'), {{nodes, edges}}, {{
            layout: {{ hierarchical: {{ enabled: false }} }},
            physics: {{ barnesHut: {{ gravitationalConstant: -8000, centralGravity: 0.3, springLength: 150 }} }},
            interaction: {{ hover: true, tooltipDelay: 200 }},
            nodes: {{ shape: "dot", borderWidth: 2 }},
            edges: {{ smooth: {{ type: "cubicBezier" }} }}
        }});
        network.on("click", function(params) {{
            if (params.nodes.length > 0) {{
                window.parent.postMessage({{ type: "mindmap_click", nodeId: params.nodes[0] }}, "*");
            }}
        }});
    </script>
    """
    st.components.v1.html(html, height=620)
    
    # Drill-down UI
    st.markdown("---")
    st.markdown("#### 🔍 Deep-Dive Exploration")
    
    # Get flat list of nodes for selection
    all_nodes = []
    def get_all_nodes(node):
        all_nodes.append(node)
        for child in node.children:
            get_all_nodes(child)
    get_all_nodes(mindmap.root)
    
    node_options = {n.label: n for n in all_nodes}
    selected_node_label = st.selectbox("Select a node to explore deeper:", ["Select a concept..."] + list(node_options.keys()))
    
    if selected_node_label != "Select a concept...":
        node = node_options[selected_node_label]
        with st.spinner(f"Analyzing '{node.label}'..."):
            drill_down = node_drill_down(node.label, llm_backend)
            
            st.markdown(f"""
            <div style="background:var(--source-card-bg); border-radius:12px; padding:20px; border-top:3px solid {node.color};">
                <div style="font-family:'DM Serif Display',serif; font-size:20px; margin-bottom:10px;">{drill_down['title']}</div>
                <div style="font-size:14px; line-height:1.6; margin-bottom:15px;">{drill_down['analysis']}</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--accent-primary);">{drill_down['citations']}</div>
            </div>
            """, unsafe_allow_html=True)
            
            if drill_down.get('connections'):
                st.markdown("**Related Contexts:**")
                for conn in drill_down['connections']:
                    st.caption(f"🔗 {conn}")

    st.markdown("---")
    st.markdown("**Cross-connections:**")
    for cc in mindmap.cross_connections:
        color = rel_colors.get(cc.relationship, "#888")
        st.markdown(f'<span style="color:{color}; font-family:\'JetBrains Mono\',monospace; font-size:12px;">{cc.source_id} → {cc.relationship} → {cc.target_id}</span><br/><span style="color:var(--text-muted); font-size:12px;">{cc.explanation}</span>', unsafe_allow_html=True)

def render_infographic(data: InfographicData):
    """Renders infographic sections with diverse visual layouts."""
    st.markdown(f"""
    <div class="infographic-header" style="background: linear-gradient(135deg, {data.theme_color}, {lighten(data.theme_color)})">
        <div class="infographic-title">{data.title}</div>
        <div class="infographic-subtitle">{data.subtitle}</div>
    </div>
    """, unsafe_allow_html=True)
    
    for section in data.sections:
        st.markdown(f"#### {section.title}")
        
        if section.section_type == "hero_stat":
            d = section.data
            st.markdown(f"""
            <div class="hero-stat-card">
                <div class="hero-number">{d.get('number')}</div>
                <div class="hero-label">{d.get('label')}</div>
                <div class="hero-context">{d.get('context')}</div>
                <div class="hero-citation">{d.get('citation')}</div>
            </div>
            """, unsafe_allow_html=True)
            
        elif section.section_type == "process_steps":
            steps = section.data.get("steps", [])
            cols = st.columns(len(steps) or 1)
            for i, step in enumerate(steps):
                with cols[i]:
                    st.markdown(f"""
                    <div style="background:var(--bg-secondary); border-radius:12px; padding:15px; border-left:4px solid var(--accent-primary); height:100%;">
                        <div style="font-weight:bold; color:var(--accent-primary); margin-bottom:5px;">STEP {step.get('number')}</div>
                        <div style="font-weight:600; font-size:14px; margin-bottom:5px;">{step.get('title')}</div>
                        <div style="font-size:12px; color:var(--text-secondary);">{step.get('description')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
        elif section.section_type == "comparison":
            d = section.data
            comp_df = pd.DataFrame(d.get("dimensions", []))
            st.table(comp_df)
            
        elif section.section_type == "timeline":
            events = section.data.get("events", [])
            for ev in events:
                st.markdown(f"""
                <div style="display:flex; gap:15px; margin-bottom:15px;">
                    <div style="min-width:80px; font-weight:bold; color:var(--accent-primary);">{ev.get('date')}</div>
                    <div style="border-left:2px solid var(--accent-primary); padding-left:15px;">
                        <div style="font-weight:600;">{ev.get('event')}</div>
                        <div style="font-size:12px; color:var(--text-secondary);">{ev.get('significance')}</div>
                        <div style="font-size:10px; color:var(--text-muted);">{ev.get('citation')}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
        elif section.section_type == "key_facts":
            facts = section.data.get("facts", [])
            cols = st.columns(3)
            for i, f in enumerate(facts):
                with cols[i % 3]:
                    st.markdown(f"""
                    <div class="key-fact-card">
                        <div style="font-size:20px; margin-bottom:8px;">{f.get('icon', '💡')}</div>
                        <div class="key-fact-text">{f.get('fact')}</div>
                        <div class="key-fact-source">{f.get('citation')}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
        elif section.section_type == "quote_highlight":
            d = section.data
            st.markdown(f"""
            <div style="background:var(--bg-sidebar); border-radius:16px; padding:30px; text-align:center; border:1px solid var(--border);">
                <div style="font-family:'DM Serif Display',serif; font-size:40px; color:var(--accent-primary); line-height:0.5; opacity:0.5;">"</div>
                <div style="font-family:'DM Serif Display',serif; font-style:italic; font-size:20px; color:var(--text-primary); margin-bottom:15px;">{d.get('quote')}</div>
                <div style="font-family:'JetBrains Mono',monospace; font-size:12px; color:var(--accent-primary);">{d.get('source')}</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.divider()

def render_data_table(table: ExtractedTable):
    """Renders structured data table with pandas."""
    st.markdown(f"### {table.title}")
    
    rows_data = []
    for row in table.rows:
        row_dict = {"Entity": row.entity}
        for col, cell in row.cells.items():
            display = cell.value
            if cell.conflict: display = f"⚠️ {display}"
            if cell.confidence == "low": display = f"~ {display}"
            row_dict[col] = display
            row_dict[f"{col} (Source)"] = cell.citation
        rows_data.append(row_dict)
        
    df = pd.DataFrame(rows_data)
    main_cols = ["Entity"] + table.columns
    st.dataframe(df[main_cols], use_container_width=True, height=400)
    
    st.caption("⚠️ = conflicting sources  |  ~ = low confidence")
    if table.extraction_notes:
        with st.expander("📝 Extraction Notes"):
            st.markdown(table.extraction_notes)
            
    st.markdown("**Document Coverage:**")
    for doc, count in table.doc_coverage.items():
        st.markdown(f"- {doc}: {count} rows")
        
    csv_path = export_to_csv(table, Path("table.csv"))
    with open(csv_path, "r") as f:
        st.download_button("⬇️ Download CSV", f.read(), "extracted_table.csv", "text/csv")

def render_studio_panel(doc_names: List[str], llm_backend: str):
    """Main Studio panel entry point."""
    tabs = st.tabs(["📋 Briefing", "📊 Slides", "🧠 Mindmap",
                    "📌 Infographic", "📈 Data Table", "🎙️ Audio"])
    
    # TAB 1: BRIEFING
    with tabs[0]:
        c1, c2 = st.columns(2)
        focus = c1.text_input("Focus area (optional)", placeholder="e.g. payment terms, risk factors...", key="brief_focus")
        audience = c2.selectbox("Audience", ["executive", "technical", "academic", "general"], key="brief_audience")
        if st.button("Generate Briefing", type="primary"):
            with st.spinner("Analyzing documents..."):
                st.session_state.briefing = generate_briefing(focus, doc_names, llm_backend, audience)
        if "briefing" in st.session_state:
            render_briefing(st.session_state.briefing)
            
    # TAB 2: SLIDES
    with tabs[1]:
        c1, c2, c3 = st.columns(3)
        topic = c1.text_input("Presentation topic", placeholder="Auto-detect if empty", key="slide_topic")
        num_s = c2.slider("Slides", 6, 20, 12)
        style = c3.selectbox("Style", ["executive","academic","technical","general"], key="slide_style")
        if st.button("Generate Slides", type="primary"):
            with st.spinner("Building slide deck..."):
                st.session_state.slides = generate_presentation(topic, doc_names, num_s, style, llm_backend)
        if "slides" in st.session_state:
            render_slide_preview(st.session_state.slides)
            
    # TAB 3: MINDMAP
    with tabs[2]:
        if st.button("Generate Mindmap", type="primary"):
            with st.spinner("Mapping knowledge..."):
                st.session_state.mindmap = generate_mindmap(doc_names, llm_backend)
        if "mindmap" in st.session_state:
            render_mindmap_interactive(st.session_state.mindmap, llm_backend)
            
    # TAB 4: INFOGRAPHIC
    with tabs[3]:
        info_focus = st.text_input("Focus (optional)", placeholder="e.g. key statistics, process overview", key="info_focus")
        if st.button("Generate Infographic", type="primary"):
            with st.spinner("Designing infographic..."):
                st.session_state.infographic = generate_infographic(info_focus, doc_names, llm_backend)
        if "infographic" in st.session_state:
            render_infographic(st.session_state.infographic)
            
    # TAB 5: DATA TABLE
    with tabs[4]:
        st.markdown("**Column Schema**")
        use_auto = st.checkbox("Auto-detect schema", value=True, key="dt_auto")
        cols_input, row_ent = "", ""
        if not use_auto:
            cols_input = st.text_input("Columns (comma-separated)", placeholder="e.g. party, obligation, deadline", key="dt_cols")
            row_ent = st.text_input("Each row represents", placeholder="e.g. contract clause, clinical trial", key="dt_row")
        if st.button("Extract Table", type="primary"):
            with st.spinner("Extracting structured data..."):
                cols = [c.strip() for c in cols_input.split(",")] if cols_input else None
                st.session_state.datatable = extract_table(cols, row_ent if row_ent else None, doc_names, llm_backend)
        if "datatable" in st.session_state:
            render_data_table(st.session_state.datatable)

    # TAB 6: AUDIO OVERVIEW
    with tabs[5]:
        from app.studio.audio_renderer import render_audio_tab
        render_audio_tab(doc_names, llm_backend)

"""
app/studio/audio_renderer.py

Streamlit UI for the Audio Overview Studio tab.
Renders a podcast player with Web Speech API TTS (free)
and optional ElevenLabs integration.
"""
import json
import streamlit as st
from app.studio.audio import PodcastScript, generate_podcast_script


# ─────────────────────────────────────────────────────────
# TRANSCRIPT MARKDOWN EXPORT
# ─────────────────────────────────────────────────────────

def format_transcript_as_markdown(script: PodcastScript) -> str:
    lines = [
        f"# {script.title}",
        f"> {script.episode_tagline}",
        "",
        f"**Hosts:** {script.host_a} · {script.host_b}  ",
        f"**Est. Duration:** {script.duration_estimate_mins} min  ",
        f"**Documents:** {', '.join(script.sources_cited)}",
        "",
        "---",
        "",
    ]
    chapter_map = {ch["start_turn_index"]: ch["title"] for ch in script.chapters}
    for i, turn in enumerate(script.turns):
        if i in chapter_map:
            lines += [f"## {chapter_map[i]}", ""]
        lines.append(f"**{turn.speaker.upper()}:** {turn.text}")
        lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# PLAYER HTML BUILDER
# ─────────────────────────────────────────────────────────

def _build_player_html(script: PodcastScript, use_elevenlabs: bool, el_key: str = "") -> str:
    turns_json = json.dumps([
        {"speaker": t.speaker, "text": t.text,
         "tone": t.tone, "pause_before_ms": t.pause_before_ms}
        for t in script.turns
    ])
    chapters_json = json.dumps(script.chapters)

    el_block = ""
    if use_elevenlabs and el_key:
        el_block = f"""
        const ELEVENLABS_KEY = {json.dumps(el_key)};
        const VOICE_ALEX   = "21m00Tcm4TlvDq8ikWAM";
        const VOICE_JORDAN = "ErXwobaYiN019PkySvjV";
        const audioCache = {{}};
        const stabilityMap = {{
            excited:0.35, curious:0.50, analytical:0.70,
            surprised:0.30, thoughtful:0.65, warm:0.55,
            skeptical:0.60, explanatory:0.60
        }};
        async function synthesizeTurn(turn) {{
            if (audioCache[currentTurn]) {{
                const a = new Audio(audioCache[currentTurn]);
                a.playbackRate = speed;
                return new Promise(r => {{ a.onended = r; a.play(); }});
            }}
            const voiceId = turn.speaker === 'Alex' ? VOICE_ALEX : VOICE_JORDAN;
            const resp = await fetch(
                `https://api.elevenlabs.io/v1/text-to-speech/${{voiceId}}/stream`,
                {{ method:'POST',
                   headers:{{'xi-api-key':ELEVENLABS_KEY,'Content-Type':'application/json'}},
                   body: JSON.stringify({{
                       text: turn.text, model_id:'eleven_monolingual_v1',
                       voice_settings:{{ stability: stabilityMap[turn.tone]||0.5,
                                         similarity_boost:0.75, use_speaker_boost:true }}
                   }})
                }}
            );
            const blob = await resp.blob();
            const url = URL.createObjectURL(blob);
            audioCache[currentTurn] = url;
            const audio = new Audio(url);
            audio.playbackRate = speed;
            return new Promise(r => {{ setTimeout(()=>{{ audio.onended=r; audio.play(); }}, turn.pause_before_ms); }});
        }}
        async function playFromTurn(idx) {{
            for (let i=idx; i<SCRIPT.length && isPlaying; i++) {{
                currentTurn=i; highlightTurn(i); scrollToTurn(i);
                await synthesizeTurn(SCRIPT[i]);
            }}
            if (isPlaying) {{ isPlaying=false; updateUI(); }}
        }}
        function play() {{ isPlaying=true; updateUI(); playFromTurn(currentTurn); }}
        function pause() {{ isPlaying=false; updateUI(); }}
        """
    else:
        el_block = """
        function getVoice(speaker) {
            const voices = speechSynthesis.getVoices();
            const en = voices.filter(v => v.lang.startsWith('en'));
            if (speaker === 'Alex') {
                return en.find(v => /female|samantha|karen|moira|zira/i.test(v.name)) || en[0];
            }
            return en.find(v => /male|daniel|fred|david|mark/i.test(v.name)) || en[1] || en[0];
        }
        const toneMap = {
            excited:{rate:1.1,pitch:1.1}, curious:{rate:0.95,pitch:1.05},
            analytical:{rate:0.9,pitch:0.95}, surprised:{rate:1.0,pitch:1.15},
            thoughtful:{rate:0.88,pitch:0.98}, warm:{rate:0.95,pitch:1.0},
            skeptical:{rate:0.92,pitch:0.97}, explanatory:{rate:0.93,pitch:1.0}
        };
        function speakTurn(idx) {
            if (idx >= SCRIPT.length) { isPlaying=false; updateUI(); return; }
            const turn = SCRIPT[idx];
            currentTurn = idx; highlightTurn(idx); scrollToTurn(idx);
            setTimeout(() => {
                const utt = new SpeechSynthesisUtterance(turn.text);
                utt.voice = getVoice(turn.speaker);
                const p = toneMap[turn.tone] || {rate:1.0,pitch:1.0};
                utt.rate = p.rate * speed;
                utt.pitch = p.pitch;
                utt.onend = () => { if (isPlaying) speakTurn(idx+1); };
                speechSynthesis.speak(utt);
            }, turn.pause_before_ms);
        }
        function play()  { isPlaying=true;  updateUI(); speakTurn(currentTurn); }
        function pause() { isPlaying=false; speechSynthesis.cancel(); updateUI(); }
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link href="https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;600&family=JetBrains+Mono&display=swap" rel="stylesheet"/>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'DM Sans',sans-serif;background:transparent;color:#1C1A18;padding:8px}}
.episode-header{{background:linear-gradient(135deg,#1A7A6E,#2DA89A);border-radius:16px;padding:24px;color:white;margin-bottom:14px}}
.episode-title{{font-family:'DM Serif Display',serif;font-size:22px;margin-bottom:4px}}
.episode-tagline{{font-size:13px;opacity:.8;margin-bottom:14px}}
.host-avatars{{display:flex;gap:10px;align-items:center}}
.host-chip{{display:flex;align-items:center;gap:8px;background:rgba(255,255,255,.15);border-radius:100px;padding:5px 14px 5px 5px;font-size:13px;color:white}}
.avatar{{width:30px;height:30px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px}}
.av-alex{{background:rgba(255,255,255,.9);color:#1A7A6E}}
.av-jordan{{background:#D4825A;color:#fff}}
.duration-badge{{margin-left:auto;font-family:'JetBrains Mono',monospace;font-size:11px;opacity:.75}}
.chapters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px}}
.chapter-pill{{padding:5px 14px;border-radius:100px;font-size:12px;border:1px solid rgba(26,122,110,.35);color:#1A7A6E;cursor:pointer;background:transparent;transition:all .2s}}
.chapter-pill:hover,.chapter-pill.active{{background:#1A7A6E;color:white;border-color:#1A7A6E}}
.transcript{{height:380px;overflow-y:auto;padding:10px 6px;border:1px solid rgba(0,0,0,.08);border-radius:12px;background:#FAFAF8;scroll-behavior:smooth;margin-bottom:10px}}
.turn-bubble{{display:flex;gap:10px;padding:9px 8px;border-radius:10px;margin-bottom:5px;border-left:3px solid transparent;transition:background .2s}}
.turn-bubble.alex-turn{{border-left-color:#1A7A6E}}
.turn-bubble.jordan-turn{{border-left-color:#D4825A}}
.turn-bubble.active-turn{{background:rgba(26,122,110,.08);animation:pulse 1.5s ease-in-out infinite}}
.jordan-turn.active-turn{{animation:pulse-warm 1.5s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{border-left-color:#1A7A6E}}50%{{border-left-color:#2DA89A}}}}
@keyframes pulse-warm{{0%,100%{{border-left-color:#D4825A}}50%{{border-left-color:#E09070}}}}
.turn-avatar{{width:26px;height:26px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700}}
.turn-content{{flex:1}}
.turn-header{{display:flex;align-items:center;gap:8px;margin-bottom:3px}}
.turn-speaker{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em}}
.sp-alex{{color:#1A7A6E}}.sp-jordan{{color:#D4825A}}
.tone-badge{{font-size:10px;padding:2px 8px;border-radius:100px;background:rgba(0,0,0,.06);color:#888}}
.turn-text{{font-size:13.5px;line-height:1.6;color:#1C1A18}}
.controls{{background:#F3F1ED;border-radius:12px;padding:14px 18px}}
.progress-track{{height:4px;background:rgba(0,0,0,.1);border-radius:2px;margin-bottom:12px;cursor:pointer;position:relative}}
.progress-fill{{height:100%;background:#1A7A6E;border-radius:2px;transition:width .3s;width:0%}}
.btns{{display:flex;align-items:center;justify-content:center;gap:14px}}
.cb{{background:none;border:none;cursor:pointer;color:#6B6560;font-size:17px;padding:7px;border-radius:8px;display:flex;align-items:center;transition:all .15s}}
.cb:hover{{background:rgba(26,122,110,.1);color:#1A7A6E}}
.play-btn{{width:50px;height:50px;border-radius:50%;background:#1A7A6E;color:white;font-size:20px;justify-content:center}}
.play-btn:hover{{background:#2DA89A}}
.speed-sel{{font-size:12px;padding:4px 10px;border-radius:8px;border:1px solid rgba(0,0,0,.15);background:white;cursor:pointer}}
.time-disp{{font-family:'JetBrains Mono',monospace;font-size:11px;color:#6B6560}}
</style>
</head>
<body>

<div class="episode-header">
  <div class="episode-title">{script.title}</div>
  <div class="episode-tagline">{script.episode_tagline}</div>
  <div class="host-avatars">
    <div class="host-chip"><div class="avatar av-alex">A</div>{script.host_a}</div>
    <div class="host-chip"><div class="avatar av-jordan">J</div>{script.host_b}</div>
    <div class="duration-badge">~{script.duration_estimate_mins} min · {len(script.turns)} turns</div>
  </div>
</div>

<div class="chapters" id="chapters"></div>

<div class="transcript" id="transcript"></div>

<div class="controls">
  <div class="progress-track" id="progressTrack" onclick="seekClick(event)">
    <div class="progress-fill" id="progressFill"></div>
  </div>
  <div class="btns">
    <button class="cb" onclick="restart()" title="Restart">⏮</button>
    <button class="cb" onclick="prevTurn()" title="Previous turn">⏪</button>
    <button class="cb play-btn" id="playBtn" onclick="togglePlay()">▶</button>
    <button class="cb" onclick="nextTurn()" title="Next turn">⏩</button>
    <button class="cb" onclick="jumpEnd()" title="End">⏭</button>
    <select class="speed-sel" onchange="setSpeed(this.value)">
      <option value="0.75">0.75×</option>
      <option value="1" selected>1×</option>
      <option value="1.25">1.25×</option>
      <option value="1.5">1.5×</option>
      <option value="1.75">1.75×</option>
    </select>
    <span class="time-disp" id="timeDisp">0:00 / {int(script.duration_estimate_mins)}:{int((script.duration_estimate_mins % 1)*60):02d}</span>
  </div>
</div>

<script>
const SCRIPT = {turns_json};
const CHAPTERS = {chapters_json};
let currentTurn = 0;
let isPlaying = false;
let speed = 1.0;
let startTime = null;

// Build chapter pills
const chapDiv = document.getElementById('chapters');
CHAPTERS.forEach((ch, i) => {{
    const btn = document.createElement('button');
    btn.className = 'chapter-pill' + (i===0?' active':'');
    btn.textContent = ch.title;
    btn.onclick = () => jumpToChapter(ch.start_turn_index);
    chapDiv.appendChild(btn);
}});

// Build transcript bubbles
const transcript = document.getElementById('transcript');
SCRIPT.forEach((turn, i) => {{
    const bubble = document.createElement('div');
    const isAlex = turn.speaker === 'Alex';
    bubble.className = 'turn-bubble ' + (isAlex ? 'alex-turn' : 'jordan-turn');
    bubble.id = 'turn-' + i;
    bubble.innerHTML = `
        <div class="turn-avatar ${{isAlex ? 'av-alex' : 'av-jordan'}}">${{isAlex ? 'A' : 'J'}}</div>
        <div class="turn-content">
          <div class="turn-header">
            <span class="turn-speaker ${{isAlex ? 'sp-alex' : 'sp-jordan'}}">${{turn.speaker}}</span>
            <span class="tone-badge">${{turn.tone}}</span>
          </div>
          <div class="turn-text">${{turn.text}}</div>
        </div>`;
    transcript.appendChild(bubble);
}});

function highlightTurn(idx) {{
    document.querySelectorAll('.turn-bubble').forEach((el,i) => {{
        el.classList.toggle('active-turn', i===idx);
    }});
    updateProgressBar(idx);
    updateChapterPills(idx);
}}

function scrollToTurn(idx) {{
    const el = document.getElementById('turn-' + idx);
    if (el) el.scrollIntoView({{behavior:'smooth', block:'center'}});
}}

function updateProgressBar(idx) {{
    const pct = SCRIPT.length > 1 ? (idx/(SCRIPT.length-1))*100 : 0;
    document.getElementById('progressFill').style.width = pct + '%';
    const elapsed = Math.round((idx/SCRIPT.length) * {script.duration_estimate_mins} * 60);
    const total = Math.round({script.duration_estimate_mins} * 60);
    const fmt = s => Math.floor(s/60)+':'+(s%60).toString().padStart(2,'0');
    document.getElementById('timeDisp').textContent = fmt(elapsed)+' / '+fmt(total);
}}

function updateChapterPills(idx) {{
    document.querySelectorAll('.chapter-pill').forEach((pill,i) => {{
        const ch = CHAPTERS[i];
        const next = CHAPTERS[i+1];
        pill.classList.toggle('active', idx >= ch.start_turn_index && (!next || idx < next.start_turn_index));
    }});
}}

function updateUI() {{
    document.getElementById('playBtn').textContent = isPlaying ? '⏸' : '▶';
}}

function togglePlay() {{ isPlaying ? pause() : play(); }}
function prevTurn() {{ pause_tts(); currentTurn=Math.max(0,currentTurn-1); if(isPlaying) play(); else highlightTurn(currentTurn); }}
function nextTurn() {{ pause_tts(); currentTurn=Math.min(SCRIPT.length-1,currentTurn+1); if(isPlaying) play(); else highlightTurn(currentTurn); }}
function restart()  {{ pause_tts(); currentTurn=0; isPlaying=false; updateUI(); highlightTurn(0); scrollToTurn(0); }}
function jumpEnd()  {{ pause_tts(); currentTurn=SCRIPT.length-1; isPlaying=false; updateUI(); highlightTurn(currentTurn); scrollToTurn(currentTurn); }}
function jumpToChapter(idx) {{ pause_tts(); currentTurn=idx; if(isPlaying) play(); else {{ highlightTurn(idx); scrollToTurn(idx); }} }}
function setSpeed(v) {{ speed=parseFloat(v); }}
function seekClick(e) {{
    const rect = document.getElementById('progressTrack').getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const idx = Math.round(pct * (SCRIPT.length-1));
    pause_tts(); currentTurn=Math.max(0,Math.min(SCRIPT.length-1,idx));
    if(isPlaying) play(); else {{ highlightTurn(currentTurn); scrollToTurn(currentTurn); }}
}}
function pause_tts() {{ isPlaying=false; updateUI(); try{{ speechSynthesis.cancel(); }}catch(e){{}} }}

{el_block}

// Init
highlightTurn(0);
speechSynthesis && speechSynthesis.onvoiceschanged !== undefined && (speechSynthesis.onvoiceschanged = () => {{}});
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────
# MAIN TAB RENDERER
# ─────────────────────────────────────────────────────────

def render_audio_tab(doc_names: list, llm_backend: str):
    """Renders the Audio Overview tab in the Studio panel."""
    from app.vector_store import get_chunk_count

    st.markdown(
        '<div style="font-family:\'JetBrains Mono\',monospace;font-size:10px;'
        'text-transform:uppercase;letter-spacing:.1em;color:var(--text-muted,#888);">'
        'AUDIO OVERVIEW</div>',
        unsafe_allow_html=True
    )

    c1, c2, c3 = st.columns(3)
    focus = c1.text_input(
        "Focus (optional)", placeholder="e.g. key risks, main findings...",
        key="audio_focus"
    )
    duration = c2.select_slider(
        "Length", options=[5, 8, 12, 15], value=8,
        format_func=lambda x: f"{x} min", key="audio_duration"
    )
    tts_engine = c3.selectbox(
        "Voice engine",
        ["Browser TTS (free)", "ElevenLabs (API key required)"],
        key="audio_tts"
    )

    el_key = ""
    if tts_engine == "ElevenLabs (API key required)":
        el_key = st.text_input(
            "ElevenLabs API Key", type="password",
            placeholder="sk-...", key="audio_el_key"
        )
        st.caption("Alex → Rachel voice · Jordan → Antoni voice")

    st.divider()

    has_docs = bool(doc_names)
    if st.button("🎙️  Generate Audio Overview", type="primary",
                 use_container_width=True, disabled=not has_docs):
        if not has_docs:
            st.warning("Upload and ingest documents first.")
        else:
            progress = st.progress(0)
            status = st.empty()
            try:
                status.markdown("**Pass 1 — Planning episode structure...**")
                progress.progress(15)
                script = generate_podcast_script(
                    doc_names=doc_names,
                    focus=focus or None,
                    duration_mins=duration,
                    llm_backend=llm_backend,
                )
                status.markdown("**Pass 2 — Writing dialogue...**")
                progress.progress(60)
                # (passes run inside generate_podcast_script)
                status.markdown("**Pass 3 — Polishing script...**")
                progress.progress(90)
                st.session_state.podcast_script = script
                progress.progress(100)
                status.empty()
                st.rerun()
            except Exception as e:
                st.error(f"Generation failed: {e}")
                progress.empty()
                status.empty()

    if "podcast_script" in st.session_state:
        script: PodcastScript = st.session_state.podcast_script
        use_el = (tts_engine == "ElevenLabs (API key required)" and bool(el_key))
        html = _build_player_html(script, use_elevenlabs=use_el, el_key=el_key)
        st.components.v1.html(html, height=680, scrolling=False)

        transcript_md = format_transcript_as_markdown(script)
        st.download_button(
            "⬇️ Download Transcript",
            transcript_md,
            file_name=f"{script.title}.md",
            mime="text/markdown",
        )

        with st.expander("📊 Episode Details"):
            col1, col2, col3 = st.columns(3)
            col1.metric("Turns", len(script.turns))
            col2.metric("Est. Duration", f"{script.duration_estimate_mins} min")
            col3.metric("Chapters", len(script.chapters))
            st.caption(f"Sources: {', '.join(script.sources_cited)}")

def get_css(dark_mode: bool) -> str:
    if dark_mode:
        theme_vars = """
  --bg-primary: #1A1917;
  --bg-secondary: #221F1D;
  --bg-card: #2A2724;
  --bg-sidebar: #1E1C1A;
  --accent-primary: #2DA89A;
  --accent-secondary: #3DC0B1;
  --accent-warm: #E09070;
  --text-primary: #F2EFE9;
  --text-secondary: #A8A39D;
  --text-muted: #6B6560;
  --border: #332F2C;
  --border-strong: #4A4540;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
  --shadow-md: 0 4px 16px rgba(0,0,0,0.4);
  --shadow-lg: 0 8px 32px rgba(0,0,0,0.5);
  --source-card-bg: #1E2E2C;
"""
    else:
        theme_vars = """
  --bg-primary: #FAF9F7;
  --bg-secondary: #F3F1ED;
  --bg-card: #FFFFFF;
  --bg-sidebar: #F0EDE8;
  --accent-primary: #1A7A6E;
  --accent-secondary: #2DA89A;
  --accent-warm: #D4825A;
  --text-primary: #1C1A18;
  --text-secondary: #6B6560;
  --text-muted: #9E9893;
  --border: #E5E2DC;
  --border-strong: #CCC9C3;
  --shadow-sm: 0 1px 3px rgba(28,26,24,0.08);
  --shadow-md: 0 4px 16px rgba(28,26,24,0.10);
  --shadow-lg: 0 8px 32px rgba(28,26,24,0.12);
  --source-card-bg: #EEF7F6;
"""

    css = f"""
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
{theme_vars}
}}

html, body, [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
  background-color: var(--bg-primary) !important;
  color: var(--text-primary) !important;
}}

* {{
  font-family: 'DM Sans', sans-serif;
}}

h1, h2, h3, [data-testid="stHeader"], .st-emotion-cache-10trblm {{
  font-family: 'DM Serif Display', serif !important;
}}

.block-container {{
  padding-top: 2rem !important;
}}

#MainMenu, footer {{ visibility: hidden; }}

[data-testid="stSidebar"] {{
  background: var(--bg-sidebar) !important;
  border-right: 1px solid var(--border) !important;
  padding: 0;
}}

/* Add top gradient strip to sidebar */
[data-testid="stSidebar"]::before {{
  content: "";
  display: block;
  height: 8px;
  width: 100%;
  background: var(--accent-primary);
  position: absolute;
  top: 0;
  left: 0;
  z-index: 1000;
}}

.doc-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 12px 16px;
  margin-bottom: 8px;
  box-shadow: var(--shadow-sm);
  transition: box-shadow 0.2s ease, transform 0.2s ease;
  cursor: default;
}}

.doc-card:hover {{
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}}

.doc-card-title {{
  font-family: 'DM Serif Display', serif;
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 4px;
}}

.doc-card-meta {{
  font-size: 11px;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', monospace;
}}

[data-testid="stChatMessage"] {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 20px;
  margin-bottom: 12px;
  box-shadow: var(--shadow-sm);
}}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
  border-left: 3px solid var(--accent-primary);
  background: var(--bg-secondary);
}}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {{
  border-left: 3px solid var(--accent-warm);
}}

.source-card {{
  background: var(--source-card-bg);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px 16px;
  margin: 6px 0;
  font-size: 13px;
  line-height: 1.6;
}}

.source-card-header {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--accent-primary);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}}

.source-excerpt {{
  font-family: 'DM Serif Display', serif;
  font-style: italic;
  color: var(--text-secondary);
  font-size: 13.5px;
  line-height: 1.7;
  border-left: 2px solid var(--accent-primary);
  padding-left: 12px;
  margin-top: 8px;
}}

.score-pill {{
  display: inline-block;
  background: var(--accent-primary);
  color: white;
  border-radius: 100px;
  padding: 2px 10px;
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  margin-right: 6px;
}}

[data-testid="baseButton-primary"] {{
  background: var(--accent-primary) !important;
  color: white !important;
  border: none !important;
  border-radius: 8px !important;
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  padding: 8px 18px !important;
  transition: background 0.2s ease, transform 0.15s ease !important;
}}

[data-testid="baseButton-primary"]:hover {{
  background: var(--accent-secondary) !important;
  transform: translateY(-1px) !important;
}}

[data-testid="baseButton-secondary"] {{
  background: transparent !important;
  border: 1px solid var(--border-strong) !important;
  color: var(--text-secondary) !important;
  border-radius: 8px !important;
}}

[data-testid="stChatInput"] textarea {{
  background: var(--bg-card) !important;
  border: 1.5px solid var(--border-strong) !important;
  border-radius: 12px !important;
  color: var(--text-primary) !important;
  font-family: 'DM Sans', sans-serif !important;
  font-size: 14px !important;
  padding: 14px 16px !important;
  transition: border-color 0.2s ease !important;
}}

[data-testid="stChatInput"] textarea:focus {{
  border-color: var(--accent-primary) !important;
  box-shadow: 0 0 0 3px rgba(26,122,110,0.12) !important;
}}

[data-testid="stMetric"] {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 14px;
}}

[data-testid="stMetricLabel"] {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted) !important;
}}

[data-testid="stMetricValue"] {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 20px;
  color: var(--accent-primary) !important;
}}

[data-testid="stProgress"] > div > div {{
  background: var(--accent-primary) !important;
}}

.sidebar-section {{
  padding: 16px 16px 8px 16px;
}}

.sidebar-label {{
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 10px;
}}

.empty-state {{
  text-align: center;
  padding: 60px 20px;
  color: var(--text-muted);
}}

.empty-state-icon {{
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.4;
}}

.empty-state-title {{
  font-family: 'DM Serif Display', serif;
  font-size: 22px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}}

.empty-state-body {{
  font-size: 14px;
  line-height: 1.6;
  max-width: 360px;
  margin: 0 auto;
  color: var(--text-muted);
}}

::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ 
  background: var(--border-strong);
  border-radius: 3px;
}}

@keyframes fadeSlideUp {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}

.fade-in {{
  animation: fadeSlideUp 0.35s ease forwards;
}}

.stSpinner > div {{
  border-top-color: var(--accent-primary) !important;
}}

[data-testid="stFileUploader"] {{
  border: 2px dashed var(--border-strong) !important;
  border-radius: 12px !important;
  background: var(--bg-secondary) !important;
  transition: border-color 0.2s ease !important;
}}

[data-testid="stFileUploader"]:hover {{
  border-color: var(--accent-primary) !important;
}}

[data-testid="stRadio"] label {{
  font-size: 13px;
  padding: 8px 12px;
  border-radius: 8px;
  transition: background 0.15s ease;
  display: block;
  cursor: pointer;
}}

[data-testid="stRadio"] label:hover {{
  background: var(--bg-secondary);
}}

[data-testid="stToggle"] {{
  accent-color: var(--accent-primary);
}}

[data-testid="stAlert"] {{
  border-radius: 10px !important;
  border-left-width: 4px !important;
  font-size: 13px !important;
}}

hr {{
  border-color: var(--border) !important;
  opacity: 1 !important;
}}
/* Studio Tabs */
/* Studio Tabs */
[data-testid="stTabs"] button[role="tab"] {{
  font-family: 'DM Sans', sans-serif !important;
  font-weight: 500 !important;
  font-size: 13px !important;
  color: var(--text-secondary) !important;
  border-bottom-color: transparent !important;
  transition: all 0.2s ease !important;
}}

[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {{
  color: var(--accent-primary) !important;
  border-bottom-color: var(--accent-primary) !important;
}}

/* Selectbox */
[data-testid="stSelectbox"] > div[data-baseweb="select"] {{
  background: var(--bg-card) !important;
  border: 1px solid var(--border-strong) !important;
  border-radius: 8px !important;
  color: var(--text-primary) !important;
}}

[data-testid="stSelectbox"] > div[data-baseweb="select"]:hover {{
  border-color: var(--accent-primary) !important;
}}

/* Flashcards - NotebookLM style */
.flashcard {{
  perspective: 1000px;
  margin-bottom: 20px;
}}
.flashcard-inner {{
  position: relative;
  width: 100%;
  height: 200px;
  text-align: center;
  transition: transform 0.8s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  transform-style: preserve-3d;
  cursor: pointer;
}}
.flashcard:hover .flashcard-inner {{
  transform: rotateY(180deg);
}}
.flashcard-front, .flashcard-back {{
  position: absolute;
  width: 100%;
  height: 100%;
  backface-visibility: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
}}
.flashcard-front {{
  background: var(--bg-card);
  font-family: 'DM Serif Display', serif;
  font-size: 1.3em;
  color: var(--text-primary);
}}
.flashcard-back {{
  background: var(--accent-primary);
  color: white;
  transform: rotateY(180deg);
  font-family: 'DM Sans', sans-serif;
  font-size: 1.1em;
}}

/* Studio Module Styles */
.studio-doc-title {{
  font-family: 'DM Serif Display', serif;
  font-size: 28px;
  color: var(--text-primary);
  line-height: 1.2;
  margin-bottom: 4px;
}}
.studio-doc-subtitle {{
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  margin-bottom: 24px;
}}
.exec-summary-box {{
  background: var(--source-card-bg);
  border-left: 4px solid var(--accent-primary);
  border-radius: 0 10px 10px 0;
  padding: 16px 20px;
  margin-bottom: 24px;
}}
.exec-summary-label {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--accent-primary);
  margin-bottom: 8px;
}}
.exec-summary-text {{
  font-family: 'DM Serif Display', serif;
  font-size: 17px;
  line-height: 1.6;
  color: var(--text-primary);
  font-style: italic;
}}
.key-fact-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 14px;
  margin-bottom: 10px;
  min-height: 90px;
}}
.key-fact-text {{
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  margin-bottom: 8px;
}}
.key-fact-source {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
  color: var(--accent-primary);
}}
.conflict-card {{
  background: rgba(229,62,62,0.06);
  border: 1px solid rgba(229,62,62,0.3);
  border-radius: 10px;
  padding: 14px 16px;
  margin-bottom: 10px;
  font-size: 13px;
  line-height: 1.7;
}}
.slide-card {{
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 14px;
  overflow: hidden;
  margin-bottom: 16px;
  box-shadow: var(--shadow-md);
  min-height: 220px;
}}
.slide-header {{
  padding: 10px 18px;
  display: flex;
  align-items: center;
  gap: 10px;
}}
.slide-number {{
  color: rgba(255,255,255,0.6);
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
}}
.slide-type-badge {{
  color: white;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}}
.slide-body {{
  padding: 20px 24px;
}}
.slide-stat-number {{
  font-family: 'DM Serif Display', serif;
  font-size: 64px;
  color: var(--accent-primary);
  line-height: 1;
}}
.slide-stat-label {{
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 8px 0 4px;
}}
.slide-stat-context {{
  font-size: 13px;
  color: var(--text-secondary);
}}
.slide-quote-mark {{
  font-family: 'DM Serif Display', serif;
  font-size: 80px;
  color: var(--accent-primary);
  line-height: 0.6;
  margin-bottom: 8px;
  opacity: 0.4;
}}
.slide-quote-text {{
  font-family: 'DM Serif Display', serif;
  font-style: italic;
  font-size: 20px;
  line-height: 1.5;
  color: var(--text-primary);
}}
.hero-stat-card {{
  text-align: center;
  padding: 40px 20px;
  background: var(--bg-card);
  border-radius: 16px;
  border: 1px solid var(--border);
}}
.hero-number {{
  font-family: 'DM Serif Display', serif;
  font-size: 80px;
  color: var(--accent-primary);
  line-height: 1;
}}
.hero-label {{
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 12px 0 8px;
}}
.hero-context {{
  font-size: 14px;
  color: var(--text-secondary);
  max-width: 400px;
  margin: 0 auto;
  line-height: 1.6;
}}
.hero-citation {{
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--accent-primary);
  margin-top: 12px;
}}
.infographic-header {{
  border-radius: 14px;
  padding: 28px 32px;
  margin-bottom: 20px;
}}
.infographic-title {{
  font-family: 'DM Serif Display', serif;
  font-size: 26px;
  color: white;
  margin-bottom: 4px;
}}
.infographic-subtitle {{
  font-size: 13px;
  color: rgba(255,255,255,0.75);
  font-family: 'DM Sans', sans-serif;
}}
"""
    return css

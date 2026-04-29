"""
Ethereal Glass Design System
Shared CSS tokens and HTML helpers for the Naukri AI Opportunity Finder dashboard.
All pages use this module for visual consistency.
IMPORTANT: All HTML helper functions return FLAT strings (no indentation)
to prevent Streamlit's markdown parser from treating them as code blocks.
"""

import streamlit as st


# Page names for navigation
PAGES = [
    ("app.py", "Home"),
    ("pages/1_🕸️_Scraper.py", "Scraper"),
    ("pages/2_🧠_AI_Scoring.py", "AI Scoring"),
    ("pages/3_📊_Dashboard.py", "Dashboard"),
]


def inject_css():
    """Inject the full Ethereal Glass CSS into the Streamlit app."""
    st.markdown(GLASS_CSS, unsafe_allow_html=True)


def top_nav(current_page: str):
    """Render a persistent top navigation bar using native buttons."""
    cols = st.columns(len(PAGES))
    for i, (page_path, label) in enumerate(PAGES):
        with cols[i]:
            is_active = page_path == current_page
            if is_active:
                st.markdown(
                    '<div style="text-align:center;padding:10px 16px;'
                    'background:linear-gradient(135deg,#8b5cf6,#6366f1);'
                    'border-radius:999px;color:#fff;font-weight:600;'
                    'font-size:0.85rem;cursor:default;">'
                    f'{label}</div>',
                    unsafe_allow_html=True
                )
            else:
                if st.button(label, width="stretch", key=f"nav_{i}"):
                    st.switch_page(page_path)


def page_header(title: str, subtitle: str, eyebrow: str = ""):
    """Render a consistent page header with optional eyebrow tag."""
    eyebrow_html = f'<div class="eyebrow">{eyebrow}</div>' if eyebrow else ""
    html = f'<div style="padding:8px 0 28px 0;">{eyebrow_html}<span class="page-title">{title}</span><p class="page-sub">{subtitle}</p></div>'
    st.markdown(html, unsafe_allow_html=True)


def _flat(html: str) -> str:
    """Remove newlines and extra spaces to prevent markdown code-block parsing."""
    return " ".join(html.split())


def section_header(title: str, subtitle: str = ""):
    """Render a section title + optional subtitle."""
    sub_html = f'<p class="section-sub">{subtitle}</p>' if subtitle else ""
    st.markdown(_flat(f'<p class="section-title">{title}</p>{sub_html}'), unsafe_allow_html=True)


def welcome_card(step: str, title: str, desc: str) -> str:
    """Return HTML for a double-bezel welcome card."""
    return _flat(f'''
<div class="welcome-card-outer">
  <div class="welcome-card-inner">
    <div class="welcome-step">{step}</div>
    <div class="welcome-card-title">{title}</div>
    <p class="welcome-card-desc">{desc}</p>
  </div>
</div>
''')


def scraper_form_start(title: str = "Search Configuration", desc: str = ""):
    """Open a double-bezel scraper form container."""
    st.markdown('<div class="scraper-form-outer"><div class="scraper-form-inner">', unsafe_allow_html=True)
    if title:
        st.markdown(_flat(f'<div class="scraper-form-title">{title}</div>'), unsafe_allow_html=True)
    if desc:
        st.markdown(_flat(f'<div class="scraper-form-desc">{desc}</div>'), unsafe_allow_html=True)


def scraper_form_end():
    """Close a double-bezel scraper form container."""
    st.markdown('</div></div>', unsafe_allow_html=True)


# ── Production AI Scoring Components ─────────────────────────────

def score_badge(score: int, size: str = "md") -> str:
    """Return a color-coded score badge."""
    if score >= 80:
        color = "#10b981"; bg = "rgba(16,185,129,0.12)"; bd = "rgba(16,185,129,0.35)"
    elif score >= 50:
        color = "#f59e0b"; bg = "rgba(245,158,11,0.12)"; bd = "rgba(245,158,11,0.35)"
    else:
        color = "#ef4444"; bg = "rgba(239,68,68,0.12)"; bd = "rgba(239,68,68,0.35)"
    sz = "32px" if size == "sm" else ("48px" if size == "lg" else "40px")
    fs = "0.85rem" if size == "sm" else ("1.15rem" if size == "lg" else "1rem")
    return _flat(f'''
<div style="display:inline-flex;align-items:center;justify-content:center;width:{sz};height:{sz};
border-radius:50%;background:{bg};border:2px solid {bd};color:{color};font-weight:800;
font-size:{fs};flex-shrink:0;">{score}</div>
''')


def score_breakdown_bar(semantic: int, penalty: int, final: int) -> str:
    """Return a stacked bar showing semantic score minus penalty."""
    semantic_w = max(0, min(100, semantic))
    penalty_w = max(0, min(100, penalty))
    return _flat(f'''
<div style="width:100%;margin:8px 0 12px 0;">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;">
    <span style="font-size:0.7rem;color:var(--t3);">Match</span>
    <span style="font-size:0.7rem;color:var(--t3);margin-left:auto;">-{penalty}</span>
    <span style="font-size:0.78rem;font-weight:700;color:var(--t1);">{final}</span>
  </div>
  <div style="background:var(--track);border-radius:50px;height:6px;overflow:hidden;display:flex;">
    <div style="width:{semantic_w}%;background:var(--g-bar);border-radius:50px 0 0 50px;"></div>
    <div style="width:{penalty_w}%;background:var(--r-bar);border-radius:0 50px 50px 0;"></div>
  </div>
</div>
''')


def skill_coverage_ring(coverage: float, matched: int, total: int) -> str:
    """Return an SVG donut chart for skill coverage."""
    pct = max(0, min(100, coverage))
    circumference = 2 * 3.14159 * 36
    offset = circumference * (1 - pct / 100)
    color = "#10b981" if pct >= 60 else ("#f59e0b" if pct >= 30 else "#ef4444")
    return _flat(f'''
<div style="display:flex;align-items:center;gap:16px;">
  <div style="position:relative;width:80px;height:80px;flex-shrink:0;">
    <svg width="80" height="80" viewBox="0 0 80 80" style="transform:rotate(-90deg);">
      <circle cx="40" cy="40" r="36" fill="none" stroke="var(--track)" stroke-width="6"/>
      <circle cx="40" cy="40" r="36" fill="none" stroke="{color}" stroke-width="6"
        stroke-dasharray="{circumference}" stroke-dashoffset="{offset}" stroke-linecap="round"/>
    </svg>
    <div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;flex-direction:column;">
      <span style="font-size:1.1rem;font-weight:800;color:var(--t1);">{int(pct)}%</span>
    </div>
  </div>
  <div>
    <div style="font-size:0.85rem;color:var(--t2);line-height:1.5;">
      <span style="font-weight:700;color:var(--t1);">{matched}</span> of <span style="font-weight:700;color:var(--t1);">{total}</span> market skills covered
    </div>
  </div>
</div>
''')


def model_status_card(is_trained: bool, samples: int, accuracy: str, trained_at: str) -> str:
    """Return HTML for model status panel."""
    status_color = "#10b981" if is_trained else "#64748b"
    status_text = "Active" if is_trained else "Baseline Mode"
    status_icon = "●" if is_trained else "○"
    acc_html = f'<div style="font-size:0.78rem;color:var(--t3);margin-top:4px;">Accuracy: <span style="color:var(--t1);font-weight:600;">{accuracy}</span></div>' if accuracy else ""
    samples_html = f'<div style="font-size:0.78rem;color:var(--t3);margin-top:2px;">Trained on <span style="color:var(--t1);font-weight:600;">{samples}</span> feedback samples</div>' if samples else ""
    date_html = f'<div style="font-size:0.7rem;color:var(--t4);margin-top:4px;">Last trained: {trained_at}</div>' if trained_at else ""
    return _flat(f'''
<div class="dash-card-outer"><div class="dash-card-inner">
  <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
    <span style="color:{status_color};font-size:1rem;">{status_icon}</span>
    <span style="font-size:0.9rem;font-weight:700;color:var(--t1);">{status_text}</span>
  </div>
  {acc_html}{samples_html}{date_html}
</div></div>
''')


def filter_chip(label: str, count: int = 0, active: bool = False) -> str:
    """Return HTML for a filter chip/badge."""
    bg = "var(--ac-glass)" if active else "var(--meta-bg)"
    bd = "var(--ac-bd)" if active else "var(--meta-bd)"
    tc = "var(--ac-txt)" if active else "var(--meta-t)"
    count_html = f'<span style="margin-left:4px;opacity:0.7;">({count})</span>' if count else ""
    return _flat(f'''
<span style="display:inline-flex;align-items:center;gap:4px;background:{bg};border:1px solid {bd};
border-radius:50px;padding:4px 12px;font-size:0.75rem;font-weight:600;color:{tc} !important;">
  {label}{count_html}
</span>
''')


# ══════════════════════════════════════════════════════════════════
#  FULL CSS
# ══════════════════════════════════════════════════════════════════
GLASS_CSS = """
<style>

/* ── 1. Token System ──────────────────────────────────────────── */
:root {
  --bg-a:#050505; --bg-b:#080810; --bg-c:#0a0a14;
  --orb-1:rgba(139,92,246,0.18);
  --orb-2:rgba(16,185,129,0.12);
  --orb-3:rgba(245,158,11,0.10);
  --orb-4:rgba(6,182,212,0.08);
  --glass-bg:rgba(255,255,255,0.035);
  --glass-hov:rgba(255,255,255,0.065);
  --glass-bd:rgba(255,255,255,0.07);
  --glass-top:rgba(255,255,255,0.28);
  --glass-spec:rgba(255,255,255,0.22);
  --glass-blur:blur(28px) saturate(180%);
  --glass-r:20px;
  --glass-rl:24px;
  --glass-shad:
    inset 0 1px 0 var(--glass-spec),
    inset 0 -1px 0 rgba(255,255,255,0.015),
    0 20px 50px rgba(0,0,0,0.35),
    0 4px 12px rgba(0,0,0,0.18);
  --glass-shad-hov:
    inset 0 1px 0 rgba(255,255,255,0.42),
    0 32px 70px rgba(0,0,0,0.42),
    0 8px 24px rgba(0,0,0,0.22);
  --t1:#f8fafc;
  --t2:#94a3b8;
  --t3:#64748b;
  --t4:rgba(255,255,255,0.18);
  --td:#94a3b8;
  --sb-bg:rgba(8,8,16,0.72); --hd-bg:rgba(5,5,10,0.82);
  --sb-bd:rgba(255,255,255,0.045); --div:rgba(255,255,255,0.055);
  --scr:rgba(255,255,255,0.12); --scr-hov:rgba(255,255,255,0.22);
  --btn-bg:rgba(255,255,255,0.06); --btn-hov:rgba(255,255,255,0.12);
  --btn-txt:rgba(255,255,255,0.92); --btn-top:rgba(255,255,255,0.25);
  --btn-thov:rgba(255,255,255,0.45);
  --inp-bg:rgba(255,255,255,0.04); --inp-bd:rgba(255,255,255,0.08);
  --inp-txt:rgba(255,255,255,0.92); --inp-ph:rgba(255,255,255,0.22);
  --inp-shad:inset 0 2px 10px rgba(0,0,0,0.30);
  --ac-glass:rgba(139,92,246,0.12); --ac-bd:rgba(139,92,246,0.28);
  --ac-top:rgba(139,92,246,0.55); --ac-txt:#c4b5fd;
  --ac-btn:linear-gradient(135deg,rgba(139,92,246,0.72) 0%,rgba(99,102,241,0.48) 100%);
  --ac-hov:linear-gradient(135deg,rgba(139,92,246,0.90) 0%,rgba(99,102,241,0.62) 100%);
  --meta-bg:rgba(255,255,255,0.04); --meta-bd:rgba(255,255,255,0.065); --meta-t:rgba(255,255,255,0.50);
  --track:rgba(255,255,255,0.05);
  --g-bar:linear-gradient(90deg,#10b981,#34d399); --g-glow:rgba(16,185,129,0.45);
  --a-bar:linear-gradient(90deg,#f59e0b,#fbbf24); --a-glow:rgba(245,158,11,0.40);
  --r-bar:linear-gradient(90deg,#ef4444,#f87171); --r-glow:rgba(239,68,68,0.40);
  --g-chip-bg:rgba(16,185,129,0.10); --g-chip-bd:rgba(16,185,129,0.25);
  --a-chip-bg:rgba(245,158,11,0.10); --a-chip-bd:rgba(245,158,11,0.25);
  --r-chip-bg:rgba(239,68,68,0.10); --r-chip-bd:rgba(239,68,68,0.25);
  --g-chip-t:#6ee7b7; --a-chip-t:#fcd34d; --r-chip-t:#fca5a5;
  --strip-g:#10b981; --strip-a:#f59e0b; --strip-r:#ef4444;
  --spring:cubic-bezier(0.34,1.56,0.64,1);
  --ease-out:cubic-bezier(0.16,1,0.3,1);
  --ease:cubic-bezier(0.25,0.46,0.45,0.94);
}

/* ── 2. Light-mode overrides ──────────────────────────────────── */
@media (prefers-color-scheme: light) {
  :root {
    --bg-a:#f8f7fb; --bg-b:#f0eff6; --bg-c:#e8e7f0;
    --orb-1:rgba(139,92,246,0.10); --orb-2:rgba(16,185,129,0.07); --orb-3:rgba(245,158,11,0.06); --orb-4:rgba(6,182,212,0.05);
    --glass-bg:rgba(255,255,255,0.55); --glass-hov:rgba(255,255,255,0.75);
    --glass-bd:rgba(180,175,220,0.35); --glass-top:rgba(255,255,255,0.95);
    --glass-spec:rgba(255,255,255,0.92); --glass-blur:blur(24px) saturate(140%);
    --glass-shad: inset 0 1px 0 var(--glass-spec), 0 10px 36px rgba(80,70,160,0.10), 0 3px 10px rgba(80,70,160,0.06);
    --glass-shad-hov: inset 0 1px 0 rgba(255,255,255,0.98), 0 18px 52px rgba(80,70,160,0.14), 0 5px 18px rgba(80,70,160,0.08);
    --t1:#0f172a; --t2:#475569; --t3:#64748b; --t4:rgba(15,23,42,0.20); --td:#475569;
    --sb-bg:rgba(248,247,251,0.72); --hd-bg:rgba(248,247,251,0.88);
    --sb-bd:rgba(15,23,42,0.06); --div:rgba(15,23,42,0.06);
    --scr:rgba(15,23,42,0.10); --scr-hov:rgba(15,23,42,0.20);
    --btn-bg:rgba(255,255,255,0.55); --btn-hov:rgba(255,255,255,0.78);
    --btn-txt:rgba(15,23,42,0.84); --btn-top:rgba(255,255,255,0.96); --btn-thov:rgba(255,255,255,1.0);
    --inp-bg:rgba(255,255,255,0.60); --inp-bd:rgba(180,175,220,0.35);
    --inp-txt:rgba(15,23,42,0.88); --inp-ph:rgba(15,23,42,0.26);
    --inp-shad:inset 0 1px 5px rgba(80,70,160,0.06);
    --ac-glass:rgba(139,92,246,0.08); --ac-bd:rgba(139,92,246,0.22);
    --ac-top:rgba(139,92,246,0.42); --ac-txt:#7c3aed;
    --ac-btn:linear-gradient(135deg,rgba(139,92,246,0.88) 0%,rgba(99,102,241,0.66) 100%);
    --ac-hov:linear-gradient(135deg,rgba(139,92,246,0.98) 0%,rgba(99,102,241,0.76) 100%);
    --meta-bg:rgba(255,255,255,0.50); --meta-bd:rgba(180,175,220,0.30); --meta-t:rgba(15,23,42,0.52);
    --track:rgba(15,23,42,0.06);
    --g-bar:linear-gradient(90deg,#059669,#10b981); --g-glow:rgba(5,150,105,0.25);
    --a-bar:linear-gradient(90deg,#d97706,#f59e0b); --a-glow:rgba(217,119,6,0.24);
    --r-bar:linear-gradient(90deg,#dc2626,#ef4444); --r-glow:rgba(220,38,38,0.24);
    --g-chip-bg:rgba(5,150,105,0.08); --g-chip-bd:rgba(5,150,105,0.20);
    --a-chip-bg:rgba(217,119,6,0.08); --a-chip-bd:rgba(217,119,6,0.20);
    --r-chip-bg:rgba(220,38,38,0.08); --r-chip-bd:rgba(220,38,38,0.20);
    --g-chip-t:#047857; --a-chip-t:#b45309; --r-chip-t:#b91c1c;
    --strip-g:#059669; --strip-a:#d97706; --strip-r:#dc2626;
  }
}

/* ── 3. App background ───────────────────────────────────────── */
.stApp {
  background:
    radial-gradient(ellipse 70% 50% at 8% 10%, var(--orb-1) 0%, transparent 55%),
    radial-gradient(ellipse 60% 45% at 92% 85%, var(--orb-2) 0%, transparent 55%),
    radial-gradient(ellipse 50% 40% at 75% 15%, var(--orb-3) 0%, transparent 55%),
    radial-gradient(ellipse 45% 35% at 30% 80%, var(--orb-4) 0%, transparent 55%),
    linear-gradient(165deg, var(--bg-a) 0%, var(--bg-b) 45%, var(--bg-c) 100%) !important;
  background-attachment: fixed !important;
}

/* ── 4. Font ──────────────────────────────────────────────────── */
/* Apply font to main containers instead of aggressive * wildcard to avoid breaking Streamlit icons */
.stApp { font-family: -apple-system,'SF Pro Display','Segoe UI',system-ui,sans-serif !important; }
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6, .stApp a, .stApp button, .stApp li {
  font-family: -apple-system,'SF Pro Display','Segoe UI',system-ui,sans-serif;
}
/* Force Streamlit expander arrows and icons to render correctly */
.stApp [class*="material-symbols"], 
.stApp [class*="material-icons"],
[data-testid="stExpanderToggleIcon"] p,
[data-testid="stExpanderToggleIcon"] svg,
[data-testid="stExpanderToggleIcon"] {
  font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}
/* Ensure code blocks stay monospace */
.stApp code, .stApp pre { font-family: 'SF Mono', ui-monospace, monospace !important; }
.stApp p, .stApp li { color: var(--t1) !important; }
.stApp h1,.stApp h2,.stApp h3,.stApp h4 { color:var(--t1) !important; letter-spacing:-0.3px !important; }
[data-testid="stMarkdownContainer"] p { color:var(--t1) !important; }
[data-testid="stCaptionContainer"], .stApp small { color:var(--t3) !important; }

/* ── 5. Header ────────────────────────────────────────────────── */
[data-testid="stHeader"] {
  background:var(--hd-bg) !important;
  backdrop-filter:var(--glass-blur) !important; -webkit-backdrop-filter:var(--glass-blur) !important;
  border-bottom:1px solid var(--sb-bd) !important;
}

/* ── 6. Sidebar ───────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background:var(--sb-bg) !important;
  backdrop-filter:var(--glass-blur) !important; -webkit-backdrop-filter:var(--glass-blur) !important;
  border-right:1px solid var(--sb-bd) !important;
  box-shadow:4px 0 40px rgba(0,0,0,0.14) !important;
}
[data-testid="stSidebar"] > div:first-child { background:transparent !important; }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
  font-size:0.68rem !important; font-weight:700 !important;
  text-transform:uppercase !important; letter-spacing:1.2px !important;
  color:var(--t3) !important; margin-bottom:10px !important;
}
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] li { color:var(--t1) !important; }
/* Hide sidebar collapse button — we use top nav instead */
[data-testid="stSidebarCollapsedControl"] { display:none !important; }
[data-testid="collapsedControl"] { display:none !important; }

/* ── 7. Expanders (Job Cards) ─────────────────────────────────── */
[data-testid="stExpander"] {
  background:var(--glass-bg) !important;
  backdrop-filter:var(--glass-blur) !important; -webkit-backdrop-filter:var(--glass-blur) !important;
  border:1px solid var(--glass-bd) !important;
  border-top:1px solid var(--glass-top) !important;
  border-radius:var(--glass-rl) !important;
  box-shadow:var(--glass-shad) !important;
  margin-bottom:12px !important; overflow:hidden !important;
  transition:transform 0.30s var(--ease-out), box-shadow 0.30s var(--ease-out) !important;
  position:relative;
}
[data-testid="stExpander"]::before {
  content:''; position:absolute; left:0; top:16px; bottom:16px; width:3px; border-radius:0 3px 3px 0;
  background:var(--strip-a); opacity:0.8; transition:opacity 0.25s var(--ease);
}
[data-testid="stExpander"]:hover {
  background:var(--glass-hov) !important;
  border-top-color:var(--glass-spec) !important;
  box-shadow:var(--glass-shad-hov) !important;
  transform:translateY(-2px) !important;
}
[data-testid="stExpander"]:hover::before { opacity:1; }
[data-testid="stExpander"] summary { color:var(--t1) !important; background:transparent !important; }
[data-testid="stExpander"] summary > span:last-child p,
[data-testid="stExpander"] summary > p:first-child {
  font-weight:600 !important; font-size:0.92rem !important;
  color:var(--t1) !important; margin:0 !important;
  white-space:normal; line-height:1.4;
}

/* ── 8. Alerts ────────────────────────────────────────────────── */
[data-testid="stAlert"] {
  background:var(--glass-bg) !important; backdrop-filter:var(--glass-blur) !important;
  border:1px solid var(--glass-bd) !important; border-top:1px solid var(--glass-top) !important;
  border-radius:var(--glass-r) !important; box-shadow:var(--glass-shad) !important;
}
[data-testid="stAlert"] p { color:var(--t1) !important; }

/* ── 9. Buttons ───────────────────────────────────────────────── */
.stButton > button {
  background:var(--btn-bg) !important; backdrop-filter:blur(16px) !important;
  border:1px solid var(--glass-bd) !important; border-top:1px solid var(--btn-top) !important;
  border-radius:999px !important; color:var(--btn-txt) !important;
  font-weight:600 !important; font-size:0.875rem !important; letter-spacing:0.1px !important;
  box-shadow:inset 0 1px 0 var(--glass-spec), 0 4px 14px rgba(0,0,0,0.10) !important;
  transition:all 0.28s var(--spring) !important; padding:10px 22px !important;
}
.stButton > button p { white-space: nowrap !important; }
.stButton > button:hover {
  background:var(--btn-hov) !important; border-top-color:var(--btn-thov) !important;
  transform:translateY(-2px) scale(1.02) !important;
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.42), 0 10px 28px rgba(0,0,0,0.16) !important;
}
.stButton > button:active { transform:translateY(0) scale(0.97) !important; }
.stButton > button[kind="primary"] {
  background:var(--ac-btn) !important; border-color:var(--ac-bd) !important;
  border-top-color:var(--ac-top) !important; color:#fff !important;
}
.stButton > button[kind="primary"]:hover { background:var(--ac-hov) !important; }
[data-testid="stDownloadButton"] > button {
  background:var(--btn-bg) !important; backdrop-filter:blur(16px) !important;
  border:1px solid var(--glass-bd) !important; border-top:1px solid var(--btn-top) !important;
  border-radius:999px !important; color:var(--btn-txt) !important; font-weight:600 !important;
  box-shadow:inset 0 1px 0 var(--glass-spec), 0 4px 14px rgba(0,0,0,0.10) !important;
  transition:all 0.28s var(--spring) !important;
}
[data-testid="stDownloadButton"] > button:hover { transform:translateY(-2px) !important; border-top-color:var(--btn-thov) !important; }

/* ── 10. File Uploader ────────────────────────────────────────── */
[data-testid="stFileUploadDropzone"] {
  background:var(--glass-bg) !important; backdrop-filter:var(--glass-blur) !important;
  border:1.5px dashed var(--glass-bd) !important; border-radius:var(--glass-rl) !important;
  transition:all 0.22s var(--ease-out) !important;
}
[data-testid="stFileUploadDropzone"]:hover { background:var(--glass-hov) !important; border-color:var(--glass-top) !important; }

/* ── 11. Inputs ───────────────────────────────────────────────── */
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"] > div, .stMultiSelect div[data-baseweb="select"] > div {
  background:var(--inp-bg) !important; backdrop-filter:blur(10px) !important;
  border:1px solid var(--inp-bd) !important; border-radius:var(--glass-r) !important;
  color:var(--inp-txt) !important;
  box-shadow:var(--inp-shad) !important; transition:all 0.22s var(--ease-out) !important;
}
.stTextInput input:focus, .stNumberInput input:focus {
  background:var(--glass-hov) !important; border-color:var(--ac-bd) !important;
  box-shadow:var(--inp-shad),0 0 0 3px var(--ac-glass) !important; outline:none !important;
}
.stTextInput input::placeholder, .stNumberInput input::placeholder { color:var(--inp-ph) !important; }
[data-testid="stTextInput"] label, [data-testid="stNumberInput"] label, [data-testid="stSlider"] label,
[data-testid="stSelectbox"] label, [data-testid="stMultiSelect"] label { color:var(--t2) !important; }

/* ── 12. DataFrame ────────────────────────────────────────────── */
.stDataFrame,[data-testid="stDataFrame"] {
  border:1px solid var(--glass-bd) !important; border-top:1px solid var(--glass-top) !important;
  border-radius:var(--glass-rl) !important; overflow:hidden !important;
  box-shadow:inset 0 1px 0 var(--glass-spec), 0 10px 32px rgba(0,0,0,0.12) !important;
}

/* ── 13. Misc ─────────────────────────────────────────────────── */
.stCodeBlock code,[data-testid="stCodeBlock"] {
  background:var(--glass-bg) !important; border:1px solid var(--glass-bd) !important;
  border-radius:var(--glass-r) !important;
}
hr { border:none !important; border-top:1px solid var(--div) !important; }
::-webkit-scrollbar { width:5px; height:5px; }
::-webkit-scrollbar-track { background:transparent; }
::-webkit-scrollbar-thumb { background:var(--scr); border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:var(--scr-hov); }

/* ════════════════════════════════════════════════════════════════
   CUSTOM COMPONENTS
   ════════════════════════════════════════════════════════════════ */

.page-title {
  font-size:clamp(1.55rem,4.2vw,2.4rem); font-weight:800; letter-spacing:-0.6px;
  background:linear-gradient(135deg,var(--t1) 0%,#c4b5fd 60%,var(--t2) 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  background-clip:text; margin:0 0 6px 0; line-height:1.12; display:block;
}
.page-sub { font-size:0.92rem; color:var(--t3); margin:0; letter-spacing:0.05px; }

.eyebrow {
  display:inline-flex; align-items:center; gap:6px;
  background:var(--ac-glass); border:1px solid var(--ac-bd);
  border-radius:999px; padding:4px 12px;
  font-size:0.65rem; font-weight:700; text-transform:uppercase; letter-spacing:0.15em;
  color:var(--ac-txt) !important; margin-bottom:14px;
}

.dash-card-outer {
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:var(--glass-rl); box-shadow:var(--glass-shad); padding:2px;
  height:100%; transition:transform 0.28s var(--spring),box-shadow 0.28s var(--ease-out);
}
.dash-card-outer:hover { transform:translateY(-2px); box-shadow:var(--glass-shad-hov); }
.dash-card-inner {
  background:rgba(255,255,255,0.02); border-radius:calc(var(--glass-rl) - 2px);
  box-shadow:inset 0 1px 1px rgba(255,255,255,0.08);
  padding:22px 24px; height:100%; box-sizing:border-box;
}
.dash-card-icon { font-size:1.4rem; margin-bottom:10px; }
.dash-card-title { font-size:1.0rem; font-weight:700; color:var(--t1); margin-bottom:12px; letter-spacing:-0.2px; }
.dash-card-body { color:var(--t2); font-size:0.88rem; line-height:1.6; }

.mini-stat { margin-bottom:10px; }
.mini-stat-value { font-size:1.3rem; font-weight:800; color:var(--t1); line-height:1.1; letter-spacing:-0.3px; }
.mini-stat-label { font-size:0.65rem; font-weight:700; text-transform:uppercase; letter-spacing:0.8px; color:var(--t3); margin-top:3px; }

.stats-grid {
  display:grid; grid-template-columns:2fr 1fr 1fr; grid-template-rows:1fr 1fr;
  gap:14px; margin:0 0 32px 0;
}
.stat-card { position:relative; overflow:hidden; transition:transform 0.30s var(--spring),box-shadow 0.30s var(--ease-out); }
.stat-card-outer {
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:var(--glass-rl); box-shadow:var(--glass-shad); padding:2px; height:100%;
}
.stat-card-inner {
  background:rgba(255,255,255,0.02); border-radius:calc(var(--glass-rl) - 2px);
  box-shadow:inset 0 1px 1px rgba(255,255,255,0.08);
  padding:22px 24px 20px; height:100%; box-sizing:border-box;
}
.stat-card:hover .stat-card-outer { box-shadow:var(--glass-shad-hov); transform:translateY(-3px); }
.stat-card::after {
  content:''; position:absolute; top:0; left:20%; right:20%; height:1px;
  background:linear-gradient(90deg,transparent,var(--glass-spec),transparent); pointer-events:none;
}
.stat-card:first-child { grid-row:1 / 3; }
.stat-card:first-child .stat-card-inner { display:flex; flex-direction:column; justify-content:center; }
.stat-icon { font-size:1.5rem; line-height:1; margin-bottom:12px; }
.stat-value { font-size:clamp(2rem,3.5vw,3rem); font-weight:800; line-height:1; color:var(--t1); letter-spacing:-0.6px; margin-bottom:6px; }
.stat-label { font-size:0.68rem; font-weight:700; text-transform:uppercase; letter-spacing:1px; color:var(--t3); }

.upskill-grid { display:grid; grid-template-columns:2fr 1fr 1fr; gap:14px; margin-bottom:28px; }
.upskill-card-outer {
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:var(--glass-rl); box-shadow:var(--glass-shad); padding:2px;
  transition:transform 0.28s var(--spring),box-shadow 0.28s var(--ease-out);
}
.upskill-card-outer:hover { transform:translateY(-3px); box-shadow:var(--glass-shad-hov); }
.upskill-card-inner {
  background:rgba(255,255,255,0.02); border-radius:calc(var(--glass-rl) - 2px);
  box-shadow:inset 0 1px 1px rgba(255,255,255,0.08); padding:18px 20px;
}
.upskill-label { font-size:1.05rem; font-weight:700; color:var(--t1); margin-bottom:5px; }
.upskill-count { font-size:0.78rem; color:var(--t3); }
.upskill-bar-track { background:var(--track); border-radius:50px; height:5px; margin-top:12px; overflow:hidden; }
.upskill-bar-fill {
  height:100%; border-radius:50px;
  background:linear-gradient(90deg,rgba(139,92,246,0.85),rgba(99,102,241,0.60));
  box-shadow:0 0 10px rgba(139,92,246,0.25);
}

.section-title { font-size:1.08rem; font-weight:700; color:var(--t1); margin:0 0 5px 0; letter-spacing:-0.2px; }
.section-sub { font-size:0.84rem; color:var(--t3); margin:0 0 18px 0; }

.filter-outer {
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:var(--glass-rl); box-shadow:var(--glass-shad); padding:2px; margin-bottom:18px;
}
.filter-inner {
  background:rgba(255,255,255,0.02); border-radius:calc(var(--glass-rl) - 2px);
  box-shadow:inset 0 1px 1px rgba(255,255,255,0.08); padding:18px 22px;
}
.result-count { font-size:0.82rem; color:var(--t3); margin:4px 0 0 0; }

.score-bar-wrap { background:var(--track); border-radius:50px; height:6px; width:100%; margin-bottom:18px; overflow:hidden; }
.sb-high { height:100%; border-radius:50px; background:var(--g-bar); box-shadow:0 0 10px var(--g-glow); }
.sb-mid { height:100%; border-radius:50px; background:var(--a-bar); box-shadow:0 0 10px var(--a-glow); }
.sb-low { height:100%; border-radius:50px; background:var(--r-bar); box-shadow:0 0 10px var(--r-glow); }

.job-meta { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:14px; }
.meta-pill {
  display:inline-flex; align-items:center; gap:5px;
  background:var(--meta-bg); border:1px solid var(--meta-bd);
  border-radius:50px; padding:5px 13px; font-size:12px;
  color:var(--meta-t) !important; white-space:nowrap;
}
.skills-row { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:14px; }
.skill-pill {
  display:inline-block; background:var(--ac-glass); border:1px solid var(--ac-bd); border-top:1px solid var(--ac-top);
  border-radius:50px; padding:4px 11px; font-size:11.5px; font-weight:500;
  color:var(--ac-txt) !important; box-shadow:inset 0 1px 0 var(--ac-glass);
}
.naukri-link {
  display:inline-flex; align-items:center; gap:6px; text-decoration:none !important;
  background:var(--ac-glass); border:1px solid var(--ac-bd); border-top:1px solid var(--ac-top);
  border-radius:999px; padding:8px 18px; font-size:13px; font-weight:600;
  color:var(--ac-txt) !important;
  box-shadow:inset 0 1px 0 var(--ac-glass),0 4px 14px rgba(0,0,0,0.08);
  transition:all 0.28s var(--spring);
}
.naukri-link:hover {
  background:rgba(139,92,246,0.20) !important; border-top-color:rgba(139,92,246,0.65) !important;
  transform:translateY(-1px); box-shadow:inset 0 1px 0 rgba(139,92,246,0.25),0 10px 24px rgba(0,0,0,0.12) !important;
}

.skill-tile {
  position:relative; display:inline-flex; align-items:center; gap:6px;
  background:var(--glass-bg); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  color:var(--t1) !important; padding:5px 12px; margin:4px 4px 4px 0;
  border-radius:999px; text-decoration:none !important; font-size:12.5px; font-weight:500;
  box-shadow:inset 0 1px 0 var(--glass-spec),0 3px 10px rgba(0,0,0,0.10);
  transition:all 0.26s var(--spring);
}
.skill-tile:hover {
  background:var(--glass-hov) !important; border-top-color:var(--btn-thov) !important;
  transform:translateY(-2px) scale(1.03);
  box-shadow:inset 0 1px 0 rgba(255,255,255,0.42),0 10px 26px rgba(0,0,0,0.14);
}
.skill-tile .rm-icon {
  display:inline-flex; align-items:center; justify-content:center;
  background:rgba(239,68,68,0.90); color:#fff !important;
  width:15px; height:15px; border-radius:50%; font-size:8.5px; font-weight:800;
  opacity:0; pointer-events:none; flex-shrink:0;
  border:1px solid rgba(248,113,113,0.45); transition:opacity 0.18s ease;
}
.skill-tile:hover .rm-icon { opacity:1; }

.welcome-wrap { max-width:760px; margin:56px auto 0; text-align:center; }
.welcome-title-big {
  font-size:clamp(1.6rem,4.2vw,2.2rem); font-weight:800;
  background:linear-gradient(135deg,var(--t1) 0%,#c4b5fd 50%,var(--t2) 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
  margin-bottom:12px;
}
.welcome-sub { font-size:0.98rem; color:var(--t3); margin-bottom:42px; line-height:1.6; }
.welcome-grid { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
.welcome-card-outer {
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:var(--glass-rl); box-shadow:var(--glass-shad); padding:2px;
  transition:transform 0.28s var(--spring),box-shadow 0.28s var(--ease-out);
}
.welcome-card-outer:hover { transform:translateY(-3px); box-shadow:var(--glass-shad-hov); }
.welcome-card-inner {
  background:rgba(255,255,255,0.02); border-radius:calc(var(--glass-rl) - 2px);
  box-shadow:inset 0 1px 1px rgba(255,255,255,0.08); padding:28px; text-align:left;
}
.welcome-step { font-size:0.65rem; font-weight:700; text-transform:uppercase; letter-spacing:1.2px; color:var(--t3); margin-bottom:10px; }
.welcome-card-title { font-size:1.1rem; font-weight:700; color:var(--t1); margin-bottom:10px; }
.welcome-card-desc { font-size:0.87rem; line-height:1.68; color:var(--t2); }
.welcome-em { color:var(--t1); font-weight:600; }

.scraper-form-outer {
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:var(--glass-rl); box-shadow:var(--glass-shad); padding:2px; margin-bottom:20px;
}
.scraper-form-inner {
  background:rgba(255,255,255,0.02); border-radius:calc(var(--glass-rl) - 2px);
  box-shadow:inset 0 1px 1px rgba(255,255,255,0.08); padding:28px 32px;
}
.scraper-form-title { font-size:1.15rem; font-weight:700; color:var(--t1); margin-bottom:4px; }
.scraper-form-desc { font-size:0.85rem; color:var(--t3); margin-bottom:20px; }

/* Pipeline */
.pipeline-wrap { display:flex; align-items:center; gap:8px; margin:20px 0 12px 0; flex-wrap:wrap; }
.pipeline-step { display:flex; flex-direction:column; align-items:center; gap:6px; min-width:70px; }
.pipeline-icon { width:32px; height:32px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:14px; font-weight:700; transition:all 0.4s var(--ease-out); }
.pipeline-step.done .pipeline-icon { background:rgba(16,185,129,0.15); color:#34d399; border:1px solid rgba(16,185,129,0.35); }
.pipeline-step.active .pipeline-icon { background:var(--ac-btn); color:#fff; border:1px solid var(--ac-bd); box-shadow:0 0 16px rgba(139,92,246,0.35); animation:pulse 1.5s infinite; }
.pipeline-step.pending .pipeline-icon { background:rgba(255,255,255,0.04); color:var(--t3); border:1px solid var(--glass-bd); }
.pipeline-label { font-size:0.68rem; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; }
.pipeline-step.done .pipeline-label { color:#34d399; }
.pipeline-step.active .pipeline-label { color:var(--ac-txt); }
.pipeline-step.pending .pipeline-label { color:var(--t3); }
.pipeline-line { flex:1; height:2px; min-width:20px; border-radius:1px; transition:all 0.5s var(--ease-out); }
.pipeline-line.done { background:linear-gradient(90deg,#10b981,#34d399); }
.pipeline-line.active { background:linear-gradient(90deg,var(--ac-btn),rgba(255,255,255,0.1)); }
.pipeline-line.pending { background:rgba(255,255,255,0.06); }
.pipeline-msg { font-size:0.85rem; color:var(--t2); margin-top:8px; }
.pipeline-jobs { font-size:0.78rem; color:var(--t3); margin-top:4px; font-weight:600; }
.log-tail { background:rgba(0,0,0,0.25); border:1px solid var(--glass-bd); border-radius:12px; padding:12px 16px; margin-top:16px; max-height:200px; overflow-y:auto; font-family:'SF Mono',monospace !important; font-size:0.75rem; line-height:1.6; }
.log-line { color:var(--t2); }
.log-time { color:var(--t3); margin-right:8px; font-size:0.7rem; }
.log-detail { color:var(--t3); padding-left:52px; }
@keyframes pulse { 0% { box-shadow:0 0 0 0 rgba(139,92,246,0.4); } 70% { box-shadow:0 0 0 10px rgba(139,92,246,0); } 100% { box-shadow:0 0 0 0 rgba(139,92,246,0); } }

/* ── Job Card Hover (for compact cards) ──────────────────────── */
.job-card-hover:hover {
  transform:translateY(-2px) !important;
  box-shadow:var(--glass-shad-hov) !important;
  border-top-color:var(--glass-spec) !important;
}

/* ── Score Breakdown Tooltip ─────────────────────────────────── */
.score-breakdown-wrap { margin:8px 0 14px 0; }
.score-breakdown-row { display:flex; align-items:center; gap:8px; margin-bottom:3px; }
.score-breakdown-label { font-size:0.72rem; color:var(--t3); width:70px; }
.score-breakdown-bar-bg { flex:1; background:var(--track); border-radius:50px; height:5px; overflow:hidden; }
.score-breakdown-bar-fill { height:100%; border-radius:50px; }
.score-breakdown-value { font-size:0.72rem; color:var(--t2); width:28px; text-align:right; }

/* ── Model Status Indicator ──────────────────────────────────── */
.model-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.model-dot.active { background:#10b981; box-shadow:0 0 6px rgba(16,185,129,0.5); }
.model-dot.baseline { background:var(--t3); }

/* ── Missing Skill Row ───────────────────────────────────────── */
.missing-skill-row { display:flex; align-items:center; gap:10px; margin:4px 0; }
.missing-skill-name { font-size:0.82rem; color:var(--t1); flex:1; }
.missing-skill-bar { flex:1; background:var(--track); border-radius:50px; height:4px; overflow:hidden; max-width:100px; }
.missing-skill-fill { height:100%; background:linear-gradient(90deg,rgba(139,92,246,0.7),rgba(99,102,241,0.4)); border-radius:50px; }
.missing-skill-count { font-size:0.72rem; color:var(--t3); width:40px; text-align:right; }

/* Responsive */
@media (max-width:960px) {
  .stats-grid { grid-template-columns:1fr 1fr; grid-template-rows:auto; gap:12px; }
  .stat-card:first-child { grid-row:auto; }
  .upskill-grid { grid-template-columns:1fr 1fr; gap:12px; }
  .stat-card-inner { padding:18px 18px 16px; }
  .welcome-grid { max-width:100%; }
}
@media (max-width:768px) {
  .stats-grid { grid-template-columns:1fr; gap:10px; }
  .upskill-grid { grid-template-columns:1fr; gap:10px; }
  .stat-card-inner { padding:16px 18px; display:flex; align-items:center; gap:16px; }
  .stat-icon { font-size:1.35rem; margin-bottom:0; flex-shrink:0; }
  .stat-value { font-size:1.9rem; margin-bottom:2px; }
  .stat-label { font-size:0.67rem; }
  .welcome-grid { grid-template-columns:1fr; gap:14px; }
  [data-testid="stExpander"] summary p { font-size:0.82rem !important; }
  .meta-pill { font-size:11px; padding:3px 9px; }
  .skill-pill { font-size:10.5px; padding:2px 8px; }
  .naukri-link { font-size:12px; padding:6px 12px; }
  .job-meta { gap:5px; }
  .filter-inner { padding:14px 16px; }
  .scraper-form-inner { padding:20px 18px; }
  .dash-card-inner { padding:18px 16px; }
  :root { --glass-blur:blur(16px) saturate(150%); }
}
@media (max-width:380px) {
  .stat-card-inner { padding:13px 14px; }
  .stat-value { font-size:1.6rem; }
}
@media (max-width:768px) {
  [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; }
  [data-testid="stColumn"] { min-width:100% !important; flex:1 1 100% !important; }
}
/* ── Stat Strip (horizontal compact stats bar) ───────────────── */
.stat-strip {
  display:flex; gap:12px; margin:0 0 24px 0; flex-wrap:wrap;
}
.stat-strip-card {
  flex:1; min-width:120px; display:flex; align-items:center; gap:12px;
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:16px; padding:14px 18px;
  box-shadow:var(--glass-shad);
  transition:transform 0.28s var(--spring), box-shadow 0.28s var(--ease-out);
}
.stat-strip-card:hover { transform:translateY(-2px); box-shadow:var(--glass-shad-hov); }
.stat-strip-icon {
  width:40px; height:40px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-size:1.1rem; flex-shrink:0;
}
.stat-strip-icon.purple { background:rgba(139,92,246,0.15); }
.stat-strip-icon.green { background:rgba(16,185,129,0.15); }
.stat-strip-icon.amber { background:rgba(245,158,11,0.15); }
.stat-strip-icon.blue { background:rgba(59,130,246,0.15); }
.stat-strip-val { font-size:1.35rem; font-weight:800; color:var(--t1); line-height:1; letter-spacing:-0.3px; }
.stat-strip-lbl { font-size:0.68rem; font-weight:600; text-transform:uppercase; letter-spacing:0.6px; color:var(--t3); margin-top:2px; }

/* ── Glass Section Wrapper ───────────────────────────────────── */
.glass-section {
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:var(--glass-rl); box-shadow:var(--glass-shad); padding:24px 28px;
  margin-bottom:20px; position:relative; overflow:hidden;
}
.glass-section::before {
  content:''; position:absolute; top:0; left:15%; right:15%; height:1px;
  background:linear-gradient(90deg,transparent,var(--glass-spec),transparent); pointer-events:none;
}
.glass-section-title {
  font-size:0.72rem; font-weight:700; text-transform:uppercase; letter-spacing:1px;
  color:var(--t3); margin:0 0 16px 0; display:flex; align-items:center; gap:8px;
}
.glass-section-title::before {
  content:''; width:3px; height:14px; border-radius:2px;
  background:linear-gradient(180deg,#8b5cf6,#6366f1); flex-shrink:0;
}

/* ── Skill Management Tags with Hover Delete ─────────────────── */
.skill-mgmt-cloud {
  display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 16px 0;
}
.skill-mgmt-tag {
  position:relative; display:inline-flex; align-items:center;
  padding:7px 16px; border-radius:10px; cursor:pointer;
  font-size:0.8rem; font-weight:500; white-space:nowrap;
  background:var(--glass-bg); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  color:var(--t1) !important; text-decoration:none !important;
  box-shadow:inset 0 1px 0 var(--glass-spec), 0 3px 10px rgba(0,0,0,0.10);
  transition:all 0.26s var(--spring);
}
.skill-mgmt-tag:hover {
  background:rgba(239,68,68,0.08) !important; border-color:rgba(239,68,68,0.3) !important;
  border-top-color:rgba(239,68,68,0.3) !important;
  transform:translateY(-1px);
}
.skill-mgmt-tag::before {
  content:'✕'; position:absolute; left:-7px; top:-7px;
  width:18px; height:18px; border-radius:50%;
  background:#ef4444; color:#fff;
  font-size:9px; font-weight:800; line-height:1;
  display:flex; align-items:center; justify-content:center;
  opacity:0; transform:scale(0.3);
  transition:opacity 0.22s var(--ease-out), transform 0.22s var(--spring);
  box-shadow:0 2px 6px rgba(239,68,68,0.4);
  z-index:5; pointer-events:none;
}
.skill-mgmt-tag:hover::before {
  opacity:1; transform:scale(1);
}

/* ── Section Gradient Divider ────────────────────────────────── */
.section-gradient-divider {
  height:1px; border:none; margin:28px 0;
  background:linear-gradient(90deg, transparent 0%, var(--glass-bd) 20%, rgba(139,92,246,0.25) 50%, var(--glass-bd) 80%, transparent 100%);
}

/* ── Enhanced Metric Cards ───────────────────────────────────── */
[data-testid="stMetric"] {
  background:var(--glass-bg) !important; backdrop-filter:blur(12px) !important;
  border:1px solid var(--glass-bd) !important; border-top:1px solid var(--glass-top) !important;
  border-radius:16px !important; padding:16px 18px !important;
  box-shadow:inset 0 1px 0 var(--glass-spec), 0 4px 14px rgba(0,0,0,0.08) !important;
  transition:transform 0.25s var(--spring) !important;
}
[data-testid="stMetric"]:hover { transform:translateY(-2px) !important; }
[data-testid="stMetric"] [data-testid="stMetricValue"] {
  font-size:1.4rem !important; font-weight:800 !important; letter-spacing:-0.3px !important;
}

/* ── Page Load Animation ─────────────────────────────────────── */
@keyframes fadeSlideUp {
  from { opacity:0; transform:translateY(16px); }
  to { opacity:1; transform:translateY(0); }
}
.fade-in { animation:fadeSlideUp 0.5s var(--ease-out) both; }
.fade-in-d1 { animation:fadeSlideUp 0.5s var(--ease-out) 0.05s both; }
.fade-in-d2 { animation:fadeSlideUp 0.5s var(--ease-out) 0.10s both; }
.fade-in-d3 { animation:fadeSlideUp 0.5s var(--ease-out) 0.15s both; }
.fade-in-d4 { animation:fadeSlideUp 0.5s var(--ease-out) 0.20s both; }

/* ── Intelligence Panel Cards ────────────────────────────────── */
.intel-card {
  background:var(--glass-bg); backdrop-filter:var(--glass-blur); -webkit-backdrop-filter:var(--glass-blur);
  border:1px solid var(--glass-bd); border-top:1px solid var(--glass-top);
  border-radius:var(--glass-r); box-shadow:var(--glass-shad); padding:18px 20px;
  margin-bottom:14px; transition:transform 0.25s var(--spring), box-shadow 0.25s var(--ease-out);
}
.intel-card:hover { transform:translateY(-1px); box-shadow:var(--glass-shad-hov); }
.intel-card-title {
  font-size:0.78rem; font-weight:700; text-transform:uppercase; letter-spacing:0.8px;
  color:var(--t3); margin:0 0 12px 0; display:flex; align-items:center; gap:8px;
}

.js-plotly-plot .plotly .gtitle,
.js-plotly-plot .plotly .xtick text,
.js-plotly-plot .plotly .ytick text,
.js-plotly-plot .plotly .legend text { fill:var(--t2) !important; }
</style>
"""

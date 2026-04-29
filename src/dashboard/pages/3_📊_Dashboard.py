import streamlit as st
import pandas as pd
import os
import re
import sys
from glob import glob
import plotly.express as px

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from src.ai.ai_opportunity_finder import JobAIModel
from src.dashboard.design import inject_css, page_header, top_nav

st.set_page_config(
    page_title="Dashboard — Dream Hunt",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

inject_css()
top_nav("pages/3_📊_Dashboard.py")
page_header("Dashboard", "Final clean data analysis of your entire job dataset", eyebrow="📊 Data Insights")

# ══════════════════════════════════════════════════════════════════
#  AI MODEL & DATA LOADING
# ══════════════════════════════════════════════════════════════════
@st.cache_resource
def get_ai_model():
    return JobAIModel()

ai_model = get_ai_model()
if not hasattr(ai_model, "profile_skills"):
    st.cache_resource.clear()
    ai_model = get_ai_model()


@st.cache_data(ttl=60)
def get_latest_data(folder: str = "data"):
    if not os.path.exists(folder):
        return None, None
    files = glob(os.path.join(folder, "*.csv"))
    files = [f for f in files if "applied_jobs" not in f and "rejected_jobs" not in f and "top_matches" not in f]
    if not files:
        return None, None
    latest = max(files, key=os.path.getmtime)
    return latest, pd.read_csv(latest)


latest_csv, df = get_latest_data()

if latest_csv is None or df is None:
    st.warning("No job data found. Go to the **🕸️ Scraper** page to fetch jobs first.")
    if st.button("Go to Scraper"):
        st.switch_page("pages/1_🕸️_Scraper.py")
    st.stop()

st.success(f"Loaded: `{os.path.basename(latest_csv)}`")

before = len(df)
df = df.drop_duplicates(subset=['Title', 'Company'], keep='first').reset_index(drop=True)
if before > len(df):
    st.caption(f"Removed {before - len(df)} duplicates.")

if 'AI_Score' not in df.columns:
    with st.spinner("AI is scoring jobs..."):
        df['AI_Score'] = ai_model.predict_scores(df)
df = df.sort_values('AI_Score', ascending=False).reset_index(drop=True)

# ══════════════════════════════════════════════════════════════════
#  STATS STRIP
# ══════════════════════════════════════════════════════════════════
total = len(df)
top = len(df[df['AI_Score'] >= 85])
good = len(df[df['AI_Score'] >= 50])
avg_score = int(df['AI_Score'].mean()) if 'AI_Score' in df.columns else 0

st.markdown(f'''
<div class="stat-strip fade-in">
  <div class="stat-strip-card">
    <div class="stat-strip-icon purple">📋</div>
    <div><div class="stat-strip-val">{total}</div><div class="stat-strip-lbl">Total Jobs</div></div>
  </div>
  <div class="stat-strip-card">
    <div class="stat-strip-icon green">🏆</div>
    <div><div class="stat-strip-val">{top}</div><div class="stat-strip-lbl">Top Matches 85+</div></div>
  </div>
  <div class="stat-strip-card">
    <div class="stat-strip-icon amber">✅</div>
    <div><div class="stat-strip-val">{good}</div><div class="stat-strip-lbl">Good Matches 50+</div></div>
  </div>
  <div class="stat-strip-card">
    <div class="stat-strip-icon blue">📈</div>
    <div><div class="stat-strip-val">{avg_score}%</div><div class="stat-strip-lbl">Avg Score</div></div>
  </div>
</div>
''', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  SCORE DISTRIBUTION
# ══════════════════════════════════════════════════════════════════
st.markdown('<div class="glass-section fade-in-d1"><div class="glass-section-title">Score Distribution</div>', unsafe_allow_html=True)

score_bins = pd.cut(df['AI_Score'], bins=[0, 49, 69, 84, 100], labels=['Low (<50)', 'Mid (50-69)', 'Good (70-84)', 'Top (85+)'])
score_dist = score_bins.value_counts().sort_index().reset_index()
score_dist.columns = ['Score Range', 'Count']

# Use a horizontal bar chart for distribution
fig_score = px.bar(
    score_dist, y='Score Range', x='Count', orientation='h',
    color='Score Range',
    color_discrete_map={
        'Low (<50)': '#ef4444',
        'Mid (50-69)': '#f59e0b',
        'Good (70-84)': '#8b5cf6',
        'Top (85+)': '#10b981',
    },
)
fig_score.update_layout(
    paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
    font_color='rgba(180,175,220,0.90)', margin=dict(l=0, r=0, t=10, b=0),
    xaxis=dict(gridcolor='rgba(255,255,255,0.06)', title=""),
    yaxis=dict(gridcolor='rgba(255,255,255,0.06)', title="", categoryorder='array', categoryarray=['Top (85+)', 'Good (70-84)', 'Mid (50-69)', 'Low (<50)']),
    showlegend=False, height=200
)
st.plotly_chart(fig_score, width="stretch", key="score_dist")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  PROFILE VS MARKET
# ══════════════════════════════════════════════════════════════════
st.markdown('<div class="glass-section fade-in-d2"><div class="glass-section-title">Your Profile vs The Market</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2, gap="large")

with c1:
    st.markdown("<div style='font-size:0.9rem;font-weight:600;margin-bottom:8px;color:var(--t1);'>Skill Coverage</div>", unsafe_allow_html=True)
    coverage = ai_model.get_skill_coverage(df)
    
    # Simple ring visualization using markdown
    cov_pct = coverage["coverage"]
    st.markdown(f"""
    <div style="display:flex; align-items:center; gap:20px; margin-bottom:20px;">
        <div style="width:100px; height:100px; border-radius:50%; background:conic-gradient(#8b5cf6 {cov_pct}%, var(--track) {cov_pct}%); display:flex; align-items:center; justify-content:center; position:relative;">
            <div style="width:84px; height:84px; border-radius:50%; background:var(--glass-bg); display:flex; align-items:center; justify-content:center; flex-direction:column;">
                <span style="font-size:1.4rem; font-weight:800; color:var(--t1); line-height:1;">{int(cov_pct)}%</span>
            </div>
        </div>
        <div>
            <div style="font-size:0.85rem; color:var(--t2);">You match <b>{coverage['matched']}</b> out of <b>{coverage['total_unique']}</b> total unique skills required in this dataset.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    if coverage["missing"]:
        st.markdown("<div style='font-size:0.8rem;color:var(--t3);margin-bottom:8px;'>Top Missing Skills (Learn these!):</div>", unsafe_allow_html=True)
        max_missing = coverage["missing"][0][1]
        for skill, count in coverage["missing"][:5]:
            pct = int((count / max_missing) * 100)
            st.markdown(f'''
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:6px;">
              <span style="font-size:0.8rem; color:var(--t2); width:120px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{skill}</span>
              <div style="flex:1; background:var(--track); border-radius:10px; height:6px;">
                <div style="width:{pct}%; background:linear-gradient(90deg, #ef4444, #f87171); height:100%; border-radius:10px;"></div>
              </div>
              <span style="font-size:0.75rem; color:var(--t3); width:40px; text-align:right;">{count}</span>
            </div>
            ''', unsafe_allow_html=True)

with c2:
    st.markdown("<div style='font-size:0.9rem;font-weight:600;margin-bottom:8px;color:var(--t1);'>Top Matched Skills</div>", unsafe_allow_html=True)
    if 'Skills' in df.columns:
        market_skills = {}
        for skills_str in df['Skills'].dropna():
            for s in str(skills_str).split(','):
                s = s.strip().lower()
                if len(s) >= 2:
                    market_skills[s] = market_skills.get(s, 0) + 1
        
        my_skills = ai_model.profile_skills
        matched_counts = []
        for s in my_skills:
            # Check exact or substring match in market
            count = sum(v for k, v in market_skills.items() if s in k or k in s)
            if count > 0:
                matched_counts.append((s.title(), count))
                
        matched_counts.sort(key=lambda x: x[1], reverse=True)
        
        if matched_counts:
            max_matched = matched_counts[0][1]
            for skill, count in matched_counts[:7]:
                pct = int((count / max_matched) * 100)
                st.markdown(f'''
                <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
                  <span style="font-size:0.8rem; color:var(--t2); width:120px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">{skill}</span>
                  <div style="flex:1; background:var(--track); border-radius:10px; height:6px;">
                    <div style="width:{pct}%; background:linear-gradient(90deg, #10b981, #34d399); height:100%; border-radius:10px;"></div>
                  </div>
                  <span style="font-size:0.75rem; color:var(--t3); width:40px; text-align:right;">{count}</span>
                </div>
                ''', unsafe_allow_html=True)
        else:
            st.caption("No matches found.")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  HIRING TRENDS
# ══════════════════════════════════════════════════════════════════
st.markdown('<div class="glass-section fade-in-d3"><div class="glass-section-title">Hiring Trends</div>', unsafe_allow_html=True)

t1, t2 = st.columns(2, gap="large")

with t1:
    st.markdown("<div style='font-size:0.9rem;font-weight:600;color:var(--t1);'>Top Companies</div>", unsafe_allow_html=True)
    top_cos = df['Company'].value_counts().nlargest(10).reset_index()
    top_cos.columns = ['Company', 'Count']
    fig_cos = px.bar(
        top_cos.sort_values('Count', ascending=True), 
        x='Count', y='Company', orientation='h',
        color='Count', color_continuous_scale='Purpor'
    )
    fig_cos.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color='rgba(180,175,220,0.90)', margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(gridcolor='rgba(255,255,255,0.06)', title=""),
        yaxis=dict(gridcolor='rgba(255,255,255,0.06)', title=""),
        showlegend=False, height=300, coloraxis_showscale=False
    )
    st.plotly_chart(fig_cos, width="stretch", key="top_cos")

with t2:
    st.markdown("<div style='font-size:0.9rem;font-weight:600;color:var(--t1);'>Top Locations</div>", unsafe_allow_html=True)
    loc_counts = df['Location'].value_counts().nlargest(10).reset_index()
    loc_counts.columns = ['Location', 'Count']
    fig_loc = px.bar(
        loc_counts.sort_values('Count', ascending=True), 
        x='Count', y='Location', orientation='h',
        color='Count', color_continuous_scale='Teal'
    )
    fig_loc.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color='rgba(180,175,220,0.90)', margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(gridcolor='rgba(255,255,255,0.06)', title=""),
        yaxis=dict(gridcolor='rgba(255,255,255,0.06)', title=""),
        showlegend=False, height=300, coloraxis_showscale=False
    )
    st.plotly_chart(fig_loc, width="stretch", key="top_loc")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  EXPERIENCE FIT
# ══════════════════════════════════════════════════════════════════
st.markdown('<div class="glass-section fade-in-d4"><div class="glass-section-title">Experience Fit</div>', unsafe_allow_html=True)

def extract_min_exp(exp_str):
    try:
        s = str(exp_str).strip().lower()
        if '-' in s:
            return int(s.split('-')[0].strip())
        if 'yr' in s or 'year' in s:
            nums = re.findall(r'\d+', s)
            return int(nums[0]) if nums else 0
    except Exception:
        pass
    return 0

df['Min_Exp'] = df['Experience'].apply(extract_min_exp)
exp_counts = df[df['Min_Exp'] > 0]['Min_Exp'].value_counts().sort_index().reset_index()
exp_counts.columns = ['Min Experience (Years)', 'Count']

if not exp_counts.empty:
    # Add an annotation line for user's experience
    user_exp = ai_model.min_experience
    fig_exp = px.bar(
        exp_counts, x='Min Experience (Years)', y='Count',
        color='Count', color_continuous_scale='Blues'
    )
    fig_exp.add_vline(x=user_exp, line_dash="dash", line_color="#ef4444", annotation_text=f"You ({user_exp} Yrs)", annotation_position="top right")
    
    fig_exp.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font_color='rgba(180,175,220,0.90)', margin=dict(l=0, r=0, t=10, b=0),
        xaxis=dict(gridcolor='rgba(255,255,255,0.06)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.06)'),
        coloraxis_showscale=False, height=300
    )
    st.plotly_chart(fig_exp, width="stretch", key="exp_dist")
else:
    st.caption("No experience data available to chart.")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('<div class="section-gradient-divider"></div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  FEEDBACK SUMMARY & RAW DATA
# ══════════════════════════════════════════════════════════════════
c_feed, c_raw = st.columns([1, 2], gap="large")

with c_feed:
    st.markdown('<div class="glass-section"><div class="glass-section-title">AI Feedback Summary</div>', unsafe_allow_html=True)
    
    applied = pd.read_csv("data/applied_jobs.csv") if os.path.exists("data/applied_jobs.csv") else pd.DataFrame()
    rejected = pd.read_csv("data/rejected_jobs.csv") if os.path.exists("data/rejected_jobs.csv") else pd.DataFrame()
    
    num_app = len(applied)
    num_rej = len(rejected)
    
    st.markdown(f'''
    <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
        <span style="color:var(--t2);">Jobs Applied (👍)</span>
        <span style="font-weight:bold; color:#10b981;">{num_app}</span>
    </div>
    <div style="display:flex; justify-content:space-between; margin-bottom:20px;">
        <span style="color:var(--t2);">Jobs Rejected (👎)</span>
        <span style="font-weight:bold; color:#ef4444;">{num_rej}</span>
    </div>
    ''', unsafe_allow_html=True)
    
    info = ai_model.get_model_info()
    status_color = "#10b981" if info.get('loaded') else "#f59e0b"
    status_text = "Trained (ML Active)" if info.get('loaded') else "Not Trained (Baseline Active)"
    
    st.markdown(f'''
    <div style="background:rgba(255,255,255,0.03); padding:12px 16px; border-radius:10px; border:1px solid var(--glass-bd); margin-bottom:16px;">
        <div style="font-size:0.75rem; color:var(--t3); margin-bottom:4px; text-transform:uppercase; letter-spacing:0.5px;">Model Status</div>
        <div style="display:flex; align-items:center; gap:8px;">
            <div style="width:8px; height:8px; border-radius:50%; background:{status_color};"></div>
            <span style="font-size:0.9rem; font-weight:600; color:var(--t1);">{status_text}</span>
        </div>
        <div style="font-size:0.8rem; color:var(--t2); margin-top:6px;">Mode: {info.get("scoring_mode", "")}</div>
        <div style="font-size:0.8rem; color:var(--t2);">Samples: {info.get("samples", 0)}</div>
    </div>
    ''', unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

with c_raw:
    st.markdown('<div class="glass-section"><div class="glass-section-title">Raw Data</div>', unsafe_allow_html=True)
    
    # Try to predict with breakdown to show new columns
    with st.spinner("Calculating multi-signal scores..."):
        df_breakdown = ai_model.predict_with_breakdown(df)
        
    st.dataframe(df_breakdown, height=250, width="stretch")
    
    st.download_button(
        "Download Full Dataset",
        df_breakdown.to_csv(index=False).encode("utf-8"),
        "naukri_ai_scored_jobs.csv",
        "text/csv",
        width="stretch",
    )
    st.markdown('</div>', unsafe_allow_html=True)

# Fix plotly text colors globally
st.markdown("""
<style>
.js-plotly-plot .plotly .gtitle,
.js-plotly-plot .plotly .xtick text,
.js-plotly-plot .plotly .ytick text,
.js-plotly-plot .plotly .legend text { fill:var(--t2) !important; }
</style>
""", unsafe_allow_html=True)


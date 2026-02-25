import os
import json
import hashlib
from datetime import datetime
from dotenv import load_dotenv

import streamlit as st
from rag_answer import load_vectorstore, retrieve_and_answer

# Load environment variables from .env file
load_dotenv()

st.set_page_config(page_title="QuantAc", page_icon="", layout="wide", initial_sidebar_state="expanded")

USERS_FILE  = "users.json"
HISTORY_DIR = "chat_histories"
os.makedirs(HISTORY_DIR, exist_ok=True)

def load_users():
    if not os.path.exists(USERS_FILE):
        default = {"admin": hash_pw("admin123")}
        save_users(default)
        return default
    with open(USERS_FILE, "r") as f:
        return json.load(f)

def save_users(users):
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_login(username, password):
    users = load_users()
    return username in users and users[username] == hash_pw(password)

def register_user(username, password):
    users = load_users()
    if username in users:
        return False, "Username already exists."
    if len(username) < 3:
        return False, "Username must be at least 3 characters."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    users[username] = hash_pw(password)
    save_users(users)
    return True, "Account created successfully."

def history_path(username):
    safe = username.replace("@", "_at_").replace(".", "_")
    return os.path.join(HISTORY_DIR, f"{safe}.json")

def load_user_history(username):
    path = history_path(username)
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f)

def save_user_history(username, history):
    with open(history_path(username), "w") as f:
        json.dump(history, f, indent=2)

def clear_user_history(username):
    path = history_path(username)
    if os.path.exists(path):
        os.remove(path)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #080c18; color: #c8d6e5; }
.stApp { background: linear-gradient(160deg, #080c18 0%, #0b1322 60%, #080f1c 100%); }
#MainMenu, footer { visibility: hidden; }
[data-testid="stSidebar"] { background: #05080f !important; border-right: 1px solid #12243a; }
[data-testid="stSidebar"] * { color: #7a9dbf !important; }
.login-logo { font-family: 'IBM Plex Mono', monospace; font-size: 2.2rem; color: #e0eeff; margin-bottom: 8px; font-weight: 600; letter-spacing: 1px; }
.login-sub { font-family: 'IBM Plex Mono', monospace; font-size: 0.65rem; color: #3a6a8a; letter-spacing: 2.5px; text-transform: uppercase; margin-bottom: 32px; }
.divider { display: flex; align-items: center; gap: 12px; margin: 20px 0; font-family: 'IBM Plex Mono', monospace; font-size: 0.55rem; color: #1e3a55; }
.divider::before, .divider::after { content: ''; flex: 1; border-top: 1px solid #0f2035; }
.auth-footer { font-family: 'IBM Plex Mono', monospace; font-size: 0.55rem; color: #1e3a55; margin-top: 16px; text-align: center; line-height: 1.6; }
.fin-header {
    background: linear-gradient(90deg, #0b1a30 0%, #091422 100%);
    border: 1px solid #1a3550; border-left: 4px solid #e8e8e8; border-radius: 4px;
    padding: 22px 28px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;
}
.fin-header h1 { font-family: 'IBM Plex Mono', monospace; font-size: 1.55rem; color: #e0eeff; margin: 0; }
.fin-header .sub { font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: #3a6a8a; letter-spacing: 2px; text-transform: uppercase; margin-top: 5px; }
.filter-badge { background: #e8e8e815; border: 1px solid #e8e8e840; color: #e8e8e8; font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; padding: 4px 12px; border-radius: 2px; letter-spacing: 1.5px; text-transform: uppercase; text-align: right; line-height: 1.8; }
.stat-box { background: #0a1525; border: 1px solid #152a40; border-radius: 4px; padding: 16px; text-align: center; }
.stat-box .val { font-family: 'IBM Plex Mono', monospace; font-size: 1.3rem; color: #e8e8e8; font-weight: 600; }
.stat-box .lbl { font-size: 0.6rem; color: #3a6080; letter-spacing: 1.5px; text-transform: uppercase; margin-top: 4px; }
.msg-user { background: #0d1e36; border: 1px solid #1a3555; border-right: 3px solid #2e7dd4; border-radius: 4px; padding: 14px 18px; margin: 8px 0 4px 0; color: #bdd0e5; font-size: 0.88rem; }
.msg-user .role-label { font-family: 'IBM Plex Mono', monospace; font-size: 0.58rem; color: #2e7dd4; letter-spacing: 2px; text-transform: uppercase; margin-bottom: 7px; }
.msg-ts { font-family: 'IBM Plex Mono', monospace; font-size: 0.54rem; color: #1e3a55; float: right; }
.msg-assistant-header { background: #09131f; border: 1px solid #122030; border-left: 3px solid #e8e8e8; border-bottom: none; border-radius: 4px 4px 0 0; padding: 10px 18px 8px 18px; margin: 4px 0 0 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.role-label-assistant { font-family: 'IBM Plex Mono', monospace; font-size: 0.58rem; color: #e8e8e8; letter-spacing: 2px; text-transform: uppercase; }
.intent-tag { display: inline-block; font-family: 'IBM Plex Mono', monospace; font-size: 0.56rem; padding: 2px 8px; border-radius: 2px; letter-spacing: 1px; text-transform: uppercase; }
.intent-risk        { background: #1a1a1a; color: #ffffff; border: 1px solid #555; }
.intent-outlook     { background: #1a1a1a; color: #cccccc; border: 1px solid #555; }
.intent-performance { background: #1a1a1a; color: #aaaaaa; border: 1px solid #555; }
.intent-people      { background: #1a1a1a; color: #bbbbbb; border: 1px solid #555; }
.intent-general     { background: #1a1a1a; color: #999999; border: 1px solid #555; }
.source-row { display: flex; gap: 8px; flex-wrap: wrap; padding: 10px 18px 12px 18px; background: #09131f; border: 1px solid #122030; border-left: 3px solid #e8e8e8; border-top: 1px solid #0f1e2e; border-radius: 0 0 4px 4px; margin-bottom: 12px; }
.source-card { background: #060d18; border: 1px solid #102030; border-radius: 3px; padding: 5px 10px; font-family: 'IBM Plex Mono', monospace; font-size: 0.6rem; color: #3a6080; line-height: 1.6; }
.source-card b { color: #6a9abf; display: block; }
.assistant-body { background: #09131f; border-left: 3px solid #e8e8e8; border-right: 1px solid #122030; padding: 4px 18px 14px 18px; font-size: 0.88rem; color: #bdd0e5; line-height: 1.7; }
.status-online { font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: #e8e8e8; background: #e8e8e810; border: 1px solid #e8e8e830; border-radius: 3px; padding: 8px 12px; margin-bottom: 8px; }
.status-offline { font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: #ff6b6b; background: #ff6b6b10; border: 1px solid #ff6b6b30; border-radius: 3px; padding: 8px 12px; margin-bottom: 8px; }
.user-pill { font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; color: #4a7a9a; background: #0a1828; border: 1px solid #1a3050; border-radius: 3px; padding: 6px 12px; margin-bottom: 14px; letter-spacing: 1px; }
.section-label { font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; color: #2a5070; letter-spacing: 1.5px; text-transform: uppercase; margin-bottom: 8px; margin-top: 4px; }
.hist-entry { background: #080f1c; border: 1px solid #0f1e2e; border-radius: 3px; padding: 7px 10px; margin-bottom: 5px; font-size: 0.7rem; color: #4a7090; line-height: 1.4; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-family: 'IBM Plex Sans', sans-serif; }
.hist-entry .h-ts { font-family: 'IBM Plex Mono', monospace; font-size: 0.54rem; color: #1e3a55; display: block; margin-bottom: 2px; }
.empty-state { text-align: center; padding: 70px 20px; color: #1a3050; }
.empty-state .glyph { font-family: 'IBM Plex Mono', monospace; font-size: 2.5rem; margin-bottom: 14px; color: #162840; }
.empty-state .msg { font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem; letter-spacing: 2px; text-transform: uppercase; line-height: 2; }
.stTextInput input { background: #09121e !important; border: 1px solid #1a3050 !important; border-radius: 3px !important; color: #c8d6e5 !important; font-family: 'IBM Plex Sans', sans-serif !important; }
.stTextInput input:focus { border-color: #e8e8e8 !important; box-shadow: none !important; }
.stSelectbox > div > div { background: #09121e !important; border: 1px solid #1a3050 !important; color: #c8d6e5 !important; border-radius: 4px !important; }
.stMarkdown p, .stMarkdown li { color: #bdd0e5 !important; font-size: 0.88rem; }
.stMarkdown h3 { color: #e0eeff !important; font-size: 0.95rem !important; font-family: 'IBM Plex Mono', monospace !important; border-bottom: 1px solid #1a3050; padding-bottom: 4px; margin-top: 12px; }
.stMarkdown strong { color: #ffffff !important; }
.stMarkdown ul li::marker { color: #ffffff; }
.stMarkdown code { background: #0d1e2e !important; color: #5db8ff !important; border-radius: 3px; padding: 1px 5px; }
[data-testid="stChatInput"] { background: transparent !important; border: none !important; }
[data-testid="stChatInput"] > div { background: transparent !important; border: none !important; }
[data-testid="stChatInput"] textarea { background: #0a1525 !important; border: 1px solid #1a3550 !important; border-radius: 3px !important; color: #e0eeff !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.85rem !important; padding: 10px 14px !important; }
[data-testid="stChatInput"] textarea:focus { border: 1px solid #e8e8e8 !important; box-shadow: none !important; }
[data-testid="stChatInput"] button { background: transparent !important; border: 1px solid #1a3550 !important; border-radius: 3px !important; }
[data-testid="stChatInput"] button:hover { border-color: #e8e8e8 !important; }
.stButton > button { background: transparent !important; border: 1px solid #e8e8e8 !important; color: #e8e8e8 !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.72rem !important; letter-spacing: 1px !important; text-transform: uppercase !important; border-radius: 3px !important; transition: all 0.18s !important; width: 100% !important; }
.stButton > button:hover { background: #e8e8e812 !important; box-shadow: 0 0 10px #e8e8e825 !important; }
[data-testid="stSidebar"] .stButton > button { border-color: #1a3050 !important; color: #4a7a9a !important; font-size: 0.68rem !important; margin-bottom: 4px !important; }
[data-testid="stSidebar"] .stButton > button:hover { border-color: #e8e8e855 !important; color: #e8e8e8 !important; background: #e8e8e808 !important; }
hr { border-color: #0f2035 !important; margin: 14px 0 !important; }
::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: #06090f; }
::-webkit-scrollbar-thumb { background: #152535; border-radius: 2px; }
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# Session state defaults
defaults = {
    "logged_in": False, "username": None, "display_name": None,
    "chat_history": [], "vectorstore": None, "vs_loaded": False,
    "query_count": 0, "auth_mode": "login",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

@st.cache_resource(show_spinner=False)
def get_vectorstore():
    return load_vectorstore("vectorstore/mda_faiss")

def process_query(query, company_filter, year_filter):
    company = None if company_filter == "All Companies" else company_filter
    year    = None if year_filter    == "All Years"     else year_filter
    st.session_state.chat_history.append({
        "role": "user", "content": query,
        "timestamp": datetime.now().strftime("%d %b %Y, %H:%M")
    })
    st.session_state.query_count += 1
    with st.spinner("Retrieving context and generating answer..."):
        try:
            result = retrieve_and_answer(
                st.session_state.vectorstore, query,
                company_filter=company, year_filter=year, top_k=10, score_threshold=0.85
            )
        except Exception as e:
            result = {"answer": f"Error: {str(e)}", "sources": [], "intent": "general",
                      "company": company or "Unknown", "year": year or "All Years"}
    st.session_state.chat_history.append({
        "role": "assistant", "content": result["answer"], "sources": result["sources"],
        "intent": result["intent"], "company": result["company"], "year": result["year"],
        "timestamp": datetime.now().strftime("%d %b %Y, %H:%M")
    })
    save_user_history(st.session_state.username, st.session_state.chat_history)
    st.rerun()


# ══════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════
def show_login_page():
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none; }
        [data-testid="collapsedControl"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.markdown("<div class='login-logo'>QuantAc</div>", unsafe_allow_html=True)
        st.markdown("<div class='login-sub'>MD&A Intelligence Terminal</div>", unsafe_allow_html=True)

        # Username / password tabs
        mode = st.session_state.auth_mode
        col1, col2 = st.columns(2)
        with col1:
            if st.button("SIGN IN", key="tab_login", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()
        with col2:
            if st.button("REGISTER", key="tab_reg", use_container_width=True):
                st.session_state.auth_mode = "register"
                st.rerun()

        st.markdown("<hr>", unsafe_allow_html=True)

        if mode == "login":
            st.markdown("<div style='font-family: IBM Plex Mono, monospace; font-size: 0.7rem; color: #e8e8e8; margin-bottom: 16px; letter-spacing: 0.5px;'>Sign in to your account</div>", unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="Enter username", key="li_user")
            password = st.text_input("Password", type="password", placeholder="Enter password", key="li_pass")
            
            if st.button("SIGN IN  →", key="do_login", use_container_width=True):
                if not username or not password:
                    st.error("Please fill in both fields.")
                elif verify_login(username, password):
                    st.session_state.logged_in    = True
                    st.session_state.username     = username
                    st.session_state.display_name = username
                    st.session_state.chat_history = load_user_history(username)
                    st.session_state.query_count  = sum(1 for m in st.session_state.chat_history if m["role"] == "user")
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            st.markdown("<div class='auth-footer'>📝 Default: admin / admin123</div>", unsafe_allow_html=True)

        else:
            st.markdown("<div style='font-family: IBM Plex Mono, monospace; font-size: 0.7rem; color: #e8e8e8; margin-bottom: 16px; letter-spacing: 0.5px;'>Create a new account</div>", unsafe_allow_html=True)
            new_user = st.text_input("Username", placeholder="Choose a username", key="reg_user")
            new_pass = st.text_input("Password", type="password", placeholder="Min. 6 characters", key="reg_pass")
            confirm  = st.text_input("Confirm Password", type="password", placeholder="Repeat password", key="reg_confirm")
            
            if st.button("CREATE ACCOUNT  →", key="do_register", use_container_width=True):
                if not new_user or not new_pass or not confirm:
                    st.error("Please fill in all fields.")
                elif new_pass != confirm:
                    st.error("Passwords do not match.")
                else:
                    ok, msg = register_user(new_user, new_pass)
                    if ok:
                        st.success(f"{msg} You can now sign in.")
                        st.session_state.auth_mode = "login"
                        st.rerun()
                    else:
                        st.error(msg)
            st.markdown("<div class='auth-footer'>🔒 Password must be at least 6 characters</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# MAIN APP
# ══════════════════════════════════════════════════════════════════
def show_main_app():
    if not st.session_state.vs_loaded:
        try:
            st.session_state.vectorstore = get_vectorstore()
            st.session_state.vs_loaded   = True
        except Exception as e:
            st.error(f"Failed to load vectorstore: {e}")
            st.info("Run `python build_vectorstore.py` first.")

    with st.sidebar:
        st.markdown("""<div style='font-family: IBM Plex Mono, monospace; font-size: 0.65rem; color: #e8e8e8; letter-spacing: 2.5px; text-transform: uppercase; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid #0f2035;'>◈ QUANTAC</div>""", unsafe_allow_html=True)

        display = st.session_state.display_name or st.session_state.username or ""
        st.markdown(f"<div class='user-pill'>● {display.upper()}</div>", unsafe_allow_html=True)

        if st.session_state.vs_loaded:
            st.markdown('<div class="status-online">● SYSTEM ONLINE</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="status-offline">● SYSTEM OFFLINE</div>', unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">FILTERS</div>', unsafe_allow_html=True)
        company_filter = st.selectbox("Company", ["All Companies","ICICI Bank","TCS","Infosys","Reliance Industries","Adani Power"], label_visibility="collapsed")
        year_filter    = st.selectbox("Year",    ["All Years","FY2024-25","FY2023-24"], label_visibility="collapsed")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">SUGGESTED QUERIES</div>', unsafe_allow_html=True)
        suggestions = [
            "What risks did ICICI Bank mention?",
            "What is TCS\'s strategy?",
            "How did Infosys perform in revenue growth?",
            "What is Reliance\'s future outlook?",
            "What are the key challenges faced by Adani Power?",
            "Compare the risks across all companies",
            "What is ICICI Bank\'s credit risk exposure?",
            "How did TCS perform in FY2025?",
        ]
        for s in suggestions:
            if st.button(s, key=f"sug_{hash(s)}"):
                if st.session_state.vs_loaded:
                    process_query(s, company_filter, year_filter)
                else:
                    st.warning("System not loaded.")

        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown('<div class="section-label">CHAT HISTORY</div>', unsafe_allow_html=True)
        user_msgs = [m for m in st.session_state.chat_history if m["role"] == "user"]
        if user_msgs:
            for msg in reversed(user_msgs[-8:]):
                ts      = msg.get("timestamp", "")
                preview = msg["content"][:55] + ("…" if len(msg["content"]) > 55 else "")
                st.markdown(f"<div class='hist-entry'><span class='h-ts'>{ts}</span>{preview}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-family: IBM Plex Mono, monospace; font-size: 0.6rem; color: #1a3050; padding: 6px 0;'>No history yet.</div>", unsafe_allow_html=True)

        st.markdown("<hr>", unsafe_allow_html=True)
        col_clear, col_logout = st.columns(2)
        with col_clear:
            if st.button("CLEAR", key="clear_btn"):
                st.session_state.chat_history = []
                st.session_state.query_count  = 0
                clear_user_history(st.session_state.username)
                st.rerun()
        with col_logout:
            if st.button("LOGOUT", key="logout_btn"):
                save_user_history(st.session_state.username, st.session_state.chat_history)
                st.session_state.logged_in    = False
                st.session_state.username     = None
                st.session_state.display_name = None
                st.session_state.chat_history = []
                st.session_state.query_count  = 0
                st.rerun()

        st.markdown("<div style='font-family: IBM Plex Mono, monospace; font-size: 0.55rem; color: #1a3050; margin-top: 16px; line-height: 2;'>sentence-transformers · FAISS<br>MMR · LLaMA 3.3 70B · Groq</div>", unsafe_allow_html=True)

    company_display = company_filter if company_filter != "All Companies" else "All Companies"
    year_display    = year_filter    if year_filter    != "All Years"     else "FY2023–25"

    st.markdown(f"""
    <div class='fin-header'>
        <div>
            <h1>QuantAc</h1>
            <div class='sub'>Everything you think you need, And more.</div>
        </div>
        <div class='filter-badge'>{company_display}<br>{year_display}</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    for col, val, label in [
        (c1, st.session_state.query_count, "Queries"),
        (c2, "ON" if st.session_state.vs_loaded else "OFF", "Status"),
        (c3, "5", "Companies"),
    ]:
        col.markdown(f"<div class='stat-box'><div class='val'>{val}</div><div class='lbl'>{label}</div></div>", unsafe_allow_html=True)

    st.markdown("<hr>", unsafe_allow_html=True)

    INTENT_CLASS = {"risk":"intent-risk","outlook":"intent-outlook","performance":"intent-performance","people":"intent-people","general":"intent-general"}

    for msg in st.session_state.chat_history:
        ts = msg.get("timestamp", "")
        if msg["role"] == "user":
            st.markdown(f"<div class='msg-user'><span class='msg-ts'>{ts}</span><div class='role-label'>YOU</div>{msg['content']}</div>", unsafe_allow_html=True)
        else:
            intent    = msg.get("intent", "general")
            company   = msg.get("company", "")
            year      = msg.get("year", "")
            intent_cls = INTENT_CLASS.get(intent, "intent-general")
            st.markdown(f"""
            <div class='msg-assistant-header'>
                <span class='role-label-assistant'>QUANTAC</span>
                <span class='intent-tag {intent_cls}'>{intent}</span>
                <span style='font-family: IBM Plex Mono,monospace; font-size:0.56rem; color:#1e4060;'>{company}</span>
                <span style='font-family: IBM Plex Mono,monospace; font-size:0.56rem; color:#1a3050;'>{year}</span>
                <span style='font-family: IBM Plex Mono,monospace; font-size:0.54rem; color:#1a3050; margin-left:auto;'>{ts}</span>
            </div>""", unsafe_allow_html=True)
            with st.container():
                st.markdown("<div class='assistant-body'>", unsafe_allow_html=True)
                st.markdown(msg["content"])
                st.markdown("</div>", unsafe_allow_html=True)
            seen_src, src_cards = set(), ""
            for s in msg.get("sources", []):
                key = f"{s['company']}-{s['year']}-{s['section']}"
                if key not in seen_src:
                    seen_src.add(key)
                    src_cards += f"<div class='source-card'><b>{s['company']}</b>{s['year']} · {s['section']}</div>"
            if src_cards:
                st.markdown(f"<div class='source-row'>{src_cards}</div>", unsafe_allow_html=True)

    if not st.session_state.chat_history:
        st.markdown("<div class='empty-state'><div class='glyph'>◈</div><div class='msg'>Type a Question</div></div>", unsafe_allow_html=True)

    user_input = st.chat_input("Ask about any company — risks, outlook, performance, strategy...", disabled=not st.session_state.vs_loaded)
    if user_input and user_input.strip():
        process_query(user_input.strip(), company_filter, year_filter)


# ══════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    show_login_page()
else:
    show_main_app()
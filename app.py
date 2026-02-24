import os
import json
import hashlib
from datetime import datetime
from dotenv import load_dotenv

import streamlit as st
from rag_answer import load_vectorstore, retrieve_and_answer

# Load environment variables from .env file
load_dotenv()
GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI         = os.getenv("REDIRECT_URI", "http://localhost:8501")
GOOGLE_ENABLED       = bool(GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET)

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT         = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT      = "https://www.googleapis.com/oauth2/v1/userinfo"

if GOOGLE_ENABLED:
    from authlib.integrations.requests_client import OAuth2Session

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

def set_google_username(google_email, new_username):
    """Allow Google users to set a custom username for login"""
    users = load_users()
    if new_username in users and users[new_username] != "__google__":
        return False, "Username already taken."
    if len(new_username) < 3:
        return False, "Username must be at least 3 characters."
    
    # Update the mapping
    users[new_username] = "__google__"
    # Keep the email mapping too
    users[google_email] = "__google__"
    save_users(users)
    return True, "Username set successfully!"

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

def get_google_auth_url():
    oauth = OAuth2Session(
        GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
        scope="openid email profile", redirect_uri=REDIRECT_URI,
    )
    auth_url, state = oauth.create_authorization_url(
        AUTHORIZATION_ENDPOINT, access_type="offline", prompt="select_account",
    )
    st.session_state["oauth_state"] = state
    return auth_url

def handle_google_callback():
    if not GOOGLE_ENABLED:
        return False
    params = st.query_params
    if "code" not in params:
        return False
    try:
        oauth = OAuth2Session(
            GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
            scope="openid email profile", redirect_uri=REDIRECT_URI,
            state=st.session_state.get("oauth_state"),
        )
        oauth.fetch_token(TOKEN_ENDPOINT, code=params["code"])
        userinfo = oauth.get(USERINFO_ENDPOINT).json()
        email = userinfo.get("email", "")
        name  = userinfo.get("name", email.split("@")[0])
        users = load_users()
        
        is_new_user = email not in users
        
        if is_new_user:
            users[email] = "__google__"
            save_users(users)
            # Set flag to show username setup modal on first login
            st.session_state.show_username_setup = True
        
        st.session_state.logged_in    = True
        st.session_state.username     = email
        st.session_state.display_name = name
        st.session_state.google_email = email
        st.session_state.chat_history = load_user_history(email)
        st.session_state.query_count  = sum(
            1 for m in st.session_state.chat_history if m["role"] == "user"
        )
        st.query_params.clear()
        return True
    except Exception as e:
        st.error(f"Google login failed: {e}")
        st.query_params.clear()
        return False

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; background-color: #080c18; color: #c8d6e5; }
.stApp { background: linear-gradient(160deg, #080c18 0%, #0b1322 60%, #080f1c 100%); }
#MainMenu, footer { visibility: hidden; }
[data-testid="stSidebar"] { background: #05080f !important; border-right: 1px solid #12243a; }
[data-testid="stSidebar"] * { color: #7a9dbf !important; }
.login-container { max-width: 380px; margin: 0 auto; padding: 40px 30px; }
.login-logo { font-family: 'IBM Plex Mono', monospace; font-size: 2.2rem; color: #e0eeff; margin-bottom: 8px; font-weight: 600; letter-spacing: 1px; }
.login-sub { font-family: 'IBM Plex Mono', monospace; font-size: 0.65rem; color: #3a6a8a; letter-spacing: 2.5px; text-transform: uppercase; margin-bottom: 32px; }
.google-btn-compact {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    background: #fff; color: #1a1a2e; border: 1px solid #ddd; border-radius: 4px;
    padding: 8px 16px; font-family: 'IBM Plex Sans', sans-serif; font-size: 0.8rem;
    font-weight: 500; text-decoration: none; width: 100%; box-sizing: border-box;
    transition: all 0.2s;
}
.google-btn-compact:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.3); transform: translateY(-1px); color: #1a1a2e; }
.google-btn-compact svg { width: 16px; height: 16px; }
.divider { display: flex; align-items: center; gap: 12px; margin: 20px 0; font-family: 'IBM Plex Mono', monospace; font-size: 0.55rem; color: #1e3a55; }
.divider::before, .divider::after { content: ''; flex: 1; border-top: 1px solid #0f2035; }
.auth-tabs { display: flex; gap: 10px; margin-bottom: 20px; }
.auth-tabs button { flex: 1; padding: 8px 14px; font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; border: 1px solid #1a3050; background: transparent; color: #4a7a9a; border-radius: 3px; cursor: pointer; transition: all 0.2s; text-transform: uppercase; letter-spacing: 1px; font-weight: 500; }
.auth-tabs button.active { border-color: #e8e8e8; color: #e8e8e8; background: #e8e8e810; }
.auth-tabs button:hover { border-color: #e8e8e8; color: #e8e8e8; }
.auth-form { display: flex; flex-direction: column; gap: 12px; }
.auth-form-row { display: flex; flex-direction: column; gap: 4px; }
.auth-form-row label { font-family: 'IBM Plex Mono', monospace; font-size: 0.62rem; color: #3a6a8a; letter-spacing: 1px; text-transform: uppercase; }
.auth-form-row input { background: #09121e !important; border: 1px solid #1a3050 !important; border-radius: 3px !important; color: #c8d6e5 !important; padding: 8px 12px !important; font-family: 'IBM Plex Sans', sans-serif !important; font-size: 0.85rem !important; }
.auth-form-row input:focus { border-color: #e8e8e8 !important; box-shadow: 0 0 0 2px #e8e8e815 !important; outline: none !important; }
.auth-submit { background: transparent !important; border: 1px solid #e8e8e8 !important; color: #e8e8e8 !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.7rem !important; letter-spacing: 1.5px !important; text-transform: uppercase !important; border-radius: 3px !important; padding: 10px 16px !important; font-weight: 500 !important; cursor: pointer; transition: all 0.2s !important; margin-top: 6px !important; }
.auth-submit:hover { background: #e8e8e812 !important; box-shadow: 0 0 8px #e8e8e820 !important; }
.auth-footer { font-family: 'IBM Plex Mono', monospace; font-size: 0.55rem; color: #1e3a55; margin-top: 16px; text-align: center; line-height: 1.6; }
.auth-error { background: #ff6b6b15; border: 1px solid #ff6b6b40; border-radius: 3px; padding: 8px 12px; color: #ff6b6b; font-size: 0.75rem; margin-bottom: 10px; }
.auth-success { background: #51cf6615; border: 1px solid #51cf6640; border-radius: 3px; padding: 8px 12px; color: #51cf66; font-size: 0.75rem; margin-bottom: 10px; }
.modal-overlay { position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: linear-gradient(135deg, #0b1e33 0%, #081420 100%); border: 1px solid #1a3555; border-radius: 6px; padding: 32px; max-width: 420px; box-shadow: 0 8px 32px rgba(0,0,0,0.5); }
.modal-title { font-family: 'IBM Plex Mono', monospace; font-size: 1.2rem; color: #e0eeff; margin-bottom: 8px; font-weight: 600; }
.modal-subtitle { font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem; color: #3a6a8a; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 20px; }
.modal-input { background: #09121e !important; border: 1px solid #1a3050 !important; border-radius: 3px !important; color: #c8d6e5 !important; padding: 10px 14px !important; font-family: 'IBM Plex Sans', sans-serif !important; font-size: 0.88rem !important; width: 100% !important; margin-bottom: 16px !important; }
.modal-input:focus { border-color: #e8e8e8 !important; box-shadow: 0 0 0 2px #e8e8e815 !important; outline: none !important; }
.modal-button { background: transparent !important; border: 1px solid #e8e8e8 !important; color: #e8e8e8 !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.7rem !important; letter-spacing: 1.5px !important; text-transform: uppercase !important; border-radius: 3px !important; padding: 10px 16px !important; font-weight: 500 !important; cursor: pointer; transition: all 0.2s !important; width: 100% !important; }
.modal-button:hover { background: #e8e8e812 !important; box-shadow: 0 0 8px #e8e8e820 !important; }
.modal-skip { background: transparent !important; border: 1px solid #1a3550 !important; color: #4a7a9a !important; font-family: 'IBM Plex Mono', monospace !important; font-size: 0.65rem !important; padding: 8px 12px !important; margin-top: 8px !important; }
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
    "query_count": 0, "auth_mode": "login", "show_username_setup": False,
    "google_email": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Handle Google callback BEFORE anything else renders
if not st.session_state.logged_in:
    if handle_google_callback():
        st.rerun()

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
# USERNAME SETUP MODAL (for Google users)
# ══════════════════════════════════════════════════════════════════
def show_username_setup_modal():
    """Modal for Google users to set a custom username"""
    st.markdown("""
    <div style='position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); display: flex; align-items: center; justify-content: center; z-index: 9999;'>
        <div style='background: linear-gradient(135deg, #0b1e33 0%, #081420 100%); border: 1px solid #1a3555; border-radius: 6px; padding: 32px; max-width: 420px; box-shadow: 0 8px 32px rgba(0,0,0,0.5);'>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='font-family: IBM Plex Mono, monospace; font-size: 1.2rem; color: #e0eeff; margin-bottom: 8px; font-weight: 600;'>Set Your Username</div>", unsafe_allow_html=True)
    st.markdown("<div style='font-family: IBM Plex Mono, monospace; font-size: 0.68rem; color: #3a6a8a; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 20px;'>Use this to log in without Google</div>", unsafe_allow_html=True)
    
    new_username = st.text_input("Choose a username", placeholder="e.g., john_doe", key="google_username_setup")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("SET USERNAME", key="set_username_btn", use_container_width=True):
            if not new_username:
                st.error("Please enter a username")
            else:
                ok, msg = set_google_username(st.session_state.google_email, new_username)
                if ok:
                    st.success("✅ Username set! You can now log in with this username.")
                    st.session_state.show_username_setup = False
                    st.rerun()
                else:
                    st.error(f"❌ {msg}")
    
    with col2:
        if st.button("SKIP FOR NOW", key="skip_username_btn", use_container_width=True):
            st.session_state.show_username_setup = False
            st.rerun()
    
    st.markdown("<div style='font-family: IBM Plex Mono, monospace; font-size: 0.65rem; color: #1a3050; margin-top: 16px; text-align: center; line-height: 1.6;'>You can always set this later in settings</div>", unsafe_allow_html=True)
    
    st.markdown("</div></div>", unsafe_allow_html=True)


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

        # Google OAuth button (only shown if configured) - COMPACT VERSION
        if GOOGLE_ENABLED:
            auth_url = get_google_auth_url()
            st.markdown(f"""
            <a href="{auth_url}" class="google-btn-compact" target="_self">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
                </svg>
                Google
            </a>
            """, unsafe_allow_html=True)
            st.markdown("<div class='divider'>OR</div>", unsafe_allow_html=True)

        # Username / password tabs with better styling
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
    # Show username setup modal if needed
    if st.session_state.show_username_setup:
        show_username_setup_modal()
        return
    
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
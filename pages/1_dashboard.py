import streamlit as st
import os

# Admin-first check
st.set_page_config(page_title="Dashboard — BuildIQ", layout="wide")

st.title("📊 Admin Dashboard")

# Secret access (both Render env and local secrets.toml)
SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")

st.metric("Active Members", "142")
st.metric("Departments", "8")
st.metric("Projects", "24")
st.metric("AI Copilot Status", "Active" if GROQ_API_KEY else "Offline")

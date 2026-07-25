import streamlit as st
import os
st.set_page_config(page_title="Chatbot — BuildIQ", layout="wide")
st.title("✦ ConstructrAI Copilot")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or st.secrets.get("GROQ_API_KEY")
st.info(f"AI Status: {'Hosted (Groq)' if GROQ_API_KEY else 'Local (No Key)'}")
st.write("Ask about projects, tasks, complaints, staffing, or schedule signals.")

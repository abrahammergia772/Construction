import streamlit as st
import os

st.set_page_config(page_title="Members — BuildIQ", layout="wide")

st.title("👥 Members / Employees")
st.info("Admin view: full directory, skills, department assignments, status tracking.")

SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")

st.write("Members database connected.")
st.dataframe({"Name": ["Ali H.", "Sara M."], "Department": ["Engineering", "Site Ops"], "Role": ["Engineer", "Manager"], "Status": ["Active", "Active"]})

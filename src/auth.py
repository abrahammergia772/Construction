import os

# Works on BOTH Render (env vars) and locally (secrets.toml or .env)
SUPABASE_URL = os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")

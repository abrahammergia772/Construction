import os

# Hybrid AI: Groq LLM + local scikit-learn models
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")

# Admin-first check: AI orchestrator activates for admin/manager roles
# For employee/customer roles, AI operates in read-only / limited mode

def orchestrate(query, workspace_data, user_role="admin"):
    if user_role == "admin" or user_role == "manager":
        # Full AI capabilities
        return {"status": "full", "query": query, "context": workspace_data}
    elif user_role == "employee":
        # Limited to assigned tasks/projects
        return {"status": "limited", "query": query, "scope": "assigned_only"}
    elif user_role == "customer":
        # Restricted to customer-linked records only
        return {"status": "restricted", "query": query, "scope": "customer_only"}
    return {"status": "denied", "message": "Access restricted"}

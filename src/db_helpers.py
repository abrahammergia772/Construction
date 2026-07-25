import joblib
import os

# NEVER use hardcoded absolute paths like /home/user/models/
# Use relative path from this file's directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, "models")

# Admin-first model loading (models must be pushed to repo or stored in MODEL_DIR)
def load_models():
    audit_model_path = os.path.join(MODEL_DIR, "audit_random_forest.joblib")
    audit_scaler_path = os.path.join(MODEL_DIR, "audit_scaler.joblib")
    project_path = os.path.join(MODEL_DIR, "project_model.joblib")
    complaint_path = os.path.join(MODEL_DIR, "complaint_model.joblib")

    return {
        "audit_model": joblib.load(audit_model_path) if os.path.exists(audit_model_path) else None,
        "audit_scaler": joblib.load(audit_scaler_path) if os.path.exists(audit_scaler_path) else None,
        "project_model": joblib.load(project_path) if os.path.exists(project_path) else None,
        "complaint_model": joblib.load(complaint_path) if os.path.exists(complaint_path) else None,
    }

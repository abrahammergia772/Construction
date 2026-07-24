"""Run a quick local verification of the risk model.

The live app trains the small deterministic demo model in memory at startup.
This command is useful when adapting its feature pipeline.
"""
from pathlib import Path
import sys

# Support `python scripts/train_risk_model.py` from a fresh clone.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ml.risk_model import FEATURES, assess_risk, get_model

if __name__ == "__main__":
    get_model()
    print(f"Trained local demo pipeline with features: {', '.join(FEATURES)}")
    print(assess_risk(45, 10, 180, 58, 6, 2))

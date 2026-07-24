"""A transparent, local delay-risk model for the MVP.

The training set is synthetic by design so a demo never implies it was trained
on real worker/client data. In production, retrain this pipeline on reviewed,
representative historical outcomes and register each approved model version.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = (
    "progress", "days_remaining", "planned_duration", "team_size",
    "delay_days", "high_priority_complaints",
)


@lru_cache(maxsize=1)
def get_model() -> Pipeline:
    """Fit a deterministic demo classifier without writing a binary artifact."""
    rng = np.random.default_rng(20260724)
    n = 1400
    planned_duration = rng.integers(60, 730, n)
    progress = rng.uniform(3, 98, n)
    days_remaining = rng.integers(0, 180, n)
    team_size = rng.integers(4, 100, n)
    delay_days = rng.integers(0, 46, n)
    complaints = rng.integers(0, 8, n)
    expected_progress = np.clip(100 * (1 - days_remaining / planned_duration), 0, 100)
    schedule_gap = expected_progress - progress
    latent_risk = (
        -2.1 + 0.075 * schedule_gap + 0.08 * delay_days + 0.33 * complaints
        + 0.009 * np.maximum(0, 18 - team_size) + rng.normal(0, 0.85, n)
    )
    probability = 1 / (1 + np.exp(-latent_risk))
    y = rng.binomial(1, probability)
    X = np.column_stack((progress, days_remaining, planned_duration, team_size, delay_days, complaints))
    return Pipeline([
        ("scale", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000, random_state=20260724)),
    ]).fit(X, y)


def assess_risk(
    progress: float,
    days_remaining: int,
    planned_duration: int,
    team_size: int,
    delay_days: int,
    high_priority_complaints: int,
) -> dict[str, object]:
    """Return an explainable risk estimate and operational follow-ups."""
    values = np.array([[progress, days_remaining, planned_duration, team_size, delay_days, high_priority_complaints]])
    probability = float(get_model().predict_proba(values)[0, 1])
    score = round(probability * 100)
    if score >= 76:
        level = "Critical"
    elif score >= 51:
        level = "High"
    elif score >= 26:
        level = "Moderate"
    else:
        level = "Low"

    expected_progress = max(0, min(100, 100 * (1 - days_remaining / planned_duration)))
    schedule_gap = expected_progress - progress
    drivers: list[str] = []
    recommendations: list[str] = []
    if schedule_gap >= 10:
        drivers.append(f"Progress is {schedule_gap:.0f} points behind the schedule pace implied by the remaining time.")
        recommendations.append("Run a 48-hour recovery-plan review with the project manager and site engineer.")
    elif progress < 50 and days_remaining <= 21:
        drivers.append("Less than half of the work is complete with three weeks or fewer remaining.")
        recommendations.append("Validate critical-path tasks and add an approved recovery schedule.")
    if delay_days > 0:
        drivers.append(f"The project already reports {delay_days} day(s) of delay.")
        recommendations.append("Assign an owner and due date to each open delay cause.")
    if high_priority_complaints > 0:
        drivers.append(f"{high_priority_complaints} high-priority client or site complaint(s) are unresolved.")
        recommendations.append("Escalate high-priority complaints at the next daily site coordination meeting.")
    if team_size < 15:
        drivers.append("The assigned team is relatively small for an active construction schedule.")
        recommendations.append("Confirm workforce coverage before changing scope or sequence.")
    if not drivers:
        drivers.append("Current pace, reported delay, staffing, and complaint signals do not indicate a strong delay pattern.")
        recommendations.append("Continue weekly schedule and issue review; record any scope changes promptly.")
    if not recommendations:
        recommendations.append("Review the current schedule, open issues, and resource plan with the project manager.")

    # Confidence here signals model decisiveness, not real-world validation.
    confidence = round(50 + abs(probability - 0.5) * 80)
    return {
        "risk_score": score,
        "risk_level": level,
        "confidence": min(90, confidence),
        "drivers": drivers[:4],
        "recommendations": recommendations[:4],
        "model_note": "Demo logistic-regression estimate trained on synthetic construction scenarios; validate against your reviewed historical data before operational use.",
    }

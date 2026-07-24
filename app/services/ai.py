"""Grounded construction operations copilot.

This service only receives the workspace data already authorized for the current
user. It never fabricates project records; hosted AI is optional.
"""
from __future__ import annotations

from typing import Any

from app.config import get_settings


def _match_project(message: str, projects: list[dict[str, Any]]) -> dict[str, Any] | None:
    lower = message.lower()
    return next((project for project in projects if project["name"].lower() in lower), None)


def local_answer(message: str, workspace: dict[str, Any]) -> tuple[str, list[str]]:
    lower = message.lower()
    projects = workspace["projects"]
    complaints = workspace["complaints"]
    tasks = workspace["tasks"]
    employees = workspace["employees"]
    match = _match_project(message, projects)

    if any(word in lower for word in ("complaint", "client issue", "unresolved", "safety")):
        open_items = [item for item in complaints if item["status"] != "Resolved"]
        if not open_items:
            return "There are no unresolved complaints in the records you can access.", ["Review complaint history"]
        items = open_items[:5]
        text = "Open complaint signals:\n\n" + "\n".join(
            f"• {item['priority']} · {item['category']}: {item['description']}" for item in items
        )
        return text, ["Escalate critical safety issues", "Assign an owner and due date"]

    if any(word in lower for word in ("behind", "schedule", "delay", "risk", "late")):
        targets = [match] if match else [project for project in projects if project["status"] in {"At risk", "Watch"}]
        if not targets:
            return "No accessible projects currently carry a Watch or At risk status. Review the latest field schedule before closing the loop.", ["Open project portfolio"]
        text = "Schedule signals needing review:\n\n" + "\n".join(
            f"• {project['name']}: {project['progress']}% complete, {project['days_remaining']} days remaining, {project['delay_days']} delay day(s), status {project['status']}."
            for project in targets
        )
        return text + "\n\nUse the delay-risk predictor to document factors and confirm the recovery plan with the project manager.", ["Run delay-risk assessment", "Review critical path"]

    if any(word in lower for word in ("task", "work", "action")):
        open_tasks = [task for task in tasks if task["status"] != "Done"]
        if not open_tasks:
            return "No open tasks are visible in your workspace.", ["Create a task"]
        return "Open work items:\n\n" + "\n".join(
            f"• {task['priority']} · {task['status']}: {task['title']}" for task in open_tasks[:6]
        ), ["Review blocked work", "Confirm task owners"]

    if any(word in lower for word in ("employee", "engineer", "team", "staff")) and employees:
        names = ", ".join(f"{employee['full_name']} ({employee['job_title']})" for employee in employees[:6])
        return f"Team records currently visible: {names}. Confirm live attendance and competency requirements before site assignment.", ["Open employee directory", "Review department workload"]

    if match:
        return (
            f"{match['name']} is a {match['project_type']} project at {match['progress']}% progress. "
            f"It has {match['days_remaining']} days remaining, {match['delay_days']} reported delay day(s), and is marked {match['status']}.",
            ["Run delay-risk assessment", "Review project tasks"],
        )

    metrics = workspace["metrics"]
    return (
        f"I can summarize only records you are authorized to access. The workspace currently shows {metrics['active_projects']} active project(s), "
        f"{metrics['at_risk_projects']} needing schedule attention, and {metrics['open_complaints']} open complaint(s). "
        "Try: “Which projects are behind schedule?” or “Show unresolved client complaints.”",
        ["Which projects are behind schedule?", "Show unresolved client complaints"],
    )


def grounding_context(workspace: dict[str, Any]) -> str:
    projects = workspace["projects"][:12]
    complaints = [item for item in workspace["complaints"] if item["status"] != "Resolved"][:10]
    tasks = [item for item in workspace["tasks"] if item["status"] != "Done"][:10]
    return "\n".join([
        "AUTHORIZED PROJECT RECORDS:",
        *[f"- {p['name']}: {p['progress']}% complete; {p['days_remaining']} days remaining; {p['delay_days']} delay days; {p['status']}" for p in projects],
        "AUTHORIZED OPEN COMPLAINTS:",
        *[f"- {c['priority']} {c['category']}: {c['description']}" for c in complaints],
        "AUTHORIZED OPEN TASKS:",
        *[f"- {t['priority']} {t['status']}: {t['title']}" for t in tasks],
    ])


def answer(message: str, workspace: dict[str, Any]) -> tuple[str, str, list[str]]:
    settings = get_settings()
    if not settings.openai_api_key:
        text, actions = local_answer(message, workspace)
        return text, "local operations copilot", actions
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.2,
            max_tokens=350,
            messages=[
                {"role": "system", "content": "You are ConstructrAI, a concise construction operations copilot. Use only the authorized records supplied. Never invent people, contracts, safety outcomes, or project facts. State uncertainty. You support—not replace—authorized human decisions, especially for safety, finance, employment, or contracts."},
                {"role": "system", "content": grounding_context(workspace)},
                {"role": "user", "content": message},
            ],
        )
        answer_text = completion.choices[0].message.content or "I could not produce an answer from the authorized records."
        return answer_text, "hosted AI", ["Verify source records", "Document an owner and due date"]
    except Exception:
        text, actions = local_answer(message, workspace)
        return text + "\n\nHosted AI was unavailable, so this is a local, record-grounded response.", "local operations copilot", actions

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.ml.risk_model import assess_risk
from app.repositories.supabase import SupabaseRepository, get_repository
from app.schemas import (
    AIRequest, AIResponse, ComplaintCreate, CustomerCreate, DepartmentCreate, DocumentCreate,
    EmployeeCreate, OnboardingRequest, ProjectCreate, PublicConfig, RiskRequest, RiskResponse,
    TaskCreate, TaskStatusUpdate,
)
from app.services.ai import answer

settings = get_settings()
app = FastAPI(
    title="ConstructrAI API",
    version="1.0.0",
    description="Role-aware construction operations portal backed by Supabase Postgres.",
)
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
    )


# Rate limiting (simple in-memory per IP for production hardening)
from collections import defaultdict
from time import time

_rate_limit_store: dict[str, list[float]] = defaultdict(list)

@app.middleware("http")
async def rate_limit(request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time()
    window = 60  # 1 minute
    max_requests = 60  # 1 request per second average
    # Clean old entries
    _rate_limit_store[client_ip] = [t for t in _rate_limit_store[client_ip] if now - t < window]
    if len(_rate_limit_store[client_ip]) >= max_requests:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Please slow down."})
    _rate_limit_store[client_ip].append(now)
    return await call_next(request)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def repository() -> SupabaseRepository:
    return get_repository()


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in is required.")
    return authorization.split(" ", 1)[1].strip()


def current_actor(
    token: Annotated[str, Depends(bearer_token)], repo: Annotated[SupabaseRepository, Depends(repository)],
) -> dict:
    return repo.actor(token)


def auth_identity(
    token: Annotated[str, Depends(bearer_token)], repo: Annotated[SupabaseRepository, Depends(repository)],
) -> dict:
    return repo.actor(token, require_profile=False)


@app.get("/api/health")
def health() -> dict[str, str | bool]:
    return {"status": "ok", "service": "ConstructrAI", "supabase_configured": settings.supabase_ready}


@app.get("/api/public-config", response_model=PublicConfig)
def public_config() -> dict[str, str]:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(status_code=503, detail="This deployment is missing Supabase public configuration.")
    return {"supabase_url": settings.supabase_url, "supabase_anon_key": settings.supabase_anon_key}


@app.get("/api/me")
def me(identity: Annotated[dict, Depends(auth_identity)]) -> dict:
    if not identity["profile"]:
        return {"setup_required": True, "user": identity["user"], "profile": None}
    return {"setup_required": False, "user": identity["user"], "profile": identity["profile"]}


@app.post("/api/onboarding")
def onboarding(payload: OnboardingRequest, identity: Annotated[dict, Depends(auth_identity)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    profile = repo.onboarding(identity["user"], payload.organization_name, payload.full_name, payload.role)
    return {"profile": profile}


@app.get("/api/dashboard")
def dashboard(actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return {**repo.dashboard(actor), "generated_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/departments/{department_id}/dashboard")
def department_dashboard(department_id: str, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    workspace = repo.dashboard(actor)
    department = next((item for item in workspace["departments"] if item["id"] == department_id), None)
    if not department:
        raise HTTPException(status_code=404, detail="Department not found in this workspace.")
    projects = [project for project in workspace["projects"] if project.get("department_id") == department_id]
    tasks = [task for task in workspace["tasks"] if task.get("department_id") == department_id]
    employees = [employee for employee in workspace["employees"] if employee.get("department_id") == department_id]
    return {"department": department, "projects": projects, "tasks": tasks, "employees": employees,
            "metrics": {"projects": len(projects), "open_tasks": sum(t["status"] != "Done" for t in tasks), "employees": len(employees)}}


@app.post("/api/departments", status_code=201)
def create_department(payload: DepartmentCreate, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.create_department(actor, payload.model_dump())


@app.post("/api/employees", status_code=201)
def create_employee(payload: EmployeeCreate, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.create_employee(actor, payload.model_dump(mode="json"))


@app.post("/api/employees/{employee_id}/invite")
def invite_employee(employee_id: str, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.invite_employee(actor, employee_id)


@app.post("/api/customers", status_code=201)
def create_customer(payload: CustomerCreate, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.create_customer(actor, payload.model_dump(mode="json"))


@app.post("/api/customers/{customer_id}/invite")
def invite_customer(customer_id: str, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.invite_customer(actor, customer_id)


@app.post("/api/projects", status_code=201)
def create_project(payload: ProjectCreate, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.create_project(actor, payload.model_dump(mode="json"))


@app.post("/api/tasks", status_code=201)
def create_task(payload: TaskCreate, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.create_task(actor, payload.model_dump(mode="json"))


@app.patch("/api/tasks/{task_id}")
def update_task(task_id: str, payload: TaskStatusUpdate, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.update_task_status(actor, task_id, payload.status)


@app.post("/api/complaints", status_code=201)
def create_complaint(payload: ComplaintCreate, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.create_complaint(actor, payload.model_dump(mode="json"))


@app.post("/api/documents", status_code=201)
def create_document(payload: DocumentCreate, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    return repo.create_document(actor, payload.model_dump(mode="json"))


@app.post("/api/predict-risk", response_model=RiskResponse)
def predict_risk(payload: RiskRequest, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    prediction = assess_risk(
        progress=payload.progress, days_remaining=payload.days_remaining, planned_duration=payload.planned_duration,
        team_size=payload.team_size, delay_days=payload.delay_days, high_priority_complaints=payload.high_priority_complaints,
    )
    body = payload.model_dump(mode="json")
    repo.record_prediction(actor, body, prediction)
    return {"project_name": payload.project_name, **prediction}


@app.post("/api/ai/ask", response_model=AIResponse)
def ai_ask(payload: AIRequest, actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    workspace = repo.dashboard(actor)
    text, source, actions = answer(payload.message, workspace)
    repo.record_ai(actor, payload.message, text, source)
    return {"answer": text, "source": source, "suggested_actions": actions}


@app.get("/api/search")
def search(
    actor: Annotated[dict, Depends(current_actor)],
    repo: Annotated[SupabaseRepository, Depends(repository)],
    query: str = "",
) -> dict:
    """Search workspace records by name, description, or title."""
    workspace = repo.dashboard(actor)
    q = (query or "").lower()
    if not q:
        return {"results": [], "query": query}
    results = {"projects": [], "tasks": [], "complaints": [], "employees": [], "customers": [], "documents": []}
    for p in workspace.get("projects", []):
        if q in (p.get("name") or "").lower() or q in (p.get("project_type") or "").lower():
            results["projects"].append(p)
    for t in workspace.get("tasks", []):
        if q in (t.get("title") or "").lower() or q in (t.get("description") or "").lower():
            results["tasks"].append(t)
    for c in workspace.get("complaints", []):
        if q in (c.get("description") or "").lower() or q in (c.get("category") or "").lower():
            results["complaints"].append(c)
    for e in workspace.get("employees", []):
        if q in (e.get("full_name") or "").lower() or q in (e.get("job_title") or "").lower():
            results["employees"].append(e)
    for cu in workspace.get("customers", []):
        if q in (cu.get("company_name") or "").lower() or q in (cu.get("contact_name") or "").lower():
            results["customers"].append(cu)
    for d in workspace.get("documents", []):
        if q in (d.get("name") or "").lower() or q in (d.get("document_type") or "").lower():
            results["documents"].append(d)
    return {"results": results, "query": query}


@app.get("/api/export/dashboard")
def export_dashboard(actor: Annotated[dict, Depends(current_actor)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    """Export authorized workspace data for external reporting or backup."""
    return repo.dashboard(actor)


@app.patch("/api/me")
def update_me(payload: dict, identity: Annotated[dict, Depends(auth_identity)], repo: Annotated[SupabaseRepository, Depends(repository)]) -> dict:
    user = identity["user"]
    profile = identity["profile"]
    if not profile:
        raise HTTPException(status_code=409, detail="Profile not set up. Complete onboarding first.")
    updates = {}
    if "full_name" in payload:
        updates["full_name"] = payload["full_name"]
    if updates:
        repo.update("profiles", user["id"], profile["organization_id"], updates)
        # Find employee record by profile_id and update
        employee_record = repo.one("employees", {"profile_id": user["id"], "organization_id": profile["organization_id"]})
        if employee_record:
            repo.update("employees", employee_record["id"], profile["organization_id"], updates)
    return {"updated": bool(updates), "profile": profile, "message": "Profile updated."}


@app.exception_handler(HTTPException)
def http_error(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


static_directory = Path(__file__).resolve().parent.parent / "static"
app.mount("/", StaticFiles(directory=static_directory, html=True), name="frontend")

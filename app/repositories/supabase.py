"""Supabase repository.

All calls use the server-only service role key. Browser clients use Supabase only
for Auth; application data is accessed through FastAPI so business authorization
is centralized here. RLS in the SQL migration remains a second line of defense.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Any

from fastapi import HTTPException
from supabase import Client, create_client

from app.config import get_settings


class SupabaseRepository:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.supabase_ready:
            raise HTTPException(
                status_code=503,
                detail="Supabase is not configured. Set SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_ROLE_KEY.",
            )
        self.client: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)

    @staticmethod
    def _data(response: Any) -> list[dict[str, Any]]:
        return response.data or []

    def user_from_token(self, token: str) -> dict[str, Any]:
        try:
            response = self.client.auth.get_user(token)
            user = response.user
            if not user:
                raise ValueError("No authenticated user")
            return {"id": user.id, "email": user.email or "", "metadata": user.user_metadata or {}}
        except Exception as exc:
            raise HTTPException(status_code=401, detail="Your session is invalid or expired. Please sign in again.") from exc

    def one(self, table: str, filters: dict[str, Any]) -> dict[str, Any] | None:
        query = self.client.table(table).select("*")
        for key, value in filters.items():
            query = query.eq(key, value)
        rows = self._data(query.limit(1).execute())
        return rows[0] if rows else None

    def profile(self, user_id: str) -> dict[str, Any] | None:
        return self.one("profiles", {"id": user_id})

    def actor(self, token: str, require_profile: bool = True) -> dict[str, Any]:
        user = self.user_from_token(token)
        profile = self.profile(user["id"])
        if require_profile and not profile:
            raise HTTPException(status_code=409, detail="Workspace setup is required for this account.")
        return {"user": user, "profile": profile}

    @staticmethod
    def assert_role(actor: dict[str, Any], *allowed: str) -> None:
        role = (actor.get("profile") or {}).get("role")
        if role not in allowed:
            raise HTTPException(status_code=403, detail="You do not have permission for this action.")

    def assert_references(self, actor: dict[str, Any], payload: dict[str, Any], references: dict[str, str]) -> None:
        """Reject cross-organization foreign IDs before service-role writes."""
        organization_id = self._org(actor)
        for field, table in references.items():
            record_id = payload.get(field)
            if record_id and not self.one(table, {"id": record_id, "organization_id": organization_id}):
                raise HTTPException(status_code=404, detail=f"The selected {field.replace('_id', '').replace('_', ' ')} is not in this workspace.")

    def insert(self, table: str, record: dict[str, Any]) -> dict[str, Any]:
        rows = self._data(self.client.table(table).insert(record).execute())
        if not rows:
            raise HTTPException(status_code=500, detail=f"Could not create {table.rstrip('s')}.")
        return rows[0]

    def update(self, table: str, record_id: str, organization_id: str, values: dict[str, Any]) -> dict[str, Any]:
        rows = self._data(self.client.table(table).update(values).eq("id", record_id).eq("organization_id", organization_id).execute())
        if not rows:
            raise HTTPException(status_code=404, detail="Record was not found in this workspace.")
        return rows[0]

    def log(self, actor: dict[str, Any], action: str, entity_type: str, entity_name: str, severity: str = "Low") -> None:
        profile = actor["profile"]
        self.insert("audit_events", {
            "organization_id": profile["organization_id"], "actor_profile_id": profile["id"],
            "actor_name": profile["full_name"], "action": action, "entity_type": entity_type,
            "entity_name": entity_name, "severity": severity,
        })

    def onboarding(self, user: dict[str, Any], organization_name: str, full_name: str) -> dict[str, Any]:
        existing = self.profile(user["id"])
        if existing:
            return existing
        organization = self.insert("organizations", {"name": organization_name, "created_by": user["id"]})
        department_records = [
            {"organization_id": organization["id"], "name": name, "code": code, "color": color}
            for name, code, color in [
                ("Site Operations", "SITE", "#1c6955"), ("Engineering & Design", "ENG", "#4e79cb"),
                ("Procurement & Supply", "PROC", "#8566c9"), ("Finance & Budget", "FIN", "#d28c20"),
                ("Health & Safety (HSE)", "HSE", "#d65350"), ("Quality Control", "QC", "#237a78"),
                ("Client Relations", "CLIENT", "#a26b90"),
            ]
        ]
        departments = self._data(self.client.table("departments").insert(department_records).execute())
        profile = self.insert("profiles", {
            "id": user["id"], "organization_id": organization["id"], "email": user["email"],
            "full_name": full_name, "role": "admin", "department_id": departments[0]["id"],
        })
        self.insert("employees", {
            "organization_id": organization["id"], "profile_id": user["id"], "department_id": departments[0]["id"],
            "full_name": full_name, "email": user["email"], "job_title": "Operations Administrator", "status": "Active",
        })
        self.log({"profile": profile}, "created workspace", "Organization", organization_name, "Low")
        return profile

    def _org(self, actor: dict[str, Any]) -> str:
        return actor["profile"]["organization_id"]

    def rows(self, table: str, org_id: str, order: str = "created_at", descending: bool = True, limit: int = 200) -> list[dict[str, Any]]:
        return self._data(self.client.table(table).select("*").eq("organization_id", org_id).order(order, desc=descending).limit(limit).execute())

    def dashboard(self, actor: dict[str, Any]) -> dict[str, Any]:
        profile = actor["profile"]
        org_id = self._org(actor)
        departments = self.rows("departments", org_id, "name", False)
        organization = self.one("organizations", {"id": org_id})
        if profile["role"] == "customer":
            customer = self.one("customers", {"profile_id": profile["id"], "organization_id": org_id})
            if not customer:
                raise HTTPException(status_code=403, detail="No customer account is linked to this user.")
            projects = self._data(self.client.table("projects").select("*").eq("organization_id", org_id).eq("customer_id", customer["id"]).order("updated_at", desc=True).execute())
            project_ids = [project["id"] for project in projects]
            complaints = self._data(self.client.table("complaints").select("*").eq("organization_id", org_id).eq("customer_id", customer["id"]).order("created_at", desc=True).execute())
            tasks = self._data(self.client.table("tasks").select("*").eq("organization_id", org_id).in_("project_id", project_ids or ["00000000-0000-0000-0000-000000000000"]).order("due_date").execute())
            employees: list[dict[str, Any]] = []
            customers = [customer]
            audit_events: list[dict[str, Any]] = []
            documents = self._data(self.client.table("documents").select("*").eq("organization_id", org_id).in_("project_id", project_ids or ["00000000-0000-0000-0000-000000000000"]).order("created_at", desc=True).execute())
        else:
            projects = self.rows("projects", org_id, "updated_at")
            complaints = self.rows("complaints", org_id, "created_at")
            tasks = self.rows("tasks", org_id, "due_date", False)
            employees = self.rows("employees", org_id, "full_name", False)
            customers = self.rows("customers", org_id, "company_name", False)
            audit_events = self.rows("audit_events", org_id, "created_at", True, 25) if profile["role"] in {"admin", "manager"} else []
            documents = self.rows("documents", org_id, "created_at")
        open_complaints = sum(c["status"] != "Resolved" for c in complaints)
        late_tasks = sum(t["status"] != "Done" and t.get("due_date") and t["due_date"] < date.today().isoformat() for t in tasks)
        metrics = {
            "active_projects": len([p for p in projects if p["status"] not in {"Completed", "Archived"}]),
            "at_risk_projects": len([p for p in projects if p["status"] in {"At risk", "Watch"}]),
            "open_complaints": open_complaints,
            "open_tasks": len([t for t in tasks if t["status"] != "Done"]),
            "late_tasks": late_tasks,
            "portfolio_progress": round(sum(float(p["progress"]) for p in projects) / len(projects), 1) if projects else 0,
        }
        return {"organization": organization, "profile": profile, "departments": departments, "employees": employees, "customers": customers,
                "projects": projects, "tasks": tasks, "complaints": complaints, "documents": documents, "audit_events": audit_events, "metrics": metrics}

    def create_department(self, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.assert_role(actor, "admin", "manager")
        record = self.insert("departments", {"organization_id": self._org(actor), **payload})
        self.log(actor, "created department", "Department", record["name"], "Low")
        return record

    def create_employee(self, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.assert_role(actor, "admin", "manager")
        self.assert_references(actor, payload, {"department_id": "departments"})
        record = self.insert("employees", {"organization_id": self._org(actor), **payload})
        self.log(actor, "created employee", "Employee", record["full_name"], "Low")
        return record

    def create_customer(self, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.assert_role(actor, "admin", "manager", "employee")
        record = self.insert("customers", {"organization_id": self._org(actor), **payload})
        self.log(actor, "created customer", "Customer", record["company_name"], "Low")
        return record

    def create_project(self, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.assert_role(actor, "admin", "manager")
        self.assert_references(actor, payload, {"customer_id": "customers", "department_id": "departments", "manager_profile_id": "profiles"})
        record = self.insert("projects", {"organization_id": self._org(actor), "created_by": actor["profile"]["id"], **payload})
        self.log(actor, "created project", "Project", record["name"], "Low")
        return record

    def create_task(self, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.assert_role(actor, "admin", "manager", "employee")
        if actor["profile"]["role"] == "employee":
            payload["assignee_profile_id"] = actor["profile"]["id"]
        self.assert_references(actor, payload, {"project_id": "projects", "department_id": "departments", "assignee_profile_id": "profiles"})
        record = self.insert("tasks", {"organization_id": self._org(actor), "created_by": actor["profile"]["id"], **payload})
        self.log(actor, "created task", "Task", record["title"], "Low")
        return record

    def create_complaint(self, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        profile = actor["profile"]
        if profile["role"] == "customer":
            customer = self.one("customers", {"profile_id": profile["id"], "organization_id": self._org(actor)})
            if not customer:
                raise HTTPException(status_code=403, detail="No customer profile is linked to this account.")
            payload["customer_id"] = customer["id"]
        self.assert_references(actor, payload, {"project_id": "projects", "customer_id": "customers"})
        record = self.insert("complaints", {"organization_id": self._org(actor), "reported_by": profile["id"], **payload})
        self.log(actor, "logged complaint", "Complaint", record["description"][:80], record["priority"])
        return record

    def record_prediction(self, actor: dict[str, Any], payload: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
        self.assert_references(actor, payload, {"project_id": "projects"})
        record = self.insert("risk_predictions", {
            "organization_id": self._org(actor), "project_id": payload.get("project_id"), "created_by": actor["profile"]["id"],
            "input_snapshot": payload, "risk_score": prediction["risk_score"], "risk_level": prediction["risk_level"],
            "drivers": prediction["drivers"], "recommendations": prediction["recommendations"],
        })
        self.log(actor, "ran delay-risk assessment", "Project risk", payload.get("project_name", "Project"), prediction["risk_level"])
        return record

    def record_ai(self, actor: dict[str, Any], question: str, answer: str, source: str) -> None:
        self.insert("ai_messages", {"organization_id": self._org(actor), "profile_id": actor["profile"]["id"], "question": question, "answer": answer, "source": source})
        self.log(actor, "asked operations copilot", "AI request", question[:80], "Low")


    def update_task_status(self, actor: dict[str, Any], task_id: str, status: str) -> dict[str, Any]:
        task = self.one("tasks", {"id": task_id, "organization_id": self._org(actor)})
        if not task:
            raise HTTPException(status_code=404, detail="Task was not found in this workspace.")
        role = actor["profile"]["role"]
        if role not in {"admin", "manager"} and task.get("assignee_profile_id") != actor["profile"]["id"]:
            raise HTTPException(status_code=403, detail="Only the assigned employee or a manager can update this task.")
        record = self.update("tasks", task_id, self._org(actor), {"status": status})
        self.log(actor, "updated task status", "Task", record["title"], "Low")
        return record

    def create_document(self, actor: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        self.assert_role(actor, "admin", "manager", "employee")
        self.assert_references(actor, payload, {"project_id": "projects"})
        record = self.insert("documents", {"organization_id": self._org(actor), "uploaded_by": actor["profile"]["id"], **payload})
        self.log(actor, "registered document", "Document", record["name"], "Low")
        return record

    def invite_customer(self, actor: dict[str, Any], customer_id: str) -> dict[str, Any]:
        self.assert_role(actor, "admin", "manager")
        customer = self.one("customers", {"id": customer_id, "organization_id": self._org(actor)})
        if not customer:
            raise HTTPException(status_code=404, detail="Customer was not found in this workspace.")
        if customer.get("profile_id"):
            raise HTTPException(status_code=409, detail="This customer already has a portal account.")
        try:
            settings = get_settings()
            invite = self.client.auth.admin.invite_user_by_email(customer["email"], {"data": {"full_name": customer["contact_name"]}, "redirect_to": settings.app_url})
            user_id = invite.user.id
            self.insert("profiles", {
                "id": user_id, "organization_id": self._org(actor), "email": customer["email"],
                "full_name": customer["contact_name"], "role": "customer",
            })
            record = self.update("customers", customer_id, self._org(actor), {"profile_id": user_id, "status": "Active"})
            self.log(actor, "invited customer to portal", "Customer", customer["company_name"], "Low")
            return record
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Supabase could not send the customer invitation. Check Auth email settings and redirect URLs.") from exc

    def invite_employee(self, actor: dict[str, Any], employee_id: str) -> dict[str, Any]:
        self.assert_role(actor, "admin", "manager")
        employee = self.one("employees", {"id": employee_id, "organization_id": self._org(actor)})
        if not employee:
            raise HTTPException(status_code=404, detail="Employee was not found in this workspace.")
        if employee.get("profile_id"):
            raise HTTPException(status_code=409, detail="This employee already has a portal account.")
        try:
            settings = get_settings()
            invite = self.client.auth.admin.invite_user_by_email(employee["email"], {"data": {"full_name": employee["full_name"]}, "redirect_to": settings.app_url})
            user_id = invite.user.id
            self.insert("profiles", {
                "id": user_id, "organization_id": self._org(actor), "email": employee["email"],
                "full_name": employee["full_name"], "role": employee.get("portal_role", "employee"), "department_id": employee.get("department_id"),
            })
            record = self.update("employees", employee_id, self._org(actor), {"profile_id": user_id, "status": "Invite pending"})
            self.log(actor, "invited employee to portal", "Employee", employee["full_name"], "Low")
            return record
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Supabase could not send the employee invitation. Check Auth email settings and redirect URLs.") from exc


@lru_cache(maxsize=1)
def get_repository() -> SupabaseRepository:
    return SupabaseRepository()

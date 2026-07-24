from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

Role = Literal["admin", "manager", "employee", "customer"]
Priority = Literal["Low", "Medium", "High", "Critical"]


class PublicConfig(BaseModel):
    supabase_url: str
    supabase_anon_key: str


class OnboardingRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    full_name: str = Field(min_length=2, max_length=120)
    role: Role = Field(default="admin", description="Initial workspace role. Only the first workspace user can select admin; others must be invited.")


class UserProfile(BaseModel):
    id: UUID
    organization_id: UUID
    email: EmailStr
    full_name: str
    role: Role
    department_id: UUID | None = None


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=12, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=500)
    color: str = Field(default="#1c6955", pattern=r"^#[0-9A-Fa-f]{6}$")


class EmployeeCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    job_title: str = Field(min_length=2, max_length=100)
    portal_role: Literal["employee", "manager"] = "employee"
    department_id: UUID | None = None
    phone: str | None = Field(default=None, max_length=40)
    status: Literal["Active", "Invite pending", "Inactive"] = "Invite pending"


class CustomerCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=160)
    contact_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    status: Literal["Active", "Prospect", "Inactive"] = "Prospect"
    notes: str | None = Field(default=None, max_length=1000)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=140)
    project_type: str = Field(min_length=3, max_length=80)
    customer_id: UUID | None = None
    department_id: UUID | None = None
    manager_profile_id: UUID | None = None
    progress: float = Field(default=0, ge=0, le=100)
    days_remaining: int = Field(default=90, ge=0, le=5000)
    planned_duration: int = Field(default=180, ge=1, le=10000)
    team_size: int = Field(default=1, ge=1, le=10000)
    delay_days: int = Field(default=0, ge=0, le=5000)
    budget: float = Field(default=0, ge=0, le=1_000_000_000)
    status: Literal["Planning", "On track", "Watch", "At risk", "Completed", "Archived"] = "Planning"
    start_date: date | None = None
    end_date: date | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=3, max_length=180)
    project_id: UUID | None = None
    department_id: UUID | None = None
    assignee_profile_id: UUID | None = None
    priority: Priority = "Medium"
    status: Literal["To do", "In progress", "Blocked", "Done"] = "To do"
    due_date: date | None = None
    description: str | None = Field(default=None, max_length=2000)


class ComplaintCreate(BaseModel):
    project_id: UUID | None = None
    customer_id: UUID | None = None
    category: Literal["Quality", "Safety", "Payment", "Schedule", "Communication", "Other"]
    priority: Priority
    description: str = Field(min_length=8, max_length=1500)


class RiskRequest(BaseModel):
    project_id: UUID | None = None
    project_name: str = Field(default="New project", max_length=140)
    progress: float = Field(ge=0, le=100)
    days_remaining: int = Field(ge=0, le=5000)
    planned_duration: int = Field(ge=1, le=10000)
    team_size: int = Field(ge=1, le=10000)
    delay_days: int = Field(default=0, ge=0, le=5000)
    high_priority_complaints: int = Field(default=0, ge=0, le=1000)


class RiskResponse(BaseModel):
    project_name: str
    risk_score: int
    risk_level: Literal["Low", "Moderate", "High", "Critical"]
    confidence: int
    drivers: list[str]
    recommendations: list[str]
    model_note: str


class AIRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


class AIResponse(BaseModel):
    answer: str
    source: Literal["local operations copilot", "hosted AI"]
    suggested_actions: list[str]


class DashboardResponse(BaseModel):
    profile: UserProfile
    departments: list[dict]
    employees: list[dict]
    customers: list[dict]
    projects: list[dict]
    tasks: list[dict]
    complaints: list[dict]
    audit_events: list[dict]
    metrics: dict[str, int | float]
    generated_at: datetime | None = None


class TaskStatusUpdate(BaseModel):
    status: Literal["To do", "In progress", "Blocked", "Done"]


class DocumentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    document_type: Literal["Blueprint", "Contract", "Safety report", "Budget report", "Progress report", "Other"]
    project_id: UUID | None = None
    url: str = Field(min_length=8, max_length=2000)
    notes: str | None = Field(default=None, max_length=1000)

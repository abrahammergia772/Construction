# ConstructrAI — Supabase + Render

A role-aware construction operations portal built with **HTML/CSS/JavaScript**, **FastAPI/Python**, **Supabase Postgres + Auth**, and an explainable local machine-learning risk predictor.

It is designed as a deployable foundation—not a demo-only mockup. The browser uses Supabase only for authentication; business data moves through the FastAPI service, which enforces role checks and writes audit records. The Supabase SQL migration also enables Row Level Security (RLS) as defense in depth.

## What is included

### Portals and dashboards

| Role | What the portal provides |
|---|---|
| **Admin** | Full organization command center, department hubs, employees, customers, projects, tasks, complaints, audit activity, AI, and risk assessments. |
| **Manager** | Operational management of departments, employees, customers, projects, tasks, complaints, AI, and risk assessments. |
| **Employee** | Workspace dashboard, tasks, projects, complaints, documents, AI support, and task-status updates for assigned work. |
| **Customer** | Restricted client portal showing only that customer’s projects, tasks, and complaints. |

### Construction operations features

- Admin, employee, customer, and department dashboards
- Organization / department setup with seeded construction departments
- Employee directory and Supabase Auth invitation endpoint
- Customer directory and project assignment
- Project delivery portfolio: progress, budget, team size, delay days, status, and accountable manager
- Action tracker: tasks, assignees, priority, due date, and completion state
- Client / site complaint queue with safety, quality, payment, schedule, and communication categories
- Controlled document register (stores approved HTTPS links; use Supabase Storage for uploaded files)
- Audit events for key write, AI, and risk-prediction actions
- AI operations copilot grounded only in the user-authorized workspace data
- Local Python/scikit-learn delay-risk predictor with readable drivers and recommendations

## Architecture

```text
Vanilla HTML/CSS/JS + Supabase Auth
              │ Bearer access token
              ▼
Render Web Service: FastAPI + authorization + AI + ML
              │ Service-role key (server only)
              ▼
Supabase Postgres, Auth, RLS, optional Storage
```

- The **Supabase anonymous key** is intentionally delivered to the browser via `/api/public-config`; it is public by design.
- The **Supabase service-role key** is never sent to the browser and must only exist in Render environment variables.
- The FastAPI service checks the Supabase session on each protected API request, scopes records to an organization, checks role permissions, then logs material actions.
- RLS policies in the migration prohibit cross-organization direct table access, even if a frontend is later added.

## Deploy to Supabase and Render

### 1. Create a Supabase project

1. Create a project at [supabase.com](https://supabase.com).
2. In **SQL Editor**, paste and run [`supabase/migrations/20260724_constructrai_schema.sql`](supabase/migrations/20260724_constructrai_schema.sql).
   - Or install Supabase CLI and run `supabase link --project-ref YOUR_REF` then `supabase db push`.
3. Under **Authentication → URL Configuration**, add these URLs:
   - Site URL: your final Render URL, e.g. `https://constructrai.onrender.com`
   - Redirect URLs: `https://constructrai.onrender.com/**` and `http://127.0.0.1:8000/**` for local work.
4. Under **Authentication → Providers → Email**, configure your desired email-confirmation and SMTP policy. Use custom SMTP before inviting real employees or customers.
5. Copy from **Project Settings → API**:
   - Project URL
   - `anon` / publishable key
   - `service_role` secret key (**Render only—never frontend or GitHub**)

### 2. Create a Render Web Service

1. Push this repository to GitHub.
2. In Render, select **New → Blueprint** and choose the repository. Render reads [`render.yaml`](render.yaml).
   - Or create a **Web Service** manually with build command `pip install -r requirements.txt` and start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
3. Set these secret environment variables in Render:

   ```dotenv
   SUPABASE_URL=https://YOUR-PROJECT-REF.supabase.co
   SUPABASE_ANON_KEY=your_anon_or_publishable_key
   SUPABASE_SERVICE_ROLE_KEY=your_service_role_secret
   APP_URL=https://YOUR-SERVICE.onrender.com
   # Optional; only needed when serving the frontend from another origin:
   CORS_ORIGINS=https://YOUR-FRONTEND.example
   # Optional hosted AI; omit to use only the local, data-grounded copilot.
   OPENAI_API_KEY=
   OPENAI_MODEL=gpt-4o-mini
   ```

4. Deploy. Verify `https://YOUR-SERVICE.onrender.com/api/health` returns `"supabase_configured": true`.
5. Visit the root URL, create the first account, then complete the **workspace setup**. The first workspace user becomes the **Admin** and receives construction department defaults.

> Render’s free tier can sleep after inactivity. Use a paid instance for a continuously available production portal.

## Local development

Requires Python 3.10+.

```bash
git clone <your-repository-url>
cd constructrai
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env
# Fill in the three Supabase variables in .env
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`. Add this local address to Supabase Auth redirect URLs before using email confirmation or invitations.

Run checks:

```bash
pytest -q
python scripts/train_risk_model.py
```

## AI and ML behavior

### Operations copilot

Without `OPENAI_API_KEY`, the copilot runs locally with deterministic, database-grounded operational answers. With a key, it sends only a compact context of records already authorized for the current user to the selected hosted AI provider. The application gracefully falls back to the local copilot when hosted AI is unavailable.

Before using real employee, customer, or contractual data with an external AI provider, obtain the appropriate approvals and configure a compliant retention / data-processing policy.

### Delay-risk predictor

`app/ml/risk_model.py` trains a reproducible logistic-regression model on an explicitly **synthetic** construction dataset. It considers progress, days remaining, planned duration, team size, reported delay, and high-priority complaint count. Its output is decision support—not a validated construction forecast or an autonomous decision.

For production: train on reviewed historical project outcomes, define data quality checks and human escalation thresholds, evaluate calibration and drift, and maintain an approved model/version register.

## Important API routes

All routes except health and public configuration require a Supabase bearer token.

| Method | Route | Role / purpose |
|---|---|---|
| `GET` | `/api/dashboard` | Role-scoped workspace dashboard |
| `POST` | `/api/onboarding` | Creates the first organization + Admin profile |
| `GET` | `/api/departments/{id}/dashboard` | Department hub |
| `POST` | `/api/employees` | Admin/manager employee record |
| `POST` | `/api/employees/{id}/invite` | Invite an employee/manager through Supabase Auth |
| `POST` | `/api/customers` | Customer record |
| `POST` | `/api/customers/{id}/invite` | Invite customer to their restricted portal |
| `POST` | `/api/projects` | Project record |
| `POST/PATCH` | `/api/tasks`, `/api/tasks/{id}` | Create/update work items |
| `POST` | `/api/complaints` | Client/site issue |
| `POST` | `/api/documents` | Register approved document link |
| `POST` | `/api/predict-risk` | Explainable local ML estimate |
| `POST` | `/api/ai/ask` | Grounded operations copilot |

Interactive OpenAPI docs are available at `/docs` after deployment.

## Production hardening roadmap

This starter includes role checks, RLS, validation, security headers, and audit records. Before production use, also add:

1. Supabase Storage bucket policies and malware scanning for document uploads.
2. Email/SMS notification workflows with human ownership and escalation SLAs.
3. Immutable audit-log export to a SIEM or WORM storage, plus retention policy.
4. Database backups / point-in-time recovery, monitoring, and incident runbooks.
5. Rate limits, WAF/CDN, CSP, CSRF strategy if cookies are introduced, and independent security review.
6. Formal authorization matrix, employee offboarding, and periodic access review.
7. Data migration, ML validation, model monitoring, and human approval workflows.

## Push this repo to GitHub

The repository is initialized locally. Create an empty GitHub repository, then:

```bash
git add .
git commit -m "Build ConstructrAI Supabase and Render portal"
git remote add origin https://github.com/YOUR-USERNAME/constructrai.git
git push -u origin main
```

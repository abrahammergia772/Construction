-- ConstructrAI production schema for Supabase Postgres.
-- Apply this file in Supabase Dashboard > SQL Editor, or with: supabase db push
-- The FastAPI service uses a service-role key; the browser never receives it.

create extension if not exists pgcrypto;

do $$ begin
  create type public.app_role as enum ('admin', 'manager', 'employee', 'customer');
exception when duplicate_object then null;
end $$;

do $$ begin
  create type public.priority_level as enum ('Low', 'Medium', 'High', 'Critical');
exception when duplicate_object then null;
end $$;

create table if not exists public.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(name) between 2 and 120),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.departments (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  name text not null check (char_length(name) between 2 and 100),
  code text not null check (code ~ '^[A-Za-z0-9_-]+$'),
  description text check (char_length(description) <= 500),
  color text not null default '#1c6955' check (color ~ '^#[0-9A-Fa-f]{6}$'),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, name),
  unique (organization_id, code)
);

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  organization_id uuid not null references public.organizations(id) on delete cascade,
  email text not null,
  full_name text not null check (char_length(full_name) between 2 and 120),
  role public.app_role not null default 'employee',
  department_id uuid references public.departments(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, email)
);

create table if not exists public.employees (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  profile_id uuid unique references public.profiles(id) on delete set null,
  department_id uuid references public.departments(id) on delete set null,
  full_name text not null check (char_length(full_name) between 2 and 120),
  email text not null,
  job_title text not null check (char_length(job_title) between 2 and 100),
  portal_role public.app_role not null default 'employee' check (portal_role in ('employee', 'manager')),
  phone text check (char_length(phone) <= 40),
  status text not null default 'Invite pending' check (status in ('Active', 'Invite pending', 'Inactive')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, email)
);

create table if not exists public.customers (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  profile_id uuid unique references public.profiles(id) on delete set null,
  company_name text not null check (char_length(company_name) between 2 and 160),
  contact_name text not null check (char_length(contact_name) between 2 and 120),
  email text not null,
  phone text check (char_length(phone) <= 40),
  status text not null default 'Prospect' check (status in ('Active', 'Prospect', 'Inactive')),
  notes text check (char_length(notes) <= 1000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, email)
);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  customer_id uuid references public.customers(id) on delete set null,
  department_id uuid references public.departments(id) on delete set null,
  manager_profile_id uuid references public.profiles(id) on delete set null,
  created_by uuid references public.profiles(id) on delete set null,
  name text not null check (char_length(name) between 3 and 140),
  project_type text not null check (char_length(project_type) between 3 and 80),
  progress numeric(5,2) not null default 0 check (progress between 0 and 100),
  days_remaining integer not null default 90 check (days_remaining >= 0),
  planned_duration integer not null default 180 check (planned_duration > 0),
  team_size integer not null default 1 check (team_size > 0),
  delay_days integer not null default 0 check (delay_days >= 0),
  budget numeric(14,2) not null default 0 check (budget >= 0),
  status text not null default 'Planning' check (status in ('Planning', 'On track', 'Watch', 'At risk', 'Completed', 'Archived')),
  start_date date,
  end_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (organization_id, name)
);

create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid references public.projects(id) on delete cascade,
  department_id uuid references public.departments(id) on delete set null,
  assignee_profile_id uuid references public.profiles(id) on delete set null,
  created_by uuid references public.profiles(id) on delete set null,
  title text not null check (char_length(title) between 3 and 180),
  description text check (char_length(description) <= 2000),
  priority public.priority_level not null default 'Medium',
  status text not null default 'To do' check (status in ('To do', 'In progress', 'Blocked', 'Done')),
  due_date date,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.complaints (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid references public.projects(id) on delete set null,
  customer_id uuid references public.customers(id) on delete set null,
  reported_by uuid references public.profiles(id) on delete set null,
  category text not null check (category in ('Quality', 'Safety', 'Payment', 'Schedule', 'Communication', 'Other')),
  priority public.priority_level not null,
  description text not null check (char_length(description) between 8 and 1500),
  status text not null default 'Open' check (status in ('Open', 'Investigating', 'Resolved')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid references public.projects(id) on delete set null,
  uploaded_by uuid references public.profiles(id) on delete set null,
  name text not null check (char_length(name) between 2 and 180),
  document_type text not null check (document_type in ('Blueprint', 'Contract', 'Safety report', 'Budget report', 'Progress report', 'Other')),
  url text not null check (url ~ '^https?://'),
  notes text check (char_length(notes) <= 1000),
  created_at timestamptz not null default now()
);

create table if not exists public.risk_predictions (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  project_id uuid references public.projects(id) on delete set null,
  created_by uuid references public.profiles(id) on delete set null,
  input_snapshot jsonb not null,
  risk_score integer not null check (risk_score between 0 and 100),
  risk_level text not null check (risk_level in ('Low', 'Moderate', 'High', 'Critical')),
  drivers jsonb not null default '[]'::jsonb,
  recommendations jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.ai_messages (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  profile_id uuid not null references public.profiles(id) on delete cascade,
  question text not null check (char_length(question) between 2 and 2000),
  answer text not null,
  source text not null check (source in ('local operations copilot', 'hosted AI')),
  created_at timestamptz not null default now()
);

create table if not exists public.audit_events (
  id uuid primary key default gen_random_uuid(),
  organization_id uuid not null references public.organizations(id) on delete cascade,
  actor_profile_id uuid references public.profiles(id) on delete set null,
  actor_name text not null,
  action text not null,
  entity_type text not null,
  entity_name text not null,
  severity public.priority_level not null default 'Low',
  created_at timestamptz not null default now()
);

create index if not exists idx_projects_org_status on public.projects (organization_id, status);
create index if not exists idx_tasks_org_due on public.tasks (organization_id, due_date);
create index if not exists idx_complaints_org_status on public.complaints (organization_id, status, priority);
create index if not exists idx_audit_org_created on public.audit_events (organization_id, created_at desc);

create or replace function public.set_updated_at()
returns trigger language plpgsql set search_path = public as $$
begin new.updated_at = now(); return new; end; $$;

do $$ declare table_name text;
begin
  foreach table_name in array array['organizations','departments','profiles','employees','customers','projects','tasks','complaints']
  loop
    execute format('drop trigger if exists set_%I_updated_at on public.%I', table_name, table_name);
    execute format('create trigger set_%I_updated_at before update on public.%I for each row execute function public.set_updated_at()', table_name, table_name);
  end loop;
end $$;

-- Security helpers are SECURITY DEFINER so policy checks do not recursively trigger profiles RLS.
create or replace function public.current_organization_id()
returns uuid language sql stable security definer set search_path = public as $$
  select organization_id from public.profiles where id = auth.uid()
$$;

create or replace function public.current_app_role()
returns public.app_role language sql stable security definer set search_path = public as $$
  select role from public.profiles where id = auth.uid()
$$;

create or replace function public.current_customer_id()
returns uuid language sql stable security definer set search_path = public as $$
  select id from public.customers where profile_id = auth.uid()
$$;

create or replace function public.is_org_manager()
returns boolean language sql stable security definer set search_path = public as $$
  select coalesce(public.current_app_role() in ('admin', 'manager'), false)
$$;

grant execute on function public.current_organization_id() to authenticated;
grant execute on function public.current_app_role() to authenticated;
grant execute on function public.current_customer_id() to authenticated;
grant execute on function public.is_org_manager() to authenticated;

alter table public.organizations enable row level security;
alter table public.departments enable row level security;
alter table public.profiles enable row level security;
alter table public.employees enable row level security;
alter table public.customers enable row level security;
alter table public.projects enable row level security;
alter table public.tasks enable row level security;
alter table public.complaints enable row level security;
alter table public.documents enable row level security;
alter table public.risk_predictions enable row level security;
alter table public.ai_messages enable row level security;
alter table public.audit_events enable row level security;

-- Read access is organization-scoped; customers are additionally limited to their own client records.
create policy "organization visible to members" on public.organizations for select to authenticated using (id = public.current_organization_id());
create policy "departments visible to members" on public.departments for select to authenticated using (organization_id = public.current_organization_id());
create policy "profiles own or manager" on public.profiles for select to authenticated using (id = auth.uid() or (organization_id = public.current_organization_id() and public.is_org_manager()));
create policy "employees staff only" on public.employees for select to authenticated using (organization_id = public.current_organization_id() and public.current_app_role() <> 'customer');
create policy "customers scoped" on public.customers for select to authenticated using (organization_id = public.current_organization_id() and (public.current_app_role() <> 'customer' or profile_id = auth.uid()));
create policy "projects scoped" on public.projects for select to authenticated using (organization_id = public.current_organization_id() and (public.current_app_role() <> 'customer' or customer_id = public.current_customer_id()));
create policy "tasks scoped" on public.tasks for select to authenticated using (organization_id = public.current_organization_id() and (public.current_app_role() <> 'customer' or project_id in (select id from public.projects where customer_id = public.current_customer_id())));
create policy "complaints scoped" on public.complaints for select to authenticated using (organization_id = public.current_organization_id() and (public.current_app_role() <> 'customer' or customer_id = public.current_customer_id()));
create policy "documents scoped" on public.documents for select to authenticated using (organization_id = public.current_organization_id() and (public.current_app_role() <> 'customer' or project_id in (select id from public.projects where customer_id = public.current_customer_id())));
create policy "predictions staff only" on public.risk_predictions for select to authenticated using (organization_id = public.current_organization_id() and public.current_app_role() <> 'customer');
create policy "ai messages own or manager" on public.ai_messages for select to authenticated using (profile_id = auth.uid() or (organization_id = public.current_organization_id() and public.is_org_manager()));
create policy "audit manager only" on public.audit_events for select to authenticated using (organization_id = public.current_organization_id() and public.is_org_manager());

-- Direct browser writes are deliberately narrow. The FastAPI server uses service role for approved workflows.
create policy "manager administers departments" on public.departments for all to authenticated using (organization_id = public.current_organization_id() and public.is_org_manager()) with check (organization_id = public.current_organization_id() and public.is_org_manager());
create policy "manager administers employees" on public.employees for all to authenticated using (organization_id = public.current_organization_id() and public.is_org_manager()) with check (organization_id = public.current_organization_id() and public.is_org_manager());
create policy "manager administers customers" on public.customers for all to authenticated using (organization_id = public.current_organization_id() and public.is_org_manager()) with check (organization_id = public.current_organization_id() and public.is_org_manager());
create policy "manager administers projects" on public.projects for all to authenticated using (organization_id = public.current_organization_id() and public.is_org_manager()) with check (organization_id = public.current_organization_id() and public.is_org_manager());
create policy "staff creates tasks" on public.tasks for insert to authenticated with check (organization_id = public.current_organization_id() and public.current_app_role() <> 'customer');
create policy "task assignee updates task" on public.tasks for update to authenticated using (organization_id = public.current_organization_id() and (public.is_org_manager() or assignee_profile_id = auth.uid())) with check (organization_id = public.current_organization_id());
create policy "authorized complaint insert" on public.complaints for insert to authenticated with check (organization_id = public.current_organization_id() and (public.current_app_role() <> 'customer' or customer_id = public.current_customer_id()));

-- No INSERT/UPDATE policy is granted for audit events, predictions, AI messages, or profiles to browser users.
-- The FastAPI service role creates those immutable operational records.

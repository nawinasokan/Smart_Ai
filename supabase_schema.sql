-- Run this once in the Supabase SQL editor for this project.
-- It adds the "history" table used by the History view and by
-- /api/history, /api/history/<id> in app.py.
--
-- The "users" table (email, name, generation_count) is assumed to
-- already exist, matching the columns read/written in app.py.

create table if not exists history (
  id uuid primary key default gen_random_uuid(),
  email text not null,
  mode text not null,
  prompt text not null,
  response text not null,
  created_at timestamptz not null default now()
);

create index if not exists history_email_created_idx
  on history (email, created_at desc);

-- If Row Level Security is enabled on this project, the backend talks to
-- Supabase using the service-role key (see SUPABASE_KEY in your .env),
-- which bypasses RLS. No policies are required for app.py to function.
-- Only add policies below if you also want end users to query this table
-- directly from the client with the anon/public key.

-- ---------------------------------------------------------------------
-- Keep-alive table: written by .github/workflows/supabase-keepalive.yml
-- every 6 days so the free-tier project is never paused for inactivity.
-- ---------------------------------------------------------------------
create table if not exists keepalive (
  id int primary key,
  last_ping timestamptz not null default now(),
  ping_count bigint not null default 0
);

alter table keepalive enable row level security;
-- No policies on purpose: only the service-role key (used by the workflow) can access it.

insert into keepalive (id) values (1) on conflict (id) do nothing;

-- Designs table — persistent design storage (Phase 3).
-- Run this in Supabase SQL Editor after 001_tracking_tables.sql.

create table if not exists designs (
  run_id        text primary key,
  room_type     text not null,
  target_budget numeric(10,2) not null,
  total_spent   numeric(10,2) not null default 0,
  is_feasible   boolean not null default true,
  style         jsonb not null default '{}',
  slots         jsonb not null default '[]',
  finalized_at  text,
  user_id       uuid,
  created_at    timestamptz not null default now()
);

-- RLS: default-deny.  Phase 6 adds user-scoped SELECT policy.
alter table designs enable row level security;

-- Service-role needs access for backend writes.
grant all on designs to service_role;

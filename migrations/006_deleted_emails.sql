-- Deletion cooldown: block free-tier re-registration for 30 days after account deletion.
-- The designs endpoint checks this table before granting a free room.
-- NOTE: Railway uses SUPABASE_SCHEMA=staging — table must exist in staging schema.

CREATE TABLE IF NOT EXISTS staging.deleted_emails (
    email       TEXT PRIMARY KEY,
    deleted_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    cooldown_until TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '30 days')
);

-- RLS: only the service role can read/write this table.
ALTER TABLE staging.deleted_emails ENABLE ROW LEVEL SECURITY;
-- No user-facing policies — service role bypasses RLS.

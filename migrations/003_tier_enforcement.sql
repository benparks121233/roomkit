-- Tier enforcement (Phase 6E).
-- Run in Supabase SQL Editor after 002_designs_table.sql.

-- 1. Add is_paid flag to designs (free-room count filter needs this).
ALTER TABLE designs ADD COLUMN IF NOT EXISTS is_paid boolean NOT NULL DEFAULT false;

-- 2. Pack ledger — one row per user, decremented on paid design creation.
CREATE TABLE IF NOT EXISTS user_packs (
  user_id         uuid PRIMARY KEY,
  rooms_remaining int NOT NULL DEFAULT 0,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE user_packs ENABLE ROW LEVEL SECURITY;
GRANT ALL ON user_packs TO service_role;

-- 3. RPC: atomic free-design claim (TOCTOU fix).
--    Advisory lock serializes per-user. Counts only free designs (is_paid=false).
--    Returns true if claimed, false if at limit.
CREATE OR REPLACE FUNCTION claim_and_save_free_design(
  p_run_id        text,
  p_user_id       uuid,
  p_room_type     text,
  p_target_budget numeric,
  p_total_spent   numeric,
  p_is_feasible   boolean,
  p_style         jsonb,
  p_slots         jsonb,
  p_finalized_at  text DEFAULT NULL,
  p_free_limit    int  DEFAULT 1
) RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  PERFORM pg_advisory_xact_lock(hashtext(p_user_id::text));

  IF (SELECT count(*) FROM designs WHERE user_id = p_user_id AND is_paid = false) >= p_free_limit THEN
    RETURN false;
  END IF;

  INSERT INTO designs (run_id, room_type, target_budget, total_spent, is_feasible, style, slots, finalized_at, user_id, is_paid)
  VALUES (p_run_id, p_room_type, p_target_budget, p_total_spent, p_is_feasible, p_style, p_slots, p_finalized_at, p_user_id, false)
  ON CONFLICT (run_id) DO NOTHING;

  RETURN true;
END;
$$;

-- 4. RPC: atomic pack decrement.
--    Single-statement UPDATE with row-lock serialization.
--    Returns remaining count, or no rows (null via .execute()) if pack empty/missing.
CREATE OR REPLACE FUNCTION decrement_pack(p_user_id uuid)
RETURNS int
LANGUAGE sql
SECURITY DEFINER
AS $$
  UPDATE user_packs
  SET rooms_remaining = rooms_remaining - 1, updated_at = now()
  WHERE user_id = p_user_id AND rooms_remaining >= 1
  RETURNING rooms_remaining;
$$;

-- 5. RPC: re-credit pack on clean pipeline failure.
CREATE OR REPLACE FUNCTION re_credit_pack(p_user_id uuid)
RETURNS void
LANGUAGE sql
SECURITY DEFINER
AS $$
  UPDATE user_packs
  SET rooms_remaining = rooms_remaining + 1, updated_at = now()
  WHERE user_id = p_user_id;
$$;

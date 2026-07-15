-- RLS policies — SELECT-only policies for user-facing tables.
-- Run in Supabase SQL Editor after 004_stripe_payments.sql.
-- Safe to re-run: drops existing policies first.
--
-- HISTORY: First run (2026-07-14) included permissive INSERT/UPDATE policies
-- (WITH CHECK (true)) on designs, selections, events — these were wrong
-- because all writes use the service key (bypasses RLS). The INSERT policies
-- opened an unnecessary write surface via the anon key. Second run same day
-- dropped those policies. This file reflects the corrected final state.
-- Future changes: write 006, don't edit this file.
--
-- All WRITES go through the service key (bypasses RLS) or SECURITY DEFINER
-- RPCs. No INSERT/UPDATE policies needed — their absence means the anon key
-- cannot write to these tables, which is correct.

-- =========================================================================
-- DESIGNS: users can only read their own designs
-- =========================================================================
DROP POLICY IF EXISTS designs_select_own ON designs;
DROP POLICY IF EXISTS designs_insert_service ON designs;
DROP POLICY IF EXISTS designs_update_service ON designs;
CREATE POLICY designs_select_own ON designs
  FOR SELECT
  USING (auth.uid() = user_id);

-- =========================================================================
-- USER_PACKS: users can only read their own pack balance
-- =========================================================================
DROP POLICY IF EXISTS user_packs_select_own ON user_packs;
CREATE POLICY user_packs_select_own ON user_packs
  FOR SELECT
  USING (auth.uid() = user_id);

-- =========================================================================
-- SELECTIONS: enable RLS, users can read their own run's selections
-- =========================================================================
ALTER TABLE selections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS selections_select_own ON selections;
DROP POLICY IF EXISTS selections_insert_service ON selections;
CREATE POLICY selections_select_own ON selections
  FOR SELECT
  USING (
    run_id IN (SELECT run_id FROM designs WHERE user_id = auth.uid())
  );

-- =========================================================================
-- EVENTS: enable RLS, users can read their own run's events
-- =========================================================================
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS events_select_own ON events;
DROP POLICY IF EXISTS events_insert_service ON events;
CREATE POLICY events_select_own ON events
  FOR SELECT
  USING (
    run_id IN (SELECT run_id FROM designs WHERE user_id = auth.uid())
  );

-- RLS policies — explicit SELECT policies for user-facing tables.
-- Run in Supabase SQL Editor after 004_stripe_payments.sql.
-- These policies enforce data isolation at the database level.

-- =========================================================================
-- DESIGNS: users can only read their own designs
-- =========================================================================
CREATE POLICY designs_select_own ON designs
  FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY designs_insert_service ON designs
  FOR INSERT
  WITH CHECK (true);

CREATE POLICY designs_update_service ON designs
  FOR UPDATE
  USING (true);

-- =========================================================================
-- USER_PACKS: users can only read their own pack balance
-- =========================================================================
CREATE POLICY user_packs_select_own ON user_packs
  FOR SELECT
  USING (auth.uid() = user_id);

-- =========================================================================
-- SELECTIONS: enable RLS, users can read their own run's selections
-- =========================================================================
ALTER TABLE selections ENABLE ROW LEVEL SECURITY;

CREATE POLICY selections_select_own ON selections
  FOR SELECT
  USING (
    run_id IN (SELECT run_id FROM designs WHERE user_id = auth.uid())
  );

CREATE POLICY selections_insert_service ON selections
  FOR INSERT
  WITH CHECK (true);

-- =========================================================================
-- EVENTS: enable RLS, users can read their own run's events
-- =========================================================================
ALTER TABLE events ENABLE ROW LEVEL SECURITY;

CREATE POLICY events_select_own ON events
  FOR SELECT
  USING (
    run_id IN (SELECT run_id FROM designs WHERE user_id = auth.uid())
  );

CREATE POLICY events_insert_service ON events
  FOR INSERT
  WITH CHECK (true);

-- =========================================================================
-- GRANTS — service_role bypasses RLS but needs table-level access
-- =========================================================================
GRANT ALL ON selections TO service_role;
GRANT ALL ON events TO service_role;

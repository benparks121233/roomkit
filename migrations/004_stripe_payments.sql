-- Stripe payment dedup ledger + atomic credit RPC (Phase 7A).
-- Run in Supabase SQL Editor after 003_tier_enforcement.sql.

-- 1. Payment record table — one row per completed checkout session.
--    PK on checkout_session_id is the dedup key.
CREATE TABLE IF NOT EXISTS stripe_payments (
  checkout_session_id text PRIMARY KEY,
  user_id             uuid NOT NULL,
  pack_size           int NOT NULL,
  amount_cents        int NOT NULL,
  currency            text NOT NULL DEFAULT 'usd',
  created_at          timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE stripe_payments ENABLE ROW LEVEL SECURITY;
GRANT ALL ON stripe_payments TO service_role;

-- 2. Atomic dedup + pack credit in one transaction.
--    Returns rooms_remaining on first call, NULL on duplicate (already processed).
--    No EXCEPTION block — any failure rolls back the entire transaction,
--    including the stripe_payments INSERT, so Stripe retries re-process cleanly.
CREATE OR REPLACE FUNCTION process_stripe_payment(
  p_session_id text,
  p_user_id    uuid,
  p_pack_size  int,
  p_amount     int,
  p_currency   text DEFAULT 'usd'
)
RETURNS int
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  _remaining int;
BEGIN
  INSERT INTO stripe_payments (checkout_session_id, user_id, pack_size, amount_cents, currency)
  VALUES (p_session_id, p_user_id, p_pack_size, p_amount, p_currency)
  ON CONFLICT (checkout_session_id) DO NOTHING;

  IF NOT FOUND THEN
    RETURN NULL;
  END IF;

  INSERT INTO user_packs (user_id, rooms_remaining)
  VALUES (p_user_id, p_pack_size)
  ON CONFLICT (user_id)
  DO UPDATE SET rooms_remaining = user_packs.rooms_remaining + EXCLUDED.rooms_remaining,
                updated_at = now()
  RETURNING rooms_remaining INTO _remaining;

  RETURN _remaining;
END;
$$;

-- Don't forget: NOTIFY pgrst, 'reload schema';

-- Add is_featured flag for public example rooms.
-- Only designs explicitly marked TRUE are accessible without auth.
ALTER TABLE staging.designs ADD COLUMN IF NOT EXISTS is_featured BOOLEAN NOT NULL DEFAULT FALSE;

-- Allow events.run_id to be NULL for pre-design events (e.g. stash_failed).
-- Safe to re-run: DROP NOT NULL is idempotent on a nullable column.
ALTER TABLE events ALTER COLUMN run_id DROP NOT NULL;

-- 007_add_user_id_to_scraped_metadata.sql
-- Add user_id column for per-user data isolation.

ALTER TABLE scraped_metadata ADD COLUMN IF NOT EXISTS user_id TEXT NOT NULL DEFAULT '';

-- Drop the old unique constraint on url alone
ALTER TABLE scraped_metadata DROP CONSTRAINT IF EXISTS scraped_metadata_url_key;

-- Add composite unique constraint for per-user URL deduplication
ALTER TABLE scraped_metadata ADD CONSTRAINT scraped_metadata_url_user_key UNIQUE (url, user_id);

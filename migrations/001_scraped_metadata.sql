-- 001_scraped_metadata.sql
-- Initial schema for the scraped_metadata table.

CREATE TABLE IF NOT EXISTS scraped_metadata (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    url TEXT NOT NULL UNIQUE,
    metadata JSONB NOT NULL DEFAULT '{}',
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scraped_metadata_url ON scraped_metadata (url);
CREATE INDEX IF NOT EXISTS idx_scraped_metadata_scraped_at ON scraped_metadata (scraped_at);

# Database Migrations

SQL migrations are stored in `migrations/` at the project root.

## Convention

- Files are numbered sequentially: `001_name.sql`, `002_name.sql`, etc.
- Each file uses `IF NOT EXISTS` / `IF EXISTS` guards so migrations are idempotent.
- Migrations run against the `SUPABASE_DB_URL` connection string.

## Running Migrations

```bash
just migrate
```

This executes all migration files via `psql`. Ensure `SUPABASE_DB_URL` is set in your `.env` or environment.

## Adding a New Migration

1. Create `migrations/<next_number>_<description>.sql`.
2. Write idempotent SQL (use `CREATE TABLE IF NOT EXISTS`, etc.).
3. Add the file to the `just migrate` recipe if running files individually, or use a glob pattern.
4. Test locally: `just migrate`.
5. Run against production: `fly ssh console -a quipu-hands -C "psql $SUPABASE_DB_URL -f migrations/<file>.sql"` or set the prod URL locally.

## Current Migrations

| File | Description |
|---|---|
| `001_scraped_metadata.sql` | Creates `scraped_metadata` table with URL, JSONB metadata, and timestamp |

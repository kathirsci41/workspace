-- Sprint 1 Task 1.6: marker migration for last_error VARCHAR(2000).
-- SQLite ignores VARCHAR length so no DDL needed here.
-- PostgreSQL ALTER COLUMN is handled by Alembic revision aafc87ae6bac.
SELECT 1;

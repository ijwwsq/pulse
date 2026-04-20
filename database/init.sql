-- Auto-bootstrap script for Pulse database
CREATE EXTENSION IF NOT EXISTS pgcrypto;

\i /docker-entrypoint-initdb.d/schema.sql
\i /docker-entrypoint-initdb.d/views_procs.sql
\i /docker-entrypoint-initdb.d/analytics_views.sql
\i /docker-entrypoint-initdb.d/Insert.sql
\i /docker-entrypoint-initdb.d/historical_seeds.sql

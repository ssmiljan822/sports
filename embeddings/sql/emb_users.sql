-- 1. Create the user
CREATE USER emb_writer WITH PASSWORD 'changeme';

-- 2. Grant USAGE on the schema
GRANT USAGE ON SCHEMA public TO emb_writer;

-- 3. Grant SELECT on all existing tables in the schema
GRANT SELECT ON ALL TABLES IN SCHEMA public TO emb_writer;

-- 4. Ensure future tables in the schema are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT ON TABLES TO emb_writer;
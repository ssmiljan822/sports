-- 1. Create the user
CREATE USER sports_reader WITH PASSWORD 'aaa';

-- 2. Grant USAGE on the schema
GRANT USAGE ON SCHEMA sfn TO sports_reader;

-- 3. Grant SELECT on all existing tables in the schema
GRANT SELECT ON ALL TABLES IN SCHEMA sfn TO sports_reader;

-- 4. Ensure future tables in the schema are also accessible
ALTER DEFAULT PRIVILEGES IN SCHEMA sfn
GRANT SELECT ON TABLES TO sports_reader;
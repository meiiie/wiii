-- Wiii - PostgreSQL Extensions Init
-- This script runs automatically on first container start
-- (mounted via docker-compose.yml → /docker-entrypoint-initdb.d/)

-- Enable pgvector for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable uuid generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

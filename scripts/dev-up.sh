#!/usr/bin/env bash
set -euo pipefail

echo "=== Starting AI Content Studio Local Services ==="

# 1. Start Redis
echo "Starting Redis..."
docker compose -f infra/docker-compose.yml up -d redis

# 2. Start Supabase
echo "Starting Supabase local stack..."
if command -v supabase &> /dev/null; then
  supabase start
else
  npx supabase start
fi

echo ""
echo "=== Local Services Started Successfully ==="
echo "Supabase API:     http://127.0.0.1:54321"
echo "Supabase Studio:  http://127.0.0.1:54323"
echo "Supabase DB:      postgresql://postgres:postgres@127.0.0.1:54322/postgres"
echo "Redis:            redis://127.0.0.1:6379"
echo "Inbucket (Email): http://127.0.0.1:54324"

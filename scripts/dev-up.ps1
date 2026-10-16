$ErrorActionPreference = "Stop"

Write-Host "=== Starting AI Content Studio Local Services ===" -ForegroundColor Cyan

# 1. Start Redis
Write-Host "Starting Redis..." -ForegroundColor Yellow
docker compose -f infra/docker-compose.yml up -d redis

# 2. Start Supabase
Write-Host "Starting Supabase local stack..." -ForegroundColor Yellow
if (Get-Command supabase -ErrorAction SilentlyContinue) {
    supabase start
} else {
    npx supabase start
}

Write-Host ""
Write-Host "=== Local Services Started Successfully ===" -ForegroundColor Green
Write-Host "Supabase API:     http://127.0.0.1:54321"
Write-Host "Supabase Studio:  http://127.0.0.1:54323"
Write-Host "Supabase DB:      postgresql://postgres:postgres@127.0.0.1:54322/postgres"
Write-Host "Redis:            redis://127.0.0.1:6379"
Write-Host "Inbucket (Email): http://127.0.0.1:54324"

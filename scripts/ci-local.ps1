#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Run the GitHub Actions CI checks locally before pushing or deploying.

.DESCRIPTION
    Mirrors .github/workflows/ci.yml so local runs match what CI will do.
    By default it auto-fixes Python lint/format issues (ruff check --fix and
    ruff format) before verifying, so a clean run means you are ready to push.

.PARAMETER Check
    Do not modify files. Runs ruff in check-only mode instead of auto-fixing.

.PARAMETER SkipPython
    Skip the Python lint, typecheck and test suite.

.PARAMETER SkipWeb
    Skip the TypeScript lint, build, typecheck and test suite.

.PARAMETER E2E
    Also run the Playwright browser E2E suite (slow: builds web + installs
    Chromium).

.PARAMETER Secrets
    Also run the gitleaks secrets scan if gitleaks is installed.

.EXAMPLE
    .\scripts\ci-local.ps1

.EXAMPLE
    .\scripts\ci-local.ps1 -SkipWeb -E2E

.EXAMPLE
    .\scripts\ci-local.ps1 -Check
#>
[CmdletBinding()]
param(
    [switch]$Check,
    [switch]$SkipPython,
    [switch]$SkipWeb,
    [switch]$E2E,
    [switch]$Secrets
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Failures = [System.Collections.Generic.List[string]]::new()
$Results = [System.Collections.Generic.List[object]]::new()

function Write-Section([string]$Title) {
    Write-Host ""
    Write-Host "=== $Title ===" -ForegroundColor Cyan
}

function Assert-Command([string]$Name, [string]$Hint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found. $Hint"
    }
}

function Invoke-Step {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$Command,
        [string[]]$Arguments = @()
    )

    $display = "$Command $($Arguments -join ' ')"
    Write-Host ""
    Write-Host ">>> $Name" -ForegroundColor Yellow
    Write-Host "    $display" -ForegroundColor DarkGray

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $exitCode = 0

    try {
        & $Command @Arguments
        $exitCode = $LASTEXITCODE
    }
    catch {
        Write-Host "    $($_.Exception.Message)" -ForegroundColor Red
        $exitCode = 1
    }
    finally {
        $stopwatch.Stop()
    }

    $status = if ($exitCode -eq 0) { "PASS" } else { "FAIL" }
    $color = if ($exitCode -eq 0) { "Green" } else { "Red" }
    $seconds = [math]::Round($stopwatch.Elapsed.TotalSeconds, 1)
    Write-Host "<<< $Name`: $status (${seconds}s)" -ForegroundColor $color

    $Results.Add([pscustomobject]@{
            Name     = $Name
            Status   = $status
            Duration = $seconds
        })

    if ($exitCode -ne 0) {
        $Failures.Add($Name)
    }
}

function Test-Secrets {
    if (-not (Get-Command "gitleaks" -ErrorAction SilentlyContinue)) {
        Write-Host "gitleaks is not installed; skipping the secrets scan." -ForegroundColor Yellow
        return
    }
    Invoke-Step "Secrets scan (gitleaks)" "gitleaks" @("detect", "--no-banner", "--redact")
}

$started = Get-Date

Write-Host "CI-local checks for $RepoRoot" -ForegroundColor Cyan
if ($Check) {
    Write-Host "Check mode: no files will be modified." -ForegroundColor DarkGray
}
else {
    Write-Host "Auto-fix mode: ruff will rewrite files (use -Check to disable)." -ForegroundColor DarkGray
}

# ── Python (: Python Lint, Typecheck & Tests) ────────────────────────────────
if (-not $SkipPython) {
    Write-Section "Python"

    Assert-Command "uv" "Install it from https://docs.astral.sh/uv/ and run 'uv sync --all-packages'."

    if ($Check) {
        Invoke-Step "Ruff lint (check)" "uv" @("run", "ruff", "check", ".")
        Invoke-Step "Ruff format (check)" "uv" @("run", "ruff", "format", "--check", ".")
    }
    else {
        Invoke-Step "Ruff lint (auto-fix)" "uv" @("run", "ruff", "check", ".", "--fix")
        Invoke-Step "Ruff format (write)" "uv" @("run", "ruff", "format", ".")
        # Verify the tree is now clean, matching the CI commands exactly.
        Invoke-Step "Ruff lint (verify)" "uv" @("run", "ruff", "check", ".")
        Invoke-Step "Ruff format (verify)" "uv" @("run", "ruff", "format", "--check", ".")
    }

    Invoke-Step "Mypy (source packages)" "uv" @(
        "run", "mypy",
        "-p", "api",
        "-p", "worker",
        "-p", "studio_core",
        "-p", "studio_providers",
        "-p", "studio_media"
    )

    Invoke-Step "Mypy (tests)" "uv" @(
        "run", "mypy",
        "apps/api/tests",
        "apps/worker/tests",
        "packages/studio_core/tests",
        "packages/studio_providers/tests",
        "packages/studio_media/tests",
        "tests/e2e_backend",
        "tests/infra"
    )

    Invoke-Step "Pytest" "uv" @("run", "pytest", "-q")
}

# ── Web (: Web & TypeScript Lint & Checks) ───────────────────────────────────
if (-not $SkipWeb) {
    Write-Section "Web & TypeScript"

    Assert-Command "pnpm" "Install it from https://pnpm.io/ and run 'pnpm install'."

    # Next.js telemetry can block on network access in sandboxed/offline
    # environments, which makes `next lint` appear to hang.
    if (-not $env:NEXT_TELEMETRY_DISABLED) { $env:NEXT_TELEMETRY_DISABLED = "1" }

    Invoke-Step "TypeScript lint" "pnpm" @("-r", "--if-present", "lint")
    Invoke-Step "Build packages" "pnpm" @("--filter", "./packages/**", "build")
    Invoke-Step "Typecheck" "pnpm" @("-r", "--if-present", "typecheck")
    Invoke-Step "TypeScript tests" "pnpm" @("-r", "--if-present", "test")
}

# ── E2E (: Browser E2E) ──────────────────────────────────────────────────────
if ($E2E) {
    Write-Section "Browser E2E"

    Assert-Command "pnpm" "Install it from https://pnpm.io/ and run 'pnpm install'."

    if (-not $env:NEXT_PUBLIC_API_URL) { $env:NEXT_PUBLIC_API_URL = "http://127.0.0.1:3101" }
    if (-not $env:NEXT_PUBLIC_SUPABASE_URL) { $env:NEXT_PUBLIC_SUPABASE_URL = "http://127.0.0.1:3101" }
    if (-not $env:NEXT_PUBLIC_SUPABASE_ANON_KEY) { $env:NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key" }
    if (-not $env:NEXT_TELEMETRY_DISABLED) { $env:NEXT_TELEMETRY_DISABLED = "1" }
    if (-not $env:E2E_USE_PROD) { $env:E2E_USE_PROD = "1" }

    Invoke-Step "Build API client" "pnpm" @("--filter", "@studio/api-client", "build")
    Invoke-Step "Build web for E2E" "pnpm" @("--filter", "@studio/web", "build")
    Invoke-Step "Install Playwright Chromium" "pnpm" @("--filter", "@studio/web", "exec", "playwright", "install", "chromium")
    Invoke-Step "Playwright suite" "pnpm" @("--filter", "@studio/web", "e2e")
}

# ── Secrets (: Secrets Scan) ─────────────────────────────────────────────────
if ($Secrets) {
    Write-Section "Secrets"
    Test-Secrets
}

# ── Summary ──────────────────────────────────────────────────────────────────
$total = ((Get-Date) - $started).TotalSeconds
Write-Section "Summary"

$Results | Format-Table -AutoSize | Out-String | Write-Host

if ($Failures.Count -gt 0) {
    Write-Host "CI checks FAILED in $([math]::Round($total, 1))s:" -ForegroundColor Red
    foreach ($failure in $Failures) {
        Write-Host "  - $failure" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Fix the failures above before pushing or deploying." -ForegroundColor Red
    exit 1
}

Write-Host "All CI checks passed in $([math]::Round($total, 1))s. Ready to push." -ForegroundColor Green
exit 0

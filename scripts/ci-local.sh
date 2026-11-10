#!/usr/bin/env bash
#
# Run the GitHub Actions CI checks locally before pushing or deploying.
#
# Mirrors .github/workflows/ci.yml. By default Python lint/format issues are
# auto-fixed (ruff check --fix and ruff format) before verification, so a
# clean run means the tree is ready to push.
#
# Usage:
#   ./scripts/ci-local.sh                 # auto-fix then run all checks
#   ./scripts/ci-local.sh --check         # do not modify files
#   ./scripts/ci-local.sh --skip-web      # Python only
#   ./scripts/ci-local.sh --e2e           # also run Playwright
#   ./scripts/ci-local.sh --secrets       # also run gitleaks
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

CHECK_ONLY=0
SKIP_PYTHON=0
SKIP_WEB=0
RUN_E2E=0
RUN_SECRETS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check) CHECK_ONLY=1 ;;
    --skip-python) SKIP_PYTHON=1 ;;
    --skip-web) SKIP_WEB=1 ;;
    --e2e) RUN_E2E=1 ;;
    --secrets) RUN_SECRETS=1 ;;
    -h|--help)
      sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [[ -t 1 ]]; then
  C_CYAN=$'\033[36m'
  C_YELLOW=$'\033[33m'
  C_GREEN=$'\033[32m'
  C_RED=$'\033[31m'
  C_GRAY=$'\033[90m'
  C_RESET=$'\033[0m'
else
  C_CYAN=""; C_YELLOW=""; C_GREEN=""; C_RED=""; C_GRAY=""; C_RESET=""
fi

FAILURES=()
RESULTS=()

section() {
  printf '\n%s=== %s ===%s\n' "$C_CYAN" "$1" "$C_RESET"
}

require_command() {
  local name="$1" hint="$2"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "${C_RED}Required command '$name' was not found. $hint${C_RESET}" >&2
    exit 1
  fi
}

run_step() {
  local name="$1"
  shift
  printf '\n%s>>> %s%s\n' "$C_YELLOW" "$name" "$C_RESET"
  printf '%s    %s%s\n' "$C_GRAY" "$*" "$C_RESET"

  local start status
  start=$SECONDS
  "$@"
  status=$?
  local duration=$((SECONDS - start))

  if [[ $status -eq 0 ]]; then
    printf '%s<<< %s: PASS (%ss)%s\n' "$C_GREEN" "$name" "$duration" "$C_RESET"
    RESULTS+=("PASS  ${name} (${duration}s)")
  else
    printf '%s<<< %s: FAIL (%ss)%s\n' "$C_RED" "$name" "$duration" "$C_RESET"
    RESULTS+=("FAIL  ${name} (${duration}s)")
    FAILURES+=("$name")
  fi
}

START=$SECONDS

printf '%sCI-local checks for %s%s\n' "$C_CYAN" "$REPO_ROOT" "$C_RESET"
if [[ $CHECK_ONLY -eq 1 ]]; then
  printf '%sCheck mode: no files will be modified.%s\n' "$C_GRAY" "$C_RESET"
else
  printf '%sAuto-fix mode: ruff will rewrite files (use --check to disable).%s\n' "$C_GRAY" "$C_RESET"
fi

# ── Python (: Python Lint, Typecheck & Tests) ────────────────────────────────
if [[ $SKIP_PYTHON -eq 0 ]]; then
  section "Python"
  require_command uv "Install it from https://docs.astral.sh/uv/ and run 'uv sync --all-packages'."

  if [[ $CHECK_ONLY -eq 1 ]]; then
    run_step "Ruff lint (check)" uv run ruff check .
    run_step "Ruff format (check)" uv run ruff format --check .
  else
    run_step "Ruff lint (auto-fix)" uv run ruff check . --fix
    run_step "Ruff format (write)" uv run ruff format .
    # Verify the tree is now clean, matching the CI commands exactly.
    run_step "Ruff lint (verify)" uv run ruff check .
    run_step "Ruff format (verify)" uv run ruff format --check .
  fi

  run_step "Mypy (source packages)" uv run mypy \
    -p api -p worker -p studio_core -p studio_providers -p studio_media

  run_step "Mypy (tests)" uv run mypy \
    apps/api/tests \
    apps/worker/tests \
    packages/studio_core/tests \
    packages/studio_providers/tests \
    packages/studio_media/tests \
    tests/e2e_backend \
    tests/infra

  run_step "Pytest" uv run pytest -q
fi

# ── Web (: Web & TypeScript Lint & Checks) ───────────────────────────────────
if [[ $SKIP_WEB -eq 0 ]]; then
  section "Web & TypeScript"
  require_command pnpm "Install it from https://pnpm.io/ and run 'pnpm install'."

  # Next.js telemetry can block on network access in sandboxed/offline
  # environments, which makes `next lint` appear to hang.
  export NEXT_TELEMETRY_DISABLED="${NEXT_TELEMETRY_DISABLED:-1}"

  run_step "TypeScript lint" pnpm -r --if-present lint
  run_step "Build packages" pnpm --filter "./packages/**" build
  run_step "Typecheck" pnpm -r --if-present typecheck
  run_step "TypeScript tests" pnpm -r --if-present test
fi

# ── E2E (: Browser E2E) ──────────────────────────────────────────────────────
if [[ $RUN_E2E -eq 1 ]]; then
  section "Browser E2E"
  require_command pnpm "Install it from https://pnpm.io/ and run 'pnpm install'."

  export NEXT_PUBLIC_API_URL="${NEXT_PUBLIC_API_URL:-http://127.0.0.1:3101}"
  export NEXT_PUBLIC_SUPABASE_URL="${NEXT_PUBLIC_SUPABASE_URL:-http://127.0.0.1:3101}"
  export NEXT_PUBLIC_SUPABASE_ANON_KEY="${NEXT_PUBLIC_SUPABASE_ANON_KEY:-test-anon-key}"
  export NEXT_TELEMETRY_DISABLED="${NEXT_TELEMETRY_DISABLED:-1}"
  export E2E_USE_PROD="${E2E_USE_PROD:-1}"

  run_step "Build API client" pnpm --filter @studio/api-client build
  run_step "Build web for E2E" pnpm --filter @studio/web build
  run_step "Install Playwright Chromium" pnpm --filter @studio/web exec playwright install chromium
  run_step "Playwright suite" pnpm --filter @studio/web e2e
fi

# ── Secrets (: Secrets Scan) ─────────────────────────────────────────────────
if [[ $RUN_SECRETS -eq 1 ]]; then
  section "Secrets"
  if command -v gitleaks >/dev/null 2>&1; then
    run_step "Secrets scan (gitleaks)" gitleaks detect --no-banner --redact
  else
    printf '%sgitleaks is not installed; skipping the secrets scan.%s\n' "$C_YELLOW" "$C_RESET"
  fi
fi

# ── Summary ──────────────────────────────────────────────────────────────────
TOTAL=$((SECONDS - START))
section "Summary"

for line in "${RESULTS[@]}"; do
  printf '  %s\n' "$line"
done

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  printf '\n%sCI checks FAILED in %ss:%s\n' "$C_RED" "$TOTAL" "$C_RESET"
  for failure in "${FAILURES[@]}"; do
    printf '  - %s\n' "$failure"
  done
  printf '\n%sFix the failures above before pushing or deploying.%s\n' "$C_RED" "$C_RESET"
  exit 1
fi

printf '\n%sAll CI checks passed in %ss. Ready to push.%s\n' "$C_GREEN" "$TOTAL" "$C_RESET"
exit 0

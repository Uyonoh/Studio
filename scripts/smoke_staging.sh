#!/usr/bin/env bash
# Smoke test for a deployed staging/production environment.
#
# Required:
#   API_BASE_URL   e.g. https://studio-api.onrender.com
#   WEB_BASE_URL   e.g. https://studio.vercel.app
#
# Optional (enables a real generation):
#   SMOKE_USER_TOKEN   Supabase access token for a workspace editor
#   SMOKE_PROJECT_ID   Project UUID in that workspace
#   SMOKE_MODEL        Model slug, e.g. img-fast-v1
#   SMOKE_TASK_TYPE    Defaults to text_to_image
#   SMOKE_PROMPT       Defaults to a short deterministic prompt
#   SMOKE_TIMEOUT      Seconds to wait for the job, default 180

set -euo pipefail

API_BASE_URL="${API_BASE_URL:?API_BASE_URL is required}"
WEB_BASE_URL="${WEB_BASE_URL:?WEB_BASE_URL is required}"
SMOKE_TASK_TYPE="${SMOKE_TASK_TYPE:-text_to_image}"
SMOKE_PROMPT="${SMOKE_PROMPT:-a red apple on a wooden table, studio lighting}"
SMOKE_TIMEOUT="${SMOKE_TIMEOUT:-180}"

pass() { printf 'PASS: %s\n' "$*"; }
fail() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }

request() {
  curl --silent --show-error --location --max-time 30 "$@"
}

# ── API liveness ──────────────────────────────────────────────────────────────
health="$(request "${API_BASE_URL%/}/healthz")" || fail "API /healthz is unreachable"
case "$health" in
  *'"status":"ok"'*) pass "API /healthz" ;;
  *) fail "API /healthz returned: $health" ;;
esac

# ── API readiness ─────────────────────────────────────────────────────────────
ready="$(request "${API_BASE_URL%/}/readyz")" || fail "API /readyz is unreachable"
case "$ready" in
  *'"db":"ok"'*) pass "API /readyz db" ;;
  *) fail "API /readyz db is not ok: $ready" ;;
esac
case "$ready" in
  *'"redis":"ok"'*) pass "API /readyz redis" ;;
  *) fail "API /readyz redis is not ok: $ready" ;;
esac

# ── Web reachability ──────────────────────────────────────────────────────────
web_status="$(curl --silent --output /dev/null --write-out '%{http_code}' --max-time 30 "${WEB_BASE_URL%/}/")"
case "$web_status" in
  2*|3*) pass "Web root (HTTP $web_status)" ;;
  *) fail "Web root returned HTTP $web_status" ;;
esac

# ── Optional real generation ──────────────────────────────────────────────────
if [[ -z "${SMOKE_USER_TOKEN:-}" || -z "${SMOKE_PROJECT_ID:-}" || -z "${SMOKE_MODEL:-}" ]]; then
  echo "SKIP: set SMOKE_USER_TOKEN, SMOKE_PROJECT_ID, and SMOKE_MODEL for a real generation"
  exit 0
fi

auth=(-H "Authorization: Bearer ${SMOKE_USER_TOKEN}" -H "Content-Type: application/json")
idempotency_key="smoke-$(date +%s)-$$"

submit_body="$(cat <<JSON
{"model":"${SMOKE_MODEL}","task_type":"${SMOKE_TASK_TYPE}","prompt":"${SMOKE_PROMPT}","inputs":[],"params":{}}
JSON
)"

submit_response="$(request -X POST \
  "${auth[@]}" \
  -H "Idempotency-Key: ${idempotency_key}" \
  --data "$submit_body" \
  "${API_BASE_URL%/}/v1/projects/${SMOKE_PROJECT_ID}/generations")" \
  || fail "Generation submit failed"

job_id="$(printf '%s' "$submit_response" | grep -o '"id":"[^"]*"' | head -n1 | cut -d'"' -f4)"
[[ -n "$job_id" ]] || fail "Could not parse job id from: $submit_response"
pass "Generation submitted (${job_id})"

deadline=$(( $(date +%s) + SMOKE_TIMEOUT ))
status="queued"
while :; do
  job_response="$(request -H "Authorization: Bearer ${SMOKE_USER_TOKEN}" \
    "${API_BASE_URL%/}/v1/generations/${job_id}")" || fail "Could not poll job ${job_id}"

  status="$(printf '%s' "$job_response" | grep -o '"status":"[^"]*"' | head -n1 | cut -d'"' -f4)"
  case "$status" in
    succeeded)
      pass "Generation succeeded"
      case "$job_response" in
        *'"outputs":[]'*) fail "Generation succeeded but returned no outputs" ;;
        *) pass "Generation returned at least one output" ;;
      esac
      exit 0
      ;;
    failed|canceled)
      fail "Generation ended as ${status}: ${job_response}"
      ;;
  esac

  if (( $(date +%s) >= deadline )); then
    fail "Generation ${job_id} did not finish within ${SMOKE_TIMEOUT}s (last status: ${status})"
  fi
  sleep 5
done

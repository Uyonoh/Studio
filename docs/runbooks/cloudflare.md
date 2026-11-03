# Cloudflare edge protection runbook

This runbook describes the Cloudflare configuration that sits in front of the
API (`api.<domain>`) and the web app (`app.<domain>`). It is defence in depth:
the application still enforces its own Redis token buckets (T7.1), prompt
length limits, moderation, and per-workspace concurrency caps. Cloudflare is
there to absorb volumetric floods and obvious abuse before requests reach the
origin.

## 1. Baseline settings

| Setting | API zone value | Notes |
| --- | --- | --- |
| SSL/TLS mode | Full (strict) | Origin certificate must be valid. |
| Always Use HTTPS | On | |
| Minimum TLS version | 1.2 | |
| Opportunistic Encryption / TLS 1.3 | On | |
| HTTP/2, HTTP/3 | On | |
| Bot Fight Mode | On (or Super Bot Fight Mode) | Keep verified bots allowed. |
| Browser Integrity Check | On | |
| Challenge Passage | 30 minutes | |
| Security Level | Medium (raise to High during an incident) | |

Do **not** enable "Under Attack Mode" as a permanent setting — it breaks API
clients and Playwright/health checks.

## 2. WAF custom rules

Create these rules under **Security → WAF → Custom rules**. Order matters:
allow-list first, then block/challenge rules, then rate limits.

| # | Name | Expression (example) | Action |
| --- | --- | --- | --- |
| 1 | Allow health checks | `http.request.uri.path in {"/healthz" "/readyz"}` | Skip (all remaining custom + managed rules) |
| 2 | Allow webhooks | `http.request.uri.path matches "^/v1/webhooks/"` and `ip.src in $provider_ips` | Skip rate limiting |
| 3 | Block non-API methods | `http.request.uri.path starts_with "/v1/" and not http.request.method in {"GET" "POST" "DELETE" "PATCH"}` | Block |
| 4 | Block oversized bodies | `http.request.uri.path starts_with "/v1/" and http.request.body.size gt 10485760` | Block |
| 5 | Challenge suspicious user agents | `http.request.uri.path starts_with "/v1/" and http.user_agent eq ""` | Managed Challenge |
| 6 | Protect auth endpoints | `http.request.uri.path starts_with "/auth/"` | Managed Challenge (rate limit below) |

Keep the origin's own 10 MB body guard as the authoritative check; the edge
rule is only a cheap early rejection.

## 3. Rate limiting rules

Cloudflare rate limiting is a fixed/sliding window, not a token bucket. Use it
as a coarse first line; the API's Redis buckets remain the precise per-user
and per-workspace limit.

Recommended rules (**Security → WAF → Rate limiting rules**):

| Rule | Path | Characteristic | Limit | Period | Action |
| --- | --- | --- | --- | --- | --- |
| API global | `/v1/*` | IP | 300 requests | 1 minute | Block 1 minute |
| Generation submit | `/v1/projects/*/generations` | IP | 30 requests | 1 minute | Managed Challenge |
| Upload URLs | `/v1/projects/*/assets/uploads` | IP | 60 requests | 1 minute | Managed Challenge |
| Auth | `/auth/*` | IP | 20 requests | 1 minute | Block 5 minutes |
| Webhook burst | `/v1/webhooks/*` | IP | 600 requests | 1 minute | Block 1 minute |

Notes:

- Prefer the `cf-connecting-ip` header at the origin; never trust a
  client-supplied `X-Forwarded-For`.
- Cloudflare's counters are per data centre. A distributed attack can still
  exceed the edge limit, which is why the Redis limiter exists.
- Do not apply the submit/upload rules to the worker or internal service
  tokens; add an allow-list rule for their source IPs.
- If the edge blocks a request, Cloudflare returns its own 429/403 page, not
  the API's problem+json body. Keep `Retry-After` on the origin response so
  clients that reach the API behave correctly.

## 4. Managed rules and exposed credentials

- Enable the Cloudflare Managed Ruleset and OWASP Core Ruleset in **paranoid**
  mode for the API zone; start in log-only for one week, then enforce.
- Enable **Security → Bots → Verified bots** allow-list so provider webhooks
  and uptime monitors are not challenged.
- Never place Supabase service-role keys, provider API keys, or webhook
  signing secrets in Cloudflare Workers, Transform Rules, or Page Rules.
- If a Worker is used for edge auth, it must only forward the user JWT; it
  must not mint tokens or hold the service-role key.

## 5. Health checks and failover

Cloudflare Health Checks (optional, paid plans) should probe:

- `GET https://api.<domain>/healthz` every 30 s, expect `200` and body
  `{"status":"ok"}`.
- `GET https://api.<domain>/readyz` every 60 s, expect `200`; this checks
  Postgres and Redis. A failing `readyz` should page on-call, not trigger
  automatic failover unless a secondary origin exists.

Do not cache `/healthz`, `/readyz`, or any `/v1/*` response at the edge.
Bypass cache for `Authorization`-bearing requests and all `POST` requests.

## 6. Application rate limits (source of truth)

| Control | Setting | Default |
| --- | --- | --- |
| Submit/retry, per user and per workspace | `RATE_LIMIT_SUBMIT_PER_MINUTE` | 20/min |
| Upload URL, per user and per workspace | `RATE_LIMIT_UPLOAD_PER_MINUTE` | 30/min |
| Prompt / negative prompt length | `MAX_PROMPT_CHARS` | 4000 chars |
| Concurrent active jobs per workspace | `MAX_ACTIVE_JOBS_PER_WORKSPACE` | 5 |
| Global kill switch | `RATE_LIMIT_ENABLED` | `true` |

The limiter fails **open** if Redis is unavailable, logs a warning, and lets
the request through. Cloudflare rules continue to protect the origin in that
case. When Redis recovers, buckets refill naturally; keys expire after one
full refill window plus 60 seconds.

`429` responses use the API's problem+json format and always include a
`Retry-After` header (whole seconds). Clients should honour it before retrying;
the web app surfaces the message and does not auto-retry generation submits.

## 7. Incident checklist

1. Confirm whether the traffic is volumetric (Cloudflare analytics) or
   application-level (per-user 429s in logs).
2. For volumetric floods: raise Security Level to High, enable a temporary
   IP/ASN block, and keep `/healthz` skipped.
3. For abusive authenticated users: lower `RATE_LIMIT_SUBMIT_PER_MINUTE` via
   environment and restart the API; the Redis buckets pick up the new capacity
   on the next request.
4. For a compromised key: rotate `SUPABASE_SERVICE_ROLE_KEY`,
   `WEBHOOK_SIGNING_SECRET`, and provider tokens; never rotate by editing
   Cloudflare rules.
5. After the incident: review 429/403 rates, tune the edge rules, and record
   any permanent limit changes in `docs/QUESTIONS.md` and `.env.example`.

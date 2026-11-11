# Authentication Setup (Email / Magic Link / Google)

The web app supports three sign-in methods. Email + password is the default on
the login page; magic link and Google OAuth remain available as secondary options.

| Method | Code path |
| --- | --- |
| Email + password (default) | `supabase.auth.signInWithPassword()` in `apps/web/src/app/login/page.tsx` |
| Email magic link | `supabase.auth.signInWithOtp()` → `/auth/callback` |
| Google OAuth | `supabase.auth.signInWithOAuth({ provider: "google" })` → `/auth/callback` |

All three land on `apps/web/src/app/auth/callback/route.ts`, which supports both
the PKCE `?code=` flow (default) and the `?token_hash=&type=` flow used by custom
email templates. The callback stores the session in cookies through
`@supabase/ssr`; `apps/web/src/lib/supabase/middleware.ts` refreshes it on every
request.

The code is wired up already. The steps below are the **manual provider
configuration** that cannot live in the repository.

---

## 1. Local Supabase stack

### 1.1 Google OAuth credentials

1. Open [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials).
2. Create (or reuse) an **OAuth 2.0 Client ID** of type *Web application*.
3. Add the authorized redirect URIs:
   - `http://127.0.0.1:54321/auth/v1/callback` (local Supabase)
   - `https://<project-ref>.supabase.co/auth/v1/callback` (hosted project, if used)
4. Copy the **Client ID** and **Client secret**.

Put them in the root `.env` (the one `supabase/config.toml` reads via `env()`):

```dotenv
SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID=...
SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET=...
```

Then restart the stack:

```powershell
npx supabase stop
npx supabase start
```

The provider is enabled in `supabase/config.toml` under `[auth.external.google]`
with `skip_nonce_check = true`, which the local stack requires for Google.

### 1.2 Redirect URLs

`supabase/config.toml` already allows both dev hostnames:

```toml
site_url = "http://127.0.0.1:3000"
additional_redirect_urls = [
  "http://localhost:3000",
  "http://localhost:3000/**",
  "http://127.0.0.1:3000",
  "http://127.0.0.1:3000/**",
  "https://127.0.0.1:3000",
]
```

If you serve the web app on another host/port, add it to
`additional_redirect_urls` **and** to the Google authorized redirect URIs.

### 1.3 Magic-link email

Local Supabase does not send real email. It captures messages in Inbucket:

- Open <http://127.0.0.1:54324>
- Request a magic link at <http://localhost:3000/login>
- Open the newest message and click the confirmation link

The local email rate limit is set to 30/hour in `supabase/config.toml` so repeated
testing is not blocked.

### 1.4 Web app environment

`apps/web/.env.local` must point at the same Supabase instance:

```dotenv
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321
NEXT_PUBLIC_SUPABASE_ANON_KEY=<local anon key>
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Copy from `apps/web/.env.example` if the file does not exist.

Retrieve the local anon key with:

```bash
npx supabase status -o env
```

Copy the printed `ANON_KEY` value into `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The same
command also prints `SERVICE_ROLE_KEY` for the root `.env` file.

---

## 2. Hosted Supabase project

These settings live in the Supabase dashboard and override `supabase/config.toml`
for the hosted project.

### 2.1 URL configuration

**Dashboard → Authentication → URL Configuration**

- **Site URL**: your production origin, e.g. `https://studio.example.com`
- **Redirect URLs** (add every environment):
  - `http://localhost:3000/**`
  - `http://127.0.0.1:3000/**`
  - `https://studio.example.com/**`
  - Preview URLs, e.g. `https://*-your-team.vercel.app/**`

Without the localhost entry, magic links and Google sign-in fall back to the Site
URL and the callback never runs, which looks like “only password login works”.

### 2.2 Google provider

**Dashboard → Authentication → Providers → Google**

1. Enable the provider.
2. Paste the Google **Client ID** and **Client secret**.
3. Confirm the Google Console authorized redirect URI is
   `https://<project-ref>.supabase.co/auth/v1/callback`.

The hosted project currently reports Google as disabled in
`GET /auth/v1/settings`; enabling it is the only way to make the Google button
work against that project.

### 2.3 Magic-link email delivery

**Dashboard → Authentication → Emails**

- The built-in SMTP service only sends to project team members and is heavily
  rate limited. For real users, configure **custom SMTP** (Resend, SendGrid,
  Postmark, SES, etc.) under *SMTP Settings*.
- Set the sender address/name and send a test email.
- Default rate limit is 2 emails/hour; raise **Authentication → Rate Limits →
  Email sent** for production traffic.

### 2.4 Email templates

The default magic-link template (`{{ .ConfirmationURL }}`) is supported as-is
(PKCE flow, lands on `/auth/callback?code=...`).

If you customize the template, either keep `{{ .ConfirmationURL }}` or link
directly to:

```html
<a href="{{ .SiteURL }}/auth/callback?token_hash={{ .TokenHash }}&type=magiclink">
  Sign in to Studio
</a>
```

The callback route handles both forms. Use `type=magiclink` for the *Magic Link*
template and `type=signup` for the *Confirm signup* template.

### 2.5 Web app environment

Point the web app at the hosted project (in `apps/web/.env.local` for local
development, or in the hosting provider's environment settings for deployments):

```dotenv
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<project publishable/anon key>
NEXT_PUBLIC_API_URL=https://<api-origin>
```

Restart `next dev` after changing these values.

---

## 3. Verification checklist

1. **Password**: sign in with the seeded `dev@example.com` / `DevPassword123!`.
2. **Magic link**: request a link, confirm the success banner, open the email,
   click the link, and verify you land on `/projects` (or the page you were
   redirected from).
3. **Google**: click *Continue with Google*, complete consent, and verify the
   callback lands on `/projects` and a workspace/profile was auto-created by the
   `on_auth_user_created` trigger.
4. **Session refresh**: reload `/projects`; the session cookie should refresh via
   middleware without bouncing to `/login`.
5. **Sign out**: `/auth/signout` clears the session and `/projects` redirects to
   `/login`.

---

## 4. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Google button returns “provider is not enabled” | Provider disabled in the Supabase project (dashboard for hosted, `[auth.external.google]` for local). |
| Magic link lands on the marketing site or `/` with `#access_token=` | `redirectTo` is not in the Supabase redirect allow list; add `.../auth/callback`. |
| “Email rate limit exceeded” | Default hosted SMTP limit (2/hour). Configure custom SMTP / raise the email rate limit. |
| Link opens but login fails with `auth_callback_failed` | Link expired/reused, `Site URL` mismatch, or the auth cookies were lost. Request a fresh link and confirm both dev hosts are allowlisted. |
| `redirectedFrom` / `next` ignored | Only internal paths are honored (open-redirect protection in `apps/web/src/lib/safe-redirect.ts`). |

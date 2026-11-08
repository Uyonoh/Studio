#!/usr/bin/env python3
"""
Seed dev user script.
Provisions dev@example.com via Supabase Auth Admin API and grants 1000 credits.
Supports modern SUPABASE_SECRET_KEY / SUPABASE_SERVICE_ROLE_KEY.
"""

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    return env


def main() -> None:
    env = load_env()
    supabase_url = os.getenv("SUPABASE_URL") or env.get("SUPABASE_URL", "http://127.0.0.1:54321")
    secret_key = (
        os.getenv("SUPABASE_SECRET_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or env.get("SUPABASE_SECRET_KEY")
        or env.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )

    if not secret_key:
        print(
            "ERROR: Neither SUPABASE_SECRET_KEY nor SUPABASE_SERVICE_ROLE_KEY is set.",
            file=sys.stderr,
        )
        sys.exit(1)

    headers = {
        "apikey": secret_key,
        "Authorization": f"Bearer {secret_key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }

    email = "dev@example.com"
    password = "DevPassword123!"
    display_name = "Dev User"

    print(f"Provisioning dev user {email} at {supabase_url}...")

    # 1. Create or fetch user via admin auth API
    user_id = None
    create_user_url = f"{supabase_url.rstrip('/')}/auth/v1/admin/users"
    payload = json.dumps(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "display_name": display_name,
                "full_name": display_name,
            },
        }
    ).encode("utf-8")

    req = urllib.request.Request(create_user_url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            user_id = data.get("id")
            print(f"Created dev user with ID: {user_id}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        if e.code == 422:
            print("User already exists, looking up user ID...")
            list_url = f"{supabase_url.rstrip('/')}/auth/v1/admin/users?per_page=50"
            list_req = urllib.request.Request(list_url, headers=headers, method="GET")
            with urllib.request.urlopen(list_req) as list_resp:
                users_data = json.loads(list_resp.read().decode())
                users = users_data.get("users", [])
                for u in users:
                    if u.get("email") == email:
                        user_id = u.get("id")
                        break
            if user_id:
                print(f"Found existing dev user with ID: {user_id}")
            else:
                print(
                    f"Failed to find existing user {email} in users list: {err_body}",
                    file=sys.stderr,
                )
                sys.exit(1)
        else:
            print(f"HTTPError {e.code} while creating user: {err_body}", file=sys.stderr)
            sys.exit(1)

    # 2. Get workspace for this user
    print("Finding workspace for dev user...")
    members_path = f"/rest/v1/workspace_members?user_id=eq.{user_id}&select=workspace_id,role"
    members_url = f"{supabase_url.rstrip('/')}{members_path}"
    req_members = urllib.request.Request(members_url, headers=headers, method="GET")
    workspace_id = None
    try:
        with urllib.request.urlopen(req_members) as resp:
            memberships = json.loads(resp.read().decode())
            if memberships:
                workspace_id = memberships[0].get("workspace_id")
                print(f"Found workspace ID: {workspace_id}")
            else:
                print("No workspace found automatically via trigger; creating one directly...")
                prof_url = f"{supabase_url.rstrip('/')}/rest/v1/profiles"
                prof_payload = json.dumps({"id": user_id, "display_name": display_name}).encode(
                    "utf-8"
                )
                prof_req = urllib.request.Request(
                    prof_url, data=prof_payload, headers=headers, method="POST"
                )
                urllib.request.urlopen(prof_req)

                ws_url = f"{supabase_url.rstrip('/')}/rest/v1/workspaces"
                ws_payload = json.dumps(
                    {
                        "name": f"{display_name}'s Workspace",
                        "owner_id": user_id,
                    }
                ).encode("utf-8")
                ws_req = urllib.request.Request(
                    ws_url, data=ws_payload, headers=headers, method="POST"
                )
                with urllib.request.urlopen(ws_req) as ws_resp:
                    ws_data = json.loads(ws_resp.read().decode())
                    workspace_id = ws_data[0]["id"]

                mem_url = f"{supabase_url.rstrip('/')}/rest/v1/workspace_members"
                mem_payload = json.dumps(
                    {
                        "workspace_id": workspace_id,
                        "user_id": user_id,
                        "role": "owner",
                    }
                ).encode("utf-8")
                mem_req = urllib.request.Request(
                    mem_url, data=mem_payload, headers=headers, method="POST"
                )
                urllib.request.urlopen(mem_req)
                print(f"Created fallback workspace ID: {workspace_id}")
    except Exception as e:
        print(f"Error checking workspace: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Grant 1000 credits via credit_ledger
    print("Checking credit balance...")
    ledger_path = f"/rest/v1/credit_ledger?workspace_id=eq.{workspace_id}&select=delta"
    ledger_url = f"{supabase_url.rstrip('/')}{ledger_path}"
    ledger_req = urllib.request.Request(ledger_url, headers=headers, method="GET")
    with urllib.request.urlopen(ledger_req) as resp:
        entries = json.loads(resp.read().decode())
        total_credits = sum(float(e.get("delta", 0)) for e in entries)
        print(f"Current total credits: {total_credits}")

    if total_credits < 1000:
        needed = 1000.00 - total_credits
        print(f"Granting {needed} credits to workspace {workspace_id}...")
        grant_url = f"{supabase_url.rstrip('/')}/rest/v1/credit_ledger"
        grant_payload = json.dumps(
            {
                "workspace_id": workspace_id,
                "delta": needed,
                "reason": "grant",
            }
        ).encode("utf-8")
        grant_req = urllib.request.Request(
            grant_url, data=grant_payload, headers=headers, method="POST"
        )
        with urllib.request.urlopen(grant_req) as resp:
            print("Successfully granted credits!")
    else:
        print("Dev user already has >= 1000 credits.")

    print("\nDev user seeding complete!")
    print(f"Email: {email}")
    print(f"Workspace ID: {workspace_id}")


if __name__ == "__main__":
    main()

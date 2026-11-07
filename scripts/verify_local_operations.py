import urllib.request, json, time
from studio_core.settings import get_settings

s = get_settings()
print("1. Logging into local Supabase...")
login_req = urllib.request.Request(
    f"{s.supabase_url}/auth/v1/token?grant_type=password",
    data=json.dumps({"email": "dev@example.com", "password": "DevPassword123!"}).encode("utf-8"),
    headers={"apikey": s.supabase_anon_key, "Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(login_req) as r:
    token = json.loads(r.read().decode())["access_token"]
print("   Logged in successfully.")

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# 2. Query workspaces
print("2. Fetching workspaces...")
ws_req = urllib.request.Request("http://127.0.0.1:8000/v1/workspaces", headers=headers)
with urllib.request.urlopen(ws_req) as r:
    workspaces = json.loads(r.read().decode())
    print("   Workspaces found:", workspaces)
    ws_id = workspaces[0]["id"]

# 3. Create project
print(f"3. Creating project in workspace {ws_id}...")
create_p_req = urllib.request.Request(
    f"http://127.0.0.1:8000/v1/workspaces/{ws_id}/projects",
    data=json.dumps({"name": "Cyberpunk Art Project", "description": "Local test project"}).encode("utf-8"),
    headers=headers,
    method="POST"
)
with urllib.request.urlopen(create_p_req) as cr:
    proj = json.loads(cr.read().decode())
    print("   Created project:", proj["id"], proj["name"])
    proj_id = proj["id"]

# 4. List projects
print("4. Listing projects for workspace...")
list_p_req = urllib.request.Request(f"http://127.0.0.1:8000/v1/workspaces/{ws_id}/projects", headers=headers)
with urllib.request.urlopen(list_p_req) as lr:
    p_list = json.loads(lr.read().decode())
    print("   Projects count:", len(p_list.get("items", [])))

# 5. Asset upload intent
print("5. Requesting asset upload intent...")
upload_payload = {
    "kind": "image",
    "mime_type": "image/png",
    "size_bytes": 2048,
    "filename": "concept.png"
}
upload_req = urllib.request.Request(
    f"http://127.0.0.1:8000/v1/projects/{proj_id}/assets/uploads",
    data=json.dumps(upload_payload).encode("utf-8"),
    headers=headers,
    method="POST"
)
with urllib.request.urlopen(upload_req) as ur:
    upload_res = json.loads(ur.read().decode())
    asset_id = upload_res["asset_id"]
    upload_url = upload_res["upload_url"]
    print("   Asset upload intent created! asset_id:", asset_id)
    print("   Upload URL:", upload_url)

# 6. Upload mock file to storage upload URL
print("6. Uploading 1x1 mock PNG to upload URL...")
png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\x9f\x01\r\x00\x03\x02\x01\x02P\xda\x18\xdd\x00\x00\x00\x00IEND\xaeB`\x82"
put_req = urllib.request.Request(
    upload_url,
    data=png_bytes,
    headers={"Content-Type": "image/png"},
    method="PUT"
)
try:
    with urllib.request.urlopen(put_req) as put_resp:
        print("   Upload to storage returned status:", put_resp.status)
except Exception as e:
    print("   Upload to storage error (may use direct complete):", e)

# 7. Complete asset upload
print("7. Completing asset upload...")
complete_req = urllib.request.Request(
    f"http://127.0.0.1:8000/v1/assets/{asset_id}/complete",
    data=json.dumps({}).encode("utf-8"),
    headers=headers,
    method="POST"
)
with urllib.request.urlopen(complete_req) as compl_r:
    asset_data = json.loads(compl_r.read().decode())
    print("   Asset completed successfully! Asset data:", asset_data.get("id"), asset_data.get("kind"), asset_data.get("storage_path"))

# 8. List project assets
print("8. Listing project assets...")
assets_req = urllib.request.Request(f"http://127.0.0.1:8000/v1/projects/{proj_id}/assets", headers=headers)
with urllib.request.urlopen(assets_req) as ar:
    assets_list = json.loads(ar.read().decode())
    print("   Assets count:", len(assets_list.get("items", [])))
    for a in assets_list.get("items", []):
        print("    - Asset:", a.get("id"), a.get("kind"), "Signed URL present:", bool(a.get("signed_url")))

# 9. Test Generation Job with FakeProvider
print("9. Submitting generation job with fake provider...")
gen_payload = {
    "model": "fake-image-fast",
    "task_type": "text_to_image",
    "prompt": "Cyberpunk robot in rain",
    "parameters": {
        "aspect_ratio": "1:1",
        "output_format": "png"
    }
}
gen_req = urllib.request.Request(
    f"http://127.0.0.1:8000/v1/projects/{proj_id}/generations",
    data=json.dumps(gen_payload).encode("utf-8"),
    headers={**headers, "Idempotency-Key": f"local-gen-{int(time.time())}"},
    method="POST"
)
with urllib.request.urlopen(gen_req) as gr:
    job = json.loads(gr.read().decode())
    print("   Job submitted! job_id:", job["id"], "status:", job["status"])

import urllib.request, json, time
from studio_core.settings import get_settings

s = get_settings()
login_req = urllib.request.Request(
    f"{s.supabase_url}/auth/v1/token?grant_type=password",
    data=json.dumps({"email": "dev@example.com", "password": "DevPassword123!"}).encode("utf-8"),
    headers={"apikey": s.supabase_anon_key, "Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(login_req) as r:
    token = json.loads(r.read().decode())["access_token"]

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
proj_id = "2fcb1367-36ae-4bdf-b036-c76a0acc0e2a"

idem_key = f"test-gen-{int(time.time())}"
gen_payload = {
    "model": "fake-image-fast",
    "task_type": "text_to_image",
    "prompt": "A futuristic cyberpunk city with neon lights",
    "parameters": {
        "aspect_ratio": "1:1",
        "output_format": "png"
    }
}
gen_req = urllib.request.Request(
    f"http://127.0.0.1:8000/v1/projects/{proj_id}/generations",
    data=json.dumps(gen_payload).encode("utf-8"),
    headers={**headers, "Idempotency-Key": idem_key},
    method="POST"
)

with urllib.request.urlopen(gen_req) as gr:
    job = json.loads(gr.read().decode())
    job_id = job["id"]
    print("Generation enqueued: job_id=" + job_id + ", status=" + str(job.get("status")))

for i in range(12):
    time.sleep(2)
    poll_req = urllib.request.Request(f"http://127.0.0.1:8000/v1/generations/{job_id}", headers=headers)
    with urllib.request.urlopen(poll_req) as pr:
        cur_job = json.loads(pr.read().decode())
        out_cnt = len(cur_job.get("outputs") or [])
        cur_status = cur_job.get("status")
        print(f"Poll {i+1}: status={cur_status}, outputs={out_cnt}")
        if cur_status in ("succeeded", "failed"):
            print("Job terminal state reached:")
            print(json.dumps(cur_job, indent=2))
            break

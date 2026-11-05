import http from "node:http";

// 1x1 transparent PNG. The mock uses it for every media response; browser
// elements only need a reachable URL for the E2E assertions.
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64"
);

const SEED_PROJECT_ID = "proj-e2e";

export function startMockBackend(port = 3101) {
  const makeSeedAsset = () => ({
    id: "asset-seed-1",
    workspace_id: "ws-e2e",
    project_id: SEED_PROJECT_ID,
    kind: "image",
    origin: "upload",
    mime_type: "image/png",
    size_bytes: 1024,
    width: 512,
    height: 512,
    duration_ms: null,
    fps: null,
    storage_path: `ws-e2e/${SEED_PROJECT_ID}/asset-seed-1/original.png`,
    thumbnail_path: null,
    thumbnail_url: null,
    signed_url: `http://127.0.0.1:${port}/media/ws-e2e/${SEED_PROJECT_ID}/asset-seed-1/original.png`,
    source_job_id: null,
    parent_asset_id: null,
    metadata: { filename: "seeded_photo.png", status: "ready" },
    created_at: new Date().toISOString(),
  });

  const makeSeedProject = () => ({
    id: SEED_PROJECT_ID,
    workspace_id: "ws-e2e",
    name: "Brand Launch",
    description: "E2E workspace test project",
    cover_asset_id: null,
    created_by: "usr-e2e-123",
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    archived_at: null,
  });

  let assets = [makeSeedAsset()];
  let projects = [makeSeedProject()];
  let jobs = [];
  let nextJobId = 1;
  let pendingUpload = null;

  function resetState() {
    assets = [makeSeedAsset()];
    projects = [makeSeedProject()];
    jobs = [];
    nextJobId = 1;
    pendingUpload = null;
  }

  const models = [
    {
      id: "model-e2e-1",
      slug: "fake-image-fast",
      display_name: "Fake Fast Image Generator",
      task_type: "text_to_image",
      provider_id: "fake",
      input_schema: {
        type: "object",
        properties: {
          aspect_ratio: {
            type: "string",
            enum: ["1:1", "16:9"],
            default: "1:1",
          },
        },
        additionalProperties: false,
      },
      default_params: { aspect_ratio: "1:1" },
      cost_credits: "1.00",
      required_input_roles: [],
    },
    {
      id: "model-e2e-2",
      slug: "fake-image-edit",
      display_name: "Fake Image Editor",
      task_type: "image_to_image",
      provider_id: "fake",
      input_schema: {
        type: "object",
        properties: {
          strength: {
            type: "number",
            minimum: 0,
            maximum: 1,
            default: 0.6,
          },
        },
        additionalProperties: false,
      },
      default_params: { strength: 0.6 },
      cost_credits: "1.00",
      required_input_roles: ["init_image"],
    },
    {
      id: "model-e2e-3",
      slug: "fake-video-fast",
      display_name: "Fake Fast Video Generator",
      task_type: "text_to_video",
      provider_id: "fake",
      input_schema: {
        type: "object",
        properties: {
          duration_seconds: {
            type: "integer",
            minimum: 1,
            maximum: 10,
            default: 3,
          },
        },
        additionalProperties: false,
      },
      default_params: { duration_seconds: 3 },
      cost_credits: "4.00",
      required_input_roles: [],
    },
    {
      id: "model-e2e-4",
      slug: "fake-video-i2v",
      display_name: "Fake Image-to-Video Generator",
      task_type: "image_to_video",
      provider_id: "fake",
      input_schema: {
        type: "object",
        properties: {
          duration_seconds: {
            type: "integer",
            minimum: 1,
            maximum: 10,
            default: 3,
          },
        },
        additionalProperties: false,
      },
      default_params: { duration_seconds: 3 },
      cost_credits: "4.00",
      required_input_roles: ["first_frame"],
    },
  ];

  const makeJob = (projectId, body, overrides = {}) => {
    const prompt = body?.prompt || null;
    const id = `job-e2e-${nextJobId}`;
    nextJobId += 1;
    return {
      id,
      project_id: projectId,
      workspace_id: "ws-e2e",
      status: "queued",
      task_type: body?.task_type || "text_to_image",
      prompt,
      params: body?.params || {},
      inputs: body?.inputs || [],
      error_code: null,
      error_message: null,
      queued_at: new Date().toISOString(),
      started_at: null,
      completed_at: null,
      outputs: [],
      links: { self: `/v1/generations/${id}` },
      // Internal flags; stripped before the job is sent to the browser.
      _shouldFail: /FAIL/i.test(prompt || ""),
      _slow: /SLOW|CANCEL/i.test(prompt || ""),
      ...overrides,
    };
  };

  const publicJob = (job) => {
    const { _shouldFail, _slow, ...rest } = job;
    return rest;
  };

  const makeOutput = (job) => {
    const isVideo = String(job.task_type).includes("video");
    const extension = isVideo ? "mp4" : "png";
    const assetId = `asset-generated-${job.id}`;
    const base = `http://127.0.0.1:${port}/media/ws-e2e/${job.project_id}/${assetId}`;
    return {
      asset_id: assetId,
      kind: isVideo ? "video" : "image",
      mime_type: isVideo ? "video/mp4" : "image/png",
      signed_url: `${base}/original.${extension}`,
      thumbnail_url: isVideo ? `${base}/thumb.png` : null,
    };
  };

  const progressJob = (job) => {
    if (job.status === "queued") {
      job.status = "running";
      job.started_at = new Date().toISOString();
      return;
    }

    if (job.status !== "running" || job._slow) return;

    if (job._shouldFail) {
      job.status = "failed";
      job.error_code = "PROVIDER_FAILED";
      job.error_message = "The provider rejected this prompt (simulated failure).";
      job.completed_at = new Date().toISOString();
      return;
    }

    job.status = "succeeded";
    job.completed_at = new Date().toISOString();
    job.outputs = [makeOutput(job)];
  };

  const server = http.createServer((req, res) => {
    const url = new URL(req.url, `http://127.0.0.1:${port}`);
    const method = req.method;

    // CORS
    res.setHeader("Access-Control-Allow-Origin", "*");
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,PATCH,OPTIONS");
    res.setHeader("Access-Control-Allow-Headers", "*");

    if (method === "OPTIONS") {
      res.statusCode = 204;
      return res.end();
    }

    // Read body helper
    const readJson = () =>
      new Promise((resolve, reject) => {
        let body = "";
        req.on("data", (chunk) => (body += chunk));
        req.on("end", () => {
          try {
            resolve(body ? JSON.parse(body) : {});
          } catch (e) {
            reject(e);
          }
        });
      });

    const sendJson = (data, code = 200) => {
      res.statusCode = code;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify(data));
    };

    const sendProblem = (status, errorCode, detail) => {
      res.statusCode = status;
      res.setHeader("Content-Type", "application/problem+json");
      res.end(
        JSON.stringify({
          type: `https://studio.example.com/errors/${errorCode.toLowerCase()}`,
          title: errorCode.replace(/_/g, " ").toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase()),
          status,
          detail,
          error_code: errorCode,
        })
      );
    };

    // Test-only state reset so each spec starts from the seeded fixture.
    if (url.pathname === "/__test__/reset" && method === "POST") {
      resetState();
      return sendJson({ ok: true });
    }

    // 1. Supabase auth endpoints (called by server/middleware and login page)
    if (url.pathname === "/auth/v1/user") {
      return sendJson({
        id: "usr-e2e-123",
        aud: "authenticated",
        role: "authenticated",
        email: "e2e@example.com",
        email_confirmed_at: new Date().toISOString(),
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        app_metadata: { provider: "email" },
        user_metadata: { display_name: "E2E User" },
      });
    }

    // Magic-link sign-in. The app is passwordless, so "sign up" is the same
    // request: Supabase creates the user on first OTP if needed.
    if (url.pathname === "/auth/v1/otp" && method === "POST") {
      readJson().then(() => sendJson({}, 200));
      return;
    }

    // 2. Workspaces endpoint
    if (url.pathname === "/v1/workspaces") {
      return sendJson({
        workspaces: [
          {
            id: "ws-e2e",
            name: "E2E Workspace",
            owner_id: "usr-e2e-123",
            created_at: new Date().toISOString(),
          },
        ],
      });
    }

    // 3. Project list and creation
    if (url.pathname === "/v1/workspaces/ws-e2e/projects" && method === "GET") {
      return sendJson({ items: projects, next_cursor: null });
    }

    if (url.pathname === "/v1/workspaces/ws-e2e/projects" && method === "POST") {
      readJson().then((body) => {
        const now = new Date().toISOString();
        const project = {
          id: `proj-e2e-${projects.length + 1}`,
          workspace_id: "ws-e2e",
          name: body.name,
          description: body.description ?? null,
          cover_asset_id: null,
          created_by: "usr-e2e-123",
          created_at: now,
          updated_at: now,
          archived_at: null,
        };
        projects = [project, ...projects];
        sendJson(project, 201);
      });
      return;
    }

    // 4. Project detail
    const projectMatch = url.pathname.match(/^\/v1\/projects\/([^/]+)$/);
    if (projectMatch && method === "GET") {
      const project = projects.find((item) => item.id === projectMatch[1]);
      if (!project) return sendProblem(404, "PROJECT_NOT_FOUND", "Project not found");
      return sendJson(project);
    }

    // 5. Assets
    const assetListMatch = url.pathname.match(/^\/v1\/projects\/([^/]+)\/assets$/);
    if (assetListMatch && method === "GET") {
      const projectId = assetListMatch[1];
      const kind = url.searchParams.get("kind");
      const origin = url.searchParams.get("origin");
      const items = assets.filter(
        (asset) =>
          asset.project_id === projectId &&
          (!kind || asset.kind === kind) &&
          (!origin || asset.origin === origin)
      );
      return sendJson({ items, next_cursor: null });
    }

    const uploadMatch = url.pathname.match(/^\/v1\/projects\/([^/]+)\/assets\/uploads$/);
    if (uploadMatch && method === "POST") {
      readJson().then((body) => {
        const projectId = uploadMatch[1];
        const assetId = `asset-upload-${Date.now()}`;
        pendingUpload = {
          id: assetId,
          projectId,
          filename: body.filename || "upload.png",
          mime_type: body.mime_type || "image/png",
          size_bytes: body.size_bytes || 1024,
        };
        sendJson(
          {
            asset_id: assetId,
            upload_url: `http://127.0.0.1:${port}/storage-upload/${assetId}`,
          },
          201
        );
      });
      return;
    }

    // Direct storage upload simulation (PUT)
    if (url.pathname.startsWith("/storage-upload/") && method === "PUT") {
      req.on("data", () => {});
      req.on("end", () => {
        res.statusCode = 200;
        res.end();
      });
      return;
    }

    // Complete upload
    const completeMatch = url.pathname.match(/^\/v1\/assets\/(.+)\/complete$/);
    if (completeMatch && method === "POST") {
      const assetId = completeMatch[1];
      const projectId = pendingUpload?.projectId || SEED_PROJECT_ID;
      const mimeType = pendingUpload?.mime_type || "image/png";
      const isVideo = mimeType.startsWith("video/");
      const newAsset = {
        id: assetId,
        workspace_id: "ws-e2e",
        project_id: projectId,
        kind: isVideo ? "video" : "image",
        origin: "upload",
        mime_type: mimeType,
        size_bytes: pendingUpload?.size_bytes || 1024,
        width: isVideo ? null : 512,
        height: isVideo ? null : 512,
        duration_ms: isVideo ? 3000 : null,
        fps: null,
        storage_path: `ws-e2e/${projectId}/${assetId}/original.${isVideo ? "mp4" : "png"}`,
        thumbnail_path: null,
        thumbnail_url: null,
        signed_url: `http://127.0.0.1:${port}/media/ws-e2e/${projectId}/${assetId}/original.${isVideo ? "mp4" : "png"}`,
        source_job_id: null,
        parent_asset_id: null,
        metadata: {
          filename: pendingUpload?.filename || "e2e_photo.png",
          status: "ready",
        },
        created_at: new Date().toISOString(),
      };
      assets.unshift(newAsset);
      return sendJson(newAsset);
    }

    // Asset detail / soft-delete
    const assetDetailMatch = url.pathname.match(/^\/v1\/assets\/([^/]+)$/);
    if (assetDetailMatch && method === "GET") {
      const assetId = assetDetailMatch[1];
      const found = assets.find((a) => a.id === assetId);
      if (found) {
        return sendJson({
          ...found,
          lineage: {
            source_job: null,
            inputs: [],
            parent: null,
          },
        });
      }
      return sendProblem(404, "ASSET_NOT_FOUND", "Asset not found");
    }

    if (assetDetailMatch && method === "DELETE") {
      const assetId = assetDetailMatch[1];
      const idx = assets.findIndex((a) => a.id === assetId);
      if (idx !== -1) {
        assets.splice(idx, 1);
      }
      res.statusCode = 204;
      return res.end();
    }

    // 6. Models
    if (url.pathname === "/v1/models" && method === "GET") {
      const taskType = url.searchParams.get("task_type");
      return sendJson(taskType ? models.filter((model) => model.task_type === taskType) : models);
    }

    // 7. Generations
    const generationListMatch = url.pathname.match(/^\/v1\/projects\/([^/]+)\/generations$/);
    if (generationListMatch && method === "GET") {
      const projectId = generationListMatch[1];
      const status = url.searchParams.get("status");
      const items = jobs.filter(
        (job) => job.project_id === projectId && (!status || job.status === status)
      );
      return sendJson({ items: items.map(publicJob), next_cursor: null });
    }

    if (generationListMatch && method === "POST") {
      readJson().then((body) => {
        const projectId = generationListMatch[1];
        const prompt = body?.prompt || "";

        // Simulated credit exhaustion, matching the API's 402 problem body.
        if (/NO_CREDITS/i.test(prompt)) {
          return sendProblem(
            402,
            "INSUFFICIENT_CREDITS",
            "Not enough credits to submit this generation."
          );
        }

        const job = makeJob(projectId, body);
        jobs.unshift(job);
        sendJson(publicJob(job), 202);
      });
      return;
    }

    // Cancel a queued/running job.
    const cancelMatch = url.pathname.match(/^\/v1\/generations\/([^/]+)\/cancel$/);
    if (cancelMatch && method === "POST") {
      const job = jobs.find((item) => item.id === cancelMatch[1]);
      if (!job) return sendProblem(404, "GENERATION_NOT_FOUND", "Generation not found");
      if (!["queued", "submitting", "running", "finalizing"].includes(job.status)) {
        return sendProblem(409, "JOB_NOT_CANCELABLE", "This job can no longer be canceled.");
      }
      job.status = "canceled";
      job.completed_at = new Date().toISOString();
      return sendJson(publicJob(job));
    }

    // Re-run a failed/canceled job. Retried jobs complete successfully so the
    // UI can demonstrate the full recovery path.
    const retryMatch = url.pathname.match(/^\/v1\/generations\/([^/]+)\/retry$/);
    if (retryMatch && method === "POST") {
      const original = jobs.find((item) => item.id === retryMatch[1]);
      if (!original) return sendProblem(404, "GENERATION_NOT_FOUND", "Generation not found");
      const retried = makeJob(
        original.project_id,
        {
          task_type: original.task_type,
          prompt: original.prompt,
          params: original.params,
          inputs: original.inputs,
        },
        { _shouldFail: false, _slow: false }
      );
      jobs.unshift(retried);
      return sendJson(publicJob(retried), 202);
    }

    // Generation detail (drives the polling fallback in the browser)
    const generationMatch = url.pathname.match(/^\/v1\/generations\/([^/]+)$/);
    if (generationMatch && method === "GET") {
      const job = jobs.find((item) => item.id === generationMatch[1]);
      if (!job) return sendProblem(404, "GENERATION_NOT_FOUND", "Generation not found");

      progressJob(job);
      return sendJson(publicJob(job));
    }

    // 8. Serve media images
    if (url.pathname.startsWith("/media/")) {
      const isVideo = url.pathname.endsWith(".mp4");
      res.statusCode = 200;
      res.setHeader("Content-Type", isVideo ? "video/mp4" : "image/png");
      return res.end(TINY_PNG);
    }

    res.statusCode = 404;
    res.end("Not found");
  });

  server.listen(port, "127.0.0.1", () => {
    console.log(`[mock-backend] Listening on http://127.0.0.1:${port}`);
  });

  return server;
}

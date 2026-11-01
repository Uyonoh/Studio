import http from "node:http";

// 1x1 transparent PNG
const TINY_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
  "base64"
);

export function startMockBackend(port = 3101) {
  const assets = [
    {
      id: "asset-seed-1",
      workspace_id: "ws-e2e",
      project_id: "proj-e2e",
      kind: "image",
      origin: "upload",
      mime_type: "image/png",
      size_bytes: 1024,
      width: 512,
      height: 512,
      duration_ms: null,
      fps: null,
      storage_path: "ws-e2e/proj-e2e/asset-seed-1/original.png",
      thumbnail_path: null,
      thumbnail_url: null,
      signed_url: `http://127.0.0.1:${port}/media/ws-e2e/proj-e2e/asset-seed-1/original.png`,
      source_job_id: null,
      parent_asset_id: null,
      metadata: { filename: "seeded_photo.png", status: "ready" },
      created_at: new Date().toISOString(),
    },
  ];

  let pendingUpload = null;

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

    // 1. Supabase auth endpoints (called by server/middleware)
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

    // 3. Project detail
    if (url.pathname === "/v1/projects/proj-e2e") {
      return sendJson({
        id: "proj-e2e",
        workspace_id: "ws-e2e",
        name: "Brand Launch",
        description: "E2E workspace test project",
        created_by: "usr-e2e-123",
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
        archived_at: null,
      });
    }

    // 4. List assets
    if (url.pathname === "/v1/projects/proj-e2e/assets" && method === "GET") {
      return sendJson({
        items: assets,
        next_cursor: null,
      });
    }

    // 5. Request upload
    if (url.pathname === "/v1/projects/proj-e2e/assets/uploads" && method === "POST") {
      readJson().then((body) => {
        const assetId = `asset-upload-${Date.now()}`;
        pendingUpload = {
          id: assetId,
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

    // 6. Direct storage upload simulation (PUT)
    if (url.pathname.startsWith("/storage-upload/") && method === "PUT") {
      req.on("data", () => {});
      req.on("end", () => {
        res.statusCode = 200;
        res.end();
      });
      return;
    }

    // 7. Complete upload
    const completeMatch = url.pathname.match(/^\/v1\/assets\/(.+)\/complete$/);
    if (completeMatch && method === "POST") {
      const assetId = completeMatch[1];
      const newAsset = {
        id: assetId,
        workspace_id: "ws-e2e",
        project_id: "proj-e2e",
        kind: "image",
        origin: "upload",
        mime_type: pendingUpload?.mime_type || "image/png",
        size_bytes: pendingUpload?.size_bytes || 1024,
        width: 512,
        height: 512,
        duration_ms: null,
        fps: null,
        storage_path: `ws-e2e/proj-e2e/${assetId}/original.png`,
        thumbnail_path: null,
        thumbnail_url: null,
        signed_url: `http://127.0.0.1:${port}/media/ws-e2e/proj-e2e/${assetId}/original.png`,
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

    // 8. Asset detail
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
      return sendJson({ detail: "Asset not found" }, 404);
    }

    // 9. Soft-delete asset
    if (assetDetailMatch && method === "DELETE") {
      const assetId = assetDetailMatch[1];
      const idx = assets.findIndex((a) => a.id === assetId);
      if (idx !== -1) {
        assets.splice(idx, 1);
      }
      res.statusCode = 204;
      return res.end();
    }

    // 10. Serve media images
    if (url.pathname.startsWith("/media/")) {
      res.statusCode = 200;
      res.setHeader("Content-Type", "image/png");
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

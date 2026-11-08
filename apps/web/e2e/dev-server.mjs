import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { startMockBackend } from "./mock-backend.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, "..");

const mockServer = startMockBackend(3101);

const nextBin = path.join(appRoot, "node_modules", "next", "dist", "bin", "next");

const env = {
  ...process.env,
  PORT: "3100",
  NEXT_PUBLIC_API_URL: "http://127.0.0.1:3101",
  NEXT_PUBLIC_SUPABASE_URL: "http://127.0.0.1:3101",
  NEXT_PUBLIC_SUPABASE_ANON_KEY: "test-anon-key",
  NEXT_TELEMETRY_DISABLED: "1",
};

// CI builds the app first and runs `next start`, which avoids the multi-minute
// on-demand compilation of `next dev` and keeps the suite under its time budget.
const useProductionBuild = process.env.E2E_USE_PROD === "1";
const nextCommand = useProductionBuild ? "start" : "dev";

const child = spawn(
  process.execPath,
  [nextBin, nextCommand, "-H", "127.0.0.1", "-p", "3100"],
  {
    cwd: appRoot,
    stdio: "inherit",
    env,
  }
);

function cleanup() {
  try {
    child.kill("SIGTERM");
  } catch {}
  try {
    mockServer.close();
  } catch {}
}

process.on("SIGINT", () => {
  cleanup();
  process.exit(0);
});

process.on("SIGTERM", () => {
  cleanup();
  process.exit(0);
});

child.on("exit", (code) => {
  cleanup();
  process.exit(code ?? 0);
});

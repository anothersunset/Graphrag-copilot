import path from "node:path";
import { fileURLToPath } from "node:url";

// Anchor on the config file's location, not process.cwd(): builds may be
// invoked via `pnpm --filter frontend build` or from inside the directory,
// and the Turbopack workspace root must resolve identically either way.
const appDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(appDirectory, "../..");

/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingRoot: repositoryRoot,
  turbopack: { root: repositoryRoot },
};
export default nextConfig;

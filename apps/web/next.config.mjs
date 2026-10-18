import path from "node:path"
import { fileURLToPath } from "node:url"

const appDirectory = path.dirname(fileURLToPath(import.meta.url))

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Docker image builds copy .next/standalone — a self-contained server
  // bundle with pruned node_modules (see apps/web/Dockerfile).
  output: "standalone",
  outputFileTracingRoot: path.resolve(appDirectory, "../.."),
}

export default nextConfig

/**
 * After `fly launch`, point Vercel's /api proxy at your Fly app:
 *   node scripts/sync-vercel-fly-rewrite.mjs https://your-app.fly.dev
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const vercelPath = path.join(root, "vercel.json");

let base = process.argv[2] || process.env.RLHF_API_ORIGIN;
if (!base) {
  console.error("Usage: node scripts/sync-vercel-fly-rewrite.mjs https://your-app.fly.dev");
  process.exit(1);
}
base = base.replace(/\/$/, "");

const j = JSON.parse(fs.readFileSync(vercelPath, "utf8"));
const apiRewrite = j.rewrites?.find((r) => r.source === "/api/:path*");
if (!apiRewrite) {
  console.error("vercel.json: missing rewrite with source /api/:path*");
  process.exit(1);
}
apiRewrite.destination = `${base}/api/:path*`;
fs.writeFileSync(vercelPath, JSON.stringify(j, null, 2) + "\n");
console.log(`Updated vercel.json API rewrite → ${apiRewrite.destination}`);

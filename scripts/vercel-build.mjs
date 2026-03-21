/**
 * Vercel build: emit `out/` with index.html + tasks + same-origin API (meta *).
 * API requests go to /api/* on Vercel → rewritten to Fly (see vercel.json).
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const out = path.join(root, "out");

function copyDir(src, dest) {
  if (!fs.existsSync(src)) return;
  fs.mkdirSync(dest, { recursive: true });
  for (const name of fs.readdirSync(src)) {
    const s = path.join(src, name);
    const d = path.join(dest, name);
    if (fs.statSync(s).isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

fs.mkdirSync(out, { recursive: true });

const htmlPath = path.join(root, "annotation-tool.html");
let html = fs.readFileSync(htmlPath, "utf8");
html = html.replace(
  /<meta name="rlhf-api-base" content="">/,
  '<meta name="rlhf-api-base" content="*">'
);

fs.writeFileSync(path.join(out, "index.html"), html);
fs.writeFileSync(path.join(out, "annotation-tool.html"), html);

copyDir(path.join(root, "tasks"), path.join(out, "tasks"));
copyDir(path.join(root, "guidelines"), path.join(out, "guidelines"));
copyDir(path.join(root, "templates"), path.join(out, "templates"));

console.log("vercel-build: wrote out/ (index.html, tasks/, guidelines/, templates/)");

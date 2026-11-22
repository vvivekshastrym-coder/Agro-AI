import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';

const root = process.cwd();
const dist = path.join(root, 'dist');
const pub = path.join(root, 'public');

// Clean and recreate ONLY dist/ (DO NOT wipe public/ as it contains committed assets like admin)
if (fs.existsSync(dist)) {
  fs.rmSync(dist, { recursive: true, force: true });
}
fs.mkdirSync(dist, { recursive: true });
fs.mkdirSync(pub, { recursive: true });

const filesToCopy = [
  'index.html',
  'index.modular.html',
  'demo.html',
  'privacy.html',
  'terms.html',
  'cookies.html',
  'delete-account.html',
  'favicon.ico',
  'favicon.png',
  'manifest.webmanifest',
  'sw.js',
  'robots.txt',
];

const dirsToCopy = [
  'css',
  'fonts',
  'js',
  'icons',
];

// Copy files and dirs to dist and ensure public has them
for (const file of filesToCopy) {
  const src = path.join(root, file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(dist, file));
    fs.copyFileSync(src, path.join(pub, file));
  }
}

for (const dir of dirsToCopy) {
  const src = path.join(root, dir);
  if (fs.existsSync(src)) {
    fs.cpSync(src, path.join(dist, dir), { recursive: true });
    fs.cpSync(src, path.join(pub, dir), { recursive: true });
  }
}

// Copy admin assets
const adminDistSrc = path.join(root, 'admin', 'dist');
const adminPubSrc = path.join(pub, 'admin');

if (fs.existsSync(adminDistSrc)) {
  if (fs.existsSync(adminPubSrc)) {
    fs.rmSync(adminPubSrc, { recursive: true, force: true });
  }
  fs.cpSync(adminDistSrc, path.join(dist, 'admin'), { recursive: true });
  fs.cpSync(adminDistSrc, adminPubSrc, { recursive: true });
} else if (fs.existsSync(adminPubSrc)) {
  // If admin/dist is gitignored or not present in CI, use committed public/admin
  fs.cpSync(adminPubSrc, path.join(dist, 'admin'), { recursive: true });
}

// Generate static SEO pages + authoritative sitemap.xml in root and dist/
let pyRan = false;
for (const pyBin of ['py', 'python', 'python3']) {
  try {
    execFileSync(pyBin, ['-m', 'backend.app.seo_pages'], { cwd: root, stdio: 'inherit' });
    pyRan = true;
    break;
  } catch (e) {}
}
if (!pyRan) {
  // Fallback if Python is absent in static build container: copy committed sitemap.xml and SEO routes
  for (const f of ['sitemap.xml', 'robots.txt']) {
    if (fs.existsSync(path.join(root, f))) {
      fs.copyFileSync(path.join(root, f), path.join(dist, f));
    }
  }
  for (const slug of ['diagnose', 'agrogpt', 'weather', 'mandi', 'plans', 'about', 'contact']) {
    fs.copyFileSync(path.join(root, 'index.html'), path.join(dist, `${slug}.html`));
  }
}

console.log('✅ Prepared lightweight mobile web assets in ./dist for Capacitor Android/iOS build.');

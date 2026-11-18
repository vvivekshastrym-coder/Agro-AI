import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';

const root = process.cwd();
const dist = path.join(root, 'dist');

// Clean and recreate dist/
if (fs.existsSync(dist)) {
  fs.rmSync(dist, { recursive: true, force: true });
}
fs.mkdirSync(dist, { recursive: true });

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

for (const file of filesToCopy) {
  const src = path.join(root, file);
  if (fs.existsSync(src)) {
    fs.copyFileSync(src, path.join(dist, file));
  }
}

for (const dir of dirsToCopy) {
  const src = path.join(root, dir);
  if (fs.existsSync(src)) {
    fs.cpSync(src, path.join(dist, dir), { recursive: true });
  }
}

// Copy only compiled admin/dist (never admin/node_modules or admin/src)
const adminDistSrc = path.join(root, 'admin', 'dist');
if (fs.existsSync(adminDistSrc)) {
  fs.cpSync(adminDistSrc, path.join(dist, 'admin'), { recursive: true });
}

// Copy serverless API and backend to dist/ so Vercel functions are included in outputDirectory
const apiSrc = path.join(root, 'api');
if (fs.existsSync(apiSrc)) {
  fs.cpSync(apiSrc, path.join(dist, 'api'), { recursive: true });
}
const backendSrc = path.join(root, 'backend');
if (fs.existsSync(backendSrc)) {
  fs.cpSync(backendSrc, path.join(dist, 'backend'), { recursive: true });
}
const reqSrc = path.join(root, 'requirements.txt');
if (fs.existsSync(reqSrc)) {
  fs.copyFileSync(reqSrc, path.join(dist, 'requirements.txt'));
}

// Generate static SEO pages + authoritative sitemap.xml in root and dist/
let pyRan = false;
for (const pyBin of ['python3', 'python']) {
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

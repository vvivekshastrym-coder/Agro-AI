import fs from 'fs';
import path from 'path';
import { execFileSync } from 'child_process';

const root = process.cwd();
const dist = path.join(root, 'dist');
const pub = path.join(root, 'public');
const targetDirs = [dist, pub];

// Clean and recreate dist/ and public/
for (const target of targetDirs) {
  if (fs.existsSync(target)) {
    fs.rmSync(target, { recursive: true, force: true });
  }
  fs.mkdirSync(target, { recursive: true });
}

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

for (const target of targetDirs) {
  for (const file of filesToCopy) {
    const src = path.join(root, file);
    if (fs.existsSync(src)) {
      fs.copyFileSync(src, path.join(target, file));
    }
  }

  for (const dir of dirsToCopy) {
    const src = path.join(root, dir);
    if (fs.existsSync(src)) {
      fs.cpSync(src, path.join(target, dir), { recursive: true });
    }
  }

  // Copy only compiled admin/dist (never admin/node_modules or admin/src)
  const adminDistSrc = path.join(root, 'admin', 'dist');
  if (fs.existsSync(adminDistSrc)) {
    fs.cpSync(adminDistSrc, path.join(target, 'admin'), { recursive: true });
  }
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

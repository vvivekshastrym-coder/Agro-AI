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

// Generate static SEO pages + authoritative sitemap.xml in root and dist/
execFileSync('python', ['-m', 'backend.app.seo_pages'], { cwd: root, stdio: 'inherit' });

console.log('✅ Prepared lightweight mobile web assets in ./dist for Capacitor Android/iOS build.');

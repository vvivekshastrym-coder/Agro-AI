import fs from 'fs';
import path from 'path';

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
  'delete-account.html',
  'favicon.png',
  'manifest.webmanifest',
  'sw.js',
];

const dirsToCopy = [
  'css',
  'js',
  'icons',
  'admin',
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

console.log('✅ Prepared mobile web assets in ./dist for Capacitor Android/iOS build.');

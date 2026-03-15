const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', 'electron');
const DST = path.join(__dirname, '..', 'dist-webview');
const SKIP = ['main.js', 'preload.js'];

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, e.name);
    const d = path.join(dest, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else if (!SKIP.includes(e.name)) fs.copyFileSync(s, d);
  }
}

if (fs.existsSync(DST)) fs.rmSync(DST, { recursive: true });
copyDir(SRC, DST);
console.log('Webview assets copied to dist-webview/');

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const ROOT = path.join(__dirname, '..');
const BACKEND = path.join(ROOT, 'backend');
const BACKEND_PACK = path.join(ROOT, 'backend-pack');

function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const e of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, e.name);
    const d = path.join(dest, e.name);
    if (e.isDirectory()) copyDir(s, d);
    else fs.copyFileSync(s, d);
  }
}

function rmDir(dir) {
  if (!fs.existsSync(dir)) return;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) rmDir(p);
    else fs.unlinkSync(p);
  }
  fs.rmdirSync(dir);
}

function main() {
  if (fs.existsSync(BACKEND_PACK)) rmDir(BACKEND_PACK);
  copyDir(BACKEND, BACKEND_PACK);

  const hasPyArmor = spawnSync('python', ['-m', 'pyarmor', '--version'], { encoding: 'utf8' }).status === 0;
  if (hasPyArmor) {
    console.log('Protecting backend with PyArmor...');
    const r = spawnSync('python', ['-m', 'pyarmor', 'gen', '-r', '-O', BACKEND_PACK, BACKEND], { stdio: 'inherit' });
    if (r.status !== 0) {
      console.error('PyArmor failed. Using plain backend.');
      rmDir(BACKEND_PACK);
      copyDir(BACKEND, BACKEND_PACK);
    }
  } else {
    console.log('PyArmor not installed (pip install pyarmor). Using plain backend.');
  }
  console.log('Backend prepared at backend-pack/');
}

main();

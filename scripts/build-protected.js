const { spawnSync } = require('child_process');
const path = require('path');

const root = path.join(__dirname, '..');
const obfuscate = path.join(__dirname, 'obfuscate-renderer.js');

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { stdio: 'inherit', cwd: root, ...opts });
  return r.status;
}

let exitCode = 0;
exitCode = run('npm', ['run', 'prebuild']) || exitCode;
if (exitCode) process.exit(exitCode);
exitCode = run('node', [obfuscate, 'obfuscate']) || exitCode;
if (exitCode) { run('node', [obfuscate, 'restore']); process.exit(exitCode); }
exitCode = run('node', [path.join(__dirname, 'prepare-backend.js')]) || exitCode;
if (exitCode) { run('node', [obfuscate, 'restore']); process.exit(exitCode); }
exitCode = run('npx', ['electron-builder', '--config', 'electron-builder.release.yml']);
run('node', [obfuscate, 'restore']);
process.exit(exitCode);

#!/usr/bin/env node
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const backendDir = path.join(__dirname, '..', 'backend');
const pyRuntime = path.join(__dirname, '..', 'python-runtime');
const sysPython = process.env.PYTHON || 'python';
const embedPython = process.platform === 'win32'
  ? path.join(pyRuntime, 'python.exe')
  : path.join(pyRuntime, 'bin', 'python3');

const python = fs.existsSync(embedPython) ? embedPython : sysPython;
const cli = path.join(backendDir, 'cli.py');

const env = { ...process.env };
env.PYTHONPATH = backendDir;
env.WORKSPACE_ROOT = env.WORKSPACE_ROOT || process.cwd();

const child = spawn(python, [cli, ...process.argv.slice(2)], {
  stdio: 'inherit',
  env,
  cwd: process.cwd(),
});

child.on('exit', (code) => process.exit(code || 0));

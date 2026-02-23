const fs = require('fs');
const path = require('path');
const https = require('https');
const { execSync } = require('child_process');

const PYTHON_VERSION = '3.12.7';
const PYTHON_EMBED_URL_WIN64 = `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`;
const GET_PIP_URL = 'https://bootstrap.pypa.io/get-pip.py';
const OUT_DIR = path.join(__dirname, '..', 'python-runtime');
const BACKEND_DIR = path.join(__dirname, '..', 'backend');

function download(url) {
  return new Promise((resolve, reject) => {
    const file = path.join(require('os').tmpdir(), `python-embed-${Date.now()}.zip`);
    const stream = fs.createWriteStream(file);
    const req = https.get(url, { headers: { 'User-Agent': 'Node' } }, (res) => {
      if (res.statusCode === 302 || res.statusCode === 301) {
        const redirect = res.headers.location;
        return download(redirect.startsWith('http') ? redirect : new URL(redirect, url).href).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        stream.close();
        fs.unlink(file, () => {});
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      res.pipe(stream);
      stream.on('finish', () => {
        stream.close();
        resolve(file);
      });
    });
    req.on('error', (err) => {
      stream.close();
      fs.unlink(file, () => {});
      reject(err);
    });
  });
}

function downloadToFile(url, filePath) {
  return new Promise((resolve, reject) => {
    const stream = fs.createWriteStream(filePath);
    https.get(url, { headers: { 'User-Agent': 'Node' } }, (res) => {
      if (res.statusCode === 302 || res.statusCode === 301) {
        const redirect = res.headers.location;
        return downloadToFile(redirect.startsWith('http') ? redirect : new URL(redirect, url).href, filePath).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        stream.close();
        reject(new Error(`HTTP ${res.statusCode}`));
        return;
      }
      res.pipe(stream);
      stream.on('finish', () => {
        stream.close();
        resolve();
      });
    }).on('error', reject);
  });
}

function unzip(zipPath, destDir) {
  const platform = process.platform;
  const zipAbs = path.resolve(zipPath);
  const destAbs = path.resolve(destDir);
  if (platform === 'win32') {
    execSync(`powershell -NoProfile -Command "Expand-Archive -LiteralPath '${zipAbs.replace(/'/g, "''")}' -DestinationPath '${destAbs.replace(/'/g, "''")}' -Force"`, { stdio: 'inherit' });
    return;
  }
  execSync(`unzip -o "${zipPath}" -d "${destDir}"`, { stdio: 'inherit' });
}

function enableSiteInPth(runtimeDir) {
  const files = fs.readdirSync(runtimeDir);
  const pthFile = files.find((f) => f.endsWith('._pth'));
  if (!pthFile) return;
  const pthPath = path.join(runtimeDir, pthFile);
  let content = fs.readFileSync(pthPath, 'utf8');
  const lines = content.split(/\r?\n/);
  if (lines.some((l) => l.trim() === 'import site')) return;
  const newLines = lines.map((line) => {
    const t = line.trim();
    if ((t.startsWith('#') && t.includes('import site')) || t === '#import site' || t === '# import site') return 'import site';
    return line;
  });
  if (!newLines.some((l) => l.trim() === 'import site')) newLines.push('import site');
  fs.writeFileSync(pthPath, newLines.join('\n'), 'utf8');
}

function installPipAndDeps(runtimeDir) {
  const pyExe = path.join(runtimeDir, 'python.exe');
  if (!fs.existsSync(pyExe)) return;
  const getPipPath = path.join(require('os').tmpdir(), 'get-pip.js');
  console.log('Downloading get-pip.py...');
  return downloadToFile(GET_PIP_URL, getPipPath + '.py')
    .then(() => {
      console.log('Installing pip into embedded Python...');
      execSync(`"${pyExe}" "${getPipPath}.py"`, {
        cwd: runtimeDir,
        stdio: 'inherit',
        env: { ...process.env, PYTHONUSERBASE: runtimeDir }
      });
      try { fs.unlinkSync(getPipPath + '.py'); } catch (_) {}
    })
    .then(() => {
      const reqPath = path.join(BACKEND_DIR, 'requirements.txt');
      if (!fs.existsSync(reqPath)) {
        console.log('No backend/requirements.txt found, skipping pip install.');
        return;
      }
      console.log('Installing backend dependencies...');
      execSync(`"${pyExe}" -m pip install -r "${reqPath}"`, {
        cwd: runtimeDir,
        stdio: 'inherit'
      });
    })
    .catch((err) => {
      console.error('installPipAndDeps failed:', err.message);
      throw err;
    });
}

function main() {
  if (process.platform !== 'win32') {
    console.log('prepare-python: Windows embeddable package only. On Mac/Linux the app uses system Python.');
    process.exit(0);
    return;
  }
  const pyExe = path.join(OUT_DIR, 'python.exe');
  const needDownload = !fs.existsSync(pyExe);
  const p = needDownload
    ? Promise.resolve()
        .then(() => {
          fs.mkdirSync(OUT_DIR, { recursive: true });
          console.log('Downloading Python embeddable...');
          return download(PYTHON_EMBED_URL_WIN64);
        })
        .then((zipPath) => {
          console.log('Extracting to python-runtime/...');
          unzip(zipPath, OUT_DIR);
          fs.unlinkSync(zipPath);
          enableSiteInPth(OUT_DIR);
          return installPipAndDeps(OUT_DIR);
        })
        .then(() => console.log('Done. Embedded Python is ready to run the backend.'))
    : (enableSiteInPth(OUT_DIR), installPipAndDeps(OUT_DIR).then(() => console.log('Done.')));

  p.catch((err) => {
    console.error(err);
    process.exit(1);
  }).then(() => {
    process.exit(0);
  });
}

main();

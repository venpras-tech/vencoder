const fs = require('fs');
const path = require('path');

const RENDERER = path.join(__dirname, '..', 'electron', 'renderer.js');
const RENDERER_SRC = path.join(__dirname, '..', 'electron', 'renderer.js.src');

function obfuscate() {
  let obfuscator;
  try {
    obfuscator = require('javascript-obfuscator');
  } catch (e) {
    console.error('Run: npm install --save-dev javascript-obfuscator');
    process.exit(1);
  }
  const code = fs.readFileSync(RENDERER, 'utf8');
  fs.writeFileSync(RENDERER_SRC, code, 'utf8');
  const result = obfuscator.obfuscate(code, {
    compact: true,
    controlFlowFlattening: false,
    deadCodeInjection: false,
    debugProtection: false,
    disableConsoleOutput: false,
    identifierNamesGenerator: 'hexadecimal',
    log: false,
    numbersToExpressions: false,
    renameGlobals: false,
    selfDefending: false,
    simplify: true,
    splitStrings: false,
    stringArray: true,
    stringArrayCallsTransform: false,
    stringArrayEncoding: [],
    stringArrayIndexShift: false,
    stringArrayRotate: false,
    stringArrayShuffle: false,
    stringArrayThreshold: 0.5,
    transformObjectKeys: false,
    unicodeEscapeSequence: false
  });
  fs.writeFileSync(RENDERER, result.getObfuscatedCode(), 'utf8');
  console.log('Obfuscated electron/renderer.js');
}

function restore() {
  if (fs.existsSync(RENDERER_SRC)) {
    fs.copyFileSync(RENDERER_SRC, RENDERER);
    fs.unlinkSync(RENDERER_SRC);
    console.log('Restored electron/renderer.js');
  }
}

const cmd = process.argv[2];
if (cmd === 'restore') restore();
else if (cmd === 'obfuscate' || !cmd) obfuscate();
else {
  console.error('Usage: node obfuscate-renderer.js [obfuscate|restore]');
  process.exit(1);
}

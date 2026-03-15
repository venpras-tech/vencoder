const { PNG } = require("pngjs");
const fs = require("fs");
const path = require("path");

const size = 1024;
const png = new PNG({ width: size, height: size, colorType: 6 });

for (let y = 0; y < size; y++) {
  for (let x = 0; x < size; x++) {
    const idx = (size * y + x) << 2;
    png.data[idx] = 70;
    png.data[idx + 1] = 130;
    png.data[idx + 2] = 180;
    png.data[idx + 3] = 255;
  }
}

const out = path.join(__dirname, "..", "app-icon.png");
fs.writeFileSync(out, PNG.sync.write(png));
console.log("Created app-icon.png");

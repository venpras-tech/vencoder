const fs = require('fs');
const path = require('path');
const { PNG } = require('pngjs');

const size = 512;
const png = new PNG({ width: size, height: size });

for (let y = 0; y < size; y++) {
  for (let x = 0; x < size; x++) {
    const i = (size * y + x) << 2;
    const cx = x - size / 2;
    const cy = y - size / 2;
    const r = Math.sqrt(cx * cx + cy * cy);
    const inCircle = r < size * 0.4;
    if (inCircle) {
      png.data[i] = 26;
      png.data[i + 1] = 54;
      png.data[i + 2] = 93;
      png.data[i + 3] = 255;
    } else {
      png.data[i] = 44;
      png.data[i + 1] = 82;
      png.data[i + 2] = 130;
      png.data[i + 3] = 255;
    }
  }
}

const out = path.join(__dirname, '..', 'app-icon.png');
png.pack().pipe(fs.createWriteStream(out)).on('finish', () => {
  console.log('Created app-icon.png');
});

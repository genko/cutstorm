// After smoke-dedup.mjs has produced smoke_dedup_on.mp4 and smoke_dedup_off.mp4
// (both from the real UI through setInputFiles+export), compare extracted frames.
// Emits MSE per timestamp so acceptance (< 10) can be asserted.
import fs from "node:fs";
import path from "node:path";
import zlib from "node:zlib";

const HERE = path.resolve(new URL(".", import.meta.url).pathname);
const OUT_DIR = path.join(HERE, "e2e/output");

function loadPng(file) {
  const buf = fs.readFileSync(file);
  // Minimal PNG parse: find IHDR (w,h) and concatenated IDAT data.
  // This avoids adding a new dependency for a one-off smoke.
  if (buf.slice(0, 8).toString("hex") !== "89504e470d0a1a0a")
    throw new Error(`${file}: not a PNG`);
  let off = 8;
  let w = 0, h = 0, bitDepth = 0, colorType = 0;
  const idatChunks = [];
  while (off < buf.length) {
    const len = buf.readUInt32BE(off); off += 4;
    const type = buf.slice(off, off + 4).toString("ascii"); off += 4;
    const data = buf.slice(off, off + len); off += len;
    off += 4; // crc
    if (type === "IHDR") {
      w = data.readUInt32BE(0);
      h = data.readUInt32BE(4);
      bitDepth = data[8];
      colorType = data[9];
    } else if (type === "IDAT") {
      idatChunks.push(data);
    } else if (type === "IEND") break;
  }
  if (bitDepth !== 8) throw new Error(`${file}: unsupported bitDepth ${bitDepth}`);
  const channels = colorType === 2 ? 3 : colorType === 6 ? 4 : colorType === 0 ? 1 : (() => {
    throw new Error(`${file}: unsupported colorType ${colorType}`);
  })();
  const raw = zlib.inflateSync(Buffer.concat(idatChunks));
  const stride = w * channels;
  const out = Buffer.alloc(h * stride);
  let prev = Buffer.alloc(stride);
  let pos = 0;
  for (let y = 0; y < h; y++) {
    const filter = raw[pos]; pos++;
    const row = Buffer.from(raw.slice(pos, pos + stride));
    pos += stride;
    // Un-filter per PNG spec.
    for (let x = 0; x < stride; x++) {
      const a = x >= channels ? row[x - channels] : 0;
      const b = prev[x];
      const c = x >= channels ? prev[x - channels] : 0;
      let recon;
      if (filter === 0) recon = row[x];
      else if (filter === 1) recon = row[x] + a;
      else if (filter === 2) recon = row[x] + b;
      else if (filter === 3) recon = row[x] + ((a + b) >> 1);
      else if (filter === 4) {
        // Paeth
        const p = a + b - c;
        const pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
        const pr = pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
        recon = row[x] + pr;
      } else throw new Error(`${file}: unknown filter ${filter}`);
      row[x] = recon & 0xff;
    }
    row.copy(out, y * stride);
    prev = row;
  }
  return { w, h, channels, pixels: out };
}

function mse(a, b) {
  if (a.w !== b.w || a.h !== b.h) throw new Error(`dim mismatch ${a.w}x${a.h} vs ${b.w}x${b.h}`);
  const n = Math.min(a.pixels.length, b.pixels.length);
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const d = a.pixels[i] - b.pixels[i];
    sum += d * d;
  }
  return sum / n;
}

const timestamps = [0.5, 1.5, 2.5];
let maxMse = 0;
console.log("[pixel-parity] timestamps:", timestamps);
for (const t of timestamps) {
  const onPng = path.join(OUT_DIR, `smoke_dedup_on_t${t}.png`);
  const offPng = path.join(OUT_DIR, `smoke_dedup_off_t${t}.png`);
  if (!fs.existsSync(onPng) || !fs.existsSync(offPng)) {
    console.error(`Missing ${onPng} or ${offPng}`);
    process.exit(2);
  }
  const a = loadPng(onPng);
  const b = loadPng(offPng);
  const m = mse(a, b);
  maxMse = Math.max(maxMse, m);
  console.log(`[pixel-parity] t=${t}s  MSE=${m.toFixed(3)}  (${a.w}x${a.h})`);
}
console.log(`[pixel-parity] max MSE=${maxMse.toFixed(3)}  threshold=10`);
if (maxMse >= 10) {
  console.error("[pixel-parity] FAIL: max MSE >= 10");
  process.exit(1);
}
console.log("[pixel-parity] OK");

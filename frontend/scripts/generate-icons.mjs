// Genera los iconos PWA (PNG) sin dependencias externas.
// Uso: node scripts/generate-icons.mjs
import { deflateSync } from 'node:zlib'
import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const outDir = join(root, 'public', 'icons')
mkdirSync(outDir, { recursive: true })

const SS = 4 // supersampling
const lerp = (a, b, t) => a + (b - a) * t

function makeIcon(size, { maskable = false, glyphScale = 1 } = {}) {
  const S = size * SS
  const base = new Float64Array(S * S * 3) // [r,g,b] floats

  // fondo: gradiente diagonal cyan -> violeta
  const c1 = [34, 211, 238]
  const c2 = [167, 139, 250]
  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const t = (x + y) / (2 * S)
      const i = (y * S + x) * 3
      base[i] = lerp(c1[0], c2[0], t)
      base[i + 1] = lerp(c1[1], c2[1], t)
      base[i + 2] = lerp(c1[2], c2[2], t)
    }
  }

  const cx = S / 2
  const gs = 0.5 * (maskable ? 0.86 : 1) * glyphScale
  // cilindro de base de datos
  const rx = S * 0.30 * gs
  const ry = S * 0.115 * gs
  const top = S * 0.40 * gs
  const height = S * 0.30 * gs
  const bottom = top + height

  const dark = [10, 15, 30]
  const stripe = [34, 211, 238]

  const inEllipse = (px, py, cy) => {
    const dx = (px - cx) / rx
    const dy = (py - cy) / ry
    return dx * dx + dy * dy <= 1
  }

  for (let y = 0; y < S; y++) {
    for (let x = 0; x < S; x++) {
      const i = (y * S + x) * 3
      let r = base[i], g = base[i + 1], b = base[i + 2]

      const inTopCap = inEllipse(x, y, top)
      const inBottomCap = inEllipse(x, y, bottom)
      const inBody = y >= top && y <= bottom && x >= cx - rx && x <= cx + rx

      if (inTopCap || inBody || inBottomCap) {
        r = dark[0]; g = dark[1]; b = dark[2]
      }
      // franjas horizontales del cilindro (sugieren datos)
      const stripeTop = top + height * 0.62
      const stripeBottom = stripeTop + S * 0.045
      if (x >= cx - rx * 0.82 && x <= cx + rx * 0.82 && y >= stripeTop && y <= stripeBottom) {
        r = stripe[0]; g = stripe[1]; b = stripe[2]
      }
      // brillo superior del cilindro
      if ((inBody && y >= top && y <= top + height * 0.12) ||
          (inTopCap && y <= top + ry * 0.05)) {
        r = lerp(r, 255, 0.14); g = lerp(g, 255, 0.14); b = lerp(b, 255, 0.14)
      }

      base[i] = r; base[i + 1] = g; base[i + 2] = b
    }
  }

  // downsample SS -> 1 y construir pixels RGBA con alpha redondeado
  const px = Buffer.alloc(size * size * 4)
  const radius = size * (maskable ? 0 : 0.22)
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      let r = 0, g = 0, b = 0
      for (let sy = 0; sy < SS; sy++) {
        for (let sx = 0; sx < SS; sx++) {
          const idx = ((y * SS + sy) * S + (x * SS + sx)) * 3
          r += base[idx]; g += base[idx + 1]; b += base[idx + 2]
        }
      }
      const n = SS * SS
      // esquinas redondeadas (solo para el icon silueta; maskable a sangre completa)
      let alpha = 255
      if (!maskable) {
        const dx = Math.max(radius - x, 0, x - (size - 1 - radius))
        const dy = Math.max(radius - y, 0, y - (size - 1 - radius))
        const d = Math.sqrt(dx * dx + dy * dy)
        if (d > radius) alpha = 0
      }
      const o = (y * size + x) * 4
      px[o] = Math.round(r / n)
      px[o + 1] = Math.round(g / n)
      px[o + 2] = Math.round(b / n)
      px[o + 3] = alpha
    }
  }
  return encodePNG(size, px)
}

function crc32(buf) {
  let crc = ~0
  for (let i = 0; i < buf.length; i++) {
    crc ^= buf[i]
    for (let k = 0; k < 8; k++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1))
  }
  return (~crc) >>> 0
}

function chunk(type, data) {
  const t = Buffer.from(type, 'ascii')
  const len = Buffer.alloc(4)
  len.writeUInt32BE(data.length)
  const crc = Buffer.alloc(4)
  crc.writeUInt32BE(crc32(Buffer.concat([t, data])))
  return Buffer.concat([len, t, data, crc])
}

function encodePNG(size, rgba) {
  const sig = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])
  const ihdr = Buffer.alloc(13)
  ihdr.writeUInt32BE(size, 0)
  ihdr.writeUInt32BE(size, 4)
  ihdr[8] = 8  // bit depth
  ihdr[9] = 6  // color type RGBA
  // filtrado
  const stride = size * 4
  const raw = Buffer.alloc((stride + 1) * size)
  for (let y = 0; y < size; y++) {
    raw[y * (stride + 1)] = 0
    rgba.copy(raw, y * (stride + 1) + 1, y * stride, (y + 1) * stride)
  }
  const idat = deflateSync(raw, { level: 9 })
  return Buffer.concat([sig, chunk('IHDR', ihdr), chunk('IDAT', idat), chunk('IEND', Buffer.alloc(0))])
}

const files = {
  'icon-192.png': makeIcon(192),
  'icon-512.png': makeIcon(512),
  'maskable-512.png': makeIcon(512, { maskable: true }),
}
for (const [name, buf] of Object.entries(files)) {
  writeFileSync(join(outDir, name), buf)
  console.log('escrito', join('public/icons', name), buf.length, 'bytes')
}
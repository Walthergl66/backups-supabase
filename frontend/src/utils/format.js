function parseApiDate(isoString) {
  if (!isoString) return null
  const s = String(isoString).trim()
  // La API devuelve fechas de SQLite datetime('now') = UTC sin sufijo
  // (ej. "2026-09-12 01:53:53"). Sin zona horaria, JS las interpretaría
  // como hora local; se fuerzan como UTC añadiendo 'Z'.
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?$/.test(s)) {
    const d = new Date(s.replace(' ', 'T') + 'Z')
    return Number.isNaN(d.getTime()) ? null : d
  }
  const d = new Date(s)
  return Number.isNaN(d.getTime()) ? null : d
}

export function fmtFecha(isoString, dateOnly = false) {
  const d = parseApiDate(isoString)
  if (!d) return isoString || '-'
  if (dateOnly) {
    return d.toLocaleDateString('es', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    })
  }
  return d.toLocaleString('es', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function fmtFechaDate(isoString) {
  return fmtFecha(isoString, true)
}

export function fmtBytes(n) {
  if (n === null || n === undefined) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let v = Number(n)
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`
}
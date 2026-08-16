/** Subtitle time helpers and exporters. All times are seconds (float). */

export function clampTime(t) {
  return Number.isFinite(t) && t > 0 ? t : 0
}

/** 75.25 -> "01:15.25" (compact, for the editor UI) */
export function formatShort(seconds) {
  const s = clampTime(seconds)
  const m = Math.floor(s / 60)
  const rest = s - m * 60
  return `${String(m).padStart(2, '0')}:${rest.toFixed(2).padStart(5, '0')}`
}

/** 75.25 -> "00:01:15,250" (SRT) or "00:01:15.250" (VTT) */
export function formatTimestamp(seconds, sep = ',') {
  const s = clampTime(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  const ms = Math.round((s - Math.floor(s)) * 1000)
  const p = (n, w = 2) => String(n).padStart(w, '0')
  return `${p(h)}:${p(m)}:${p(sec)}${sep}${p(ms, 3)}`
}

/** "00:01:15,250" -> 75.25 */
export function parseTimestamp(str) {
  const m = /^(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})$/.exec(String(str).trim())
  if (!m) return null
  return (
    Number(m[1]) * 3600 +
    Number(m[2]) * 60 +
    Number(m[3]) +
    Number(m[4].padEnd(3, '0')) / 1000
  )
}

/**
 * @param {Array<{start:number,end:number,target:string,source:string}>} segments
 * @param {{field?: 'target'|'source'}} opts
 */
export function toSRT(segments, opts = {}) {
  const field = opts.field || 'target'
  return (
    segments
      .filter((s) => (s[field] || '').trim().length > 0)
      .map((s, i) => {
        const text = (s[field] || '').trim()
        return `${i + 1}\n${formatTimestamp(s.start, ',')} --> ${formatTimestamp(s.end, ',')}\n${text}\n`
      })
      .join('\n') + '\n'
  )
}

export function toVTT(segments, opts = {}) {
  const field = opts.field || 'target'
  const body = segments
    .filter((s) => (s[field] || '').trim().length > 0)
    .map((s) => {
      const text = (s[field] || '').trim()
      return `${formatTimestamp(s.start, '.')} --> ${formatTimestamp(s.end, '.')}\n${text}\n`
    })
    .join('\n')
  return `WEBVTT\n\n${body}\n`
}

/** Plain transcript, one paragraph per segment. */
export function toTXT(segments, opts = {}) {
  const field = opts.field || 'target'
  return segments.map((s) => (s[field] || '').trim()).filter(Boolean).join('\n\n') + '\n'
}

/** Bilingual review file for the org's proof-readers. */
export function toBilingualTXT(segments) {
  return (
    segments
      .map(
        (s, i) =>
          `[${i + 1}] ${formatShort(s.start)} → ${formatShort(s.end)}\n` +
          `MR: ${(s.source || '').trim()}\n` +
          `   ${(s.target || '').trim()}`
      )
      .join('\n\n') + '\n'
  )
}

export function downloadText(filename, text, mime = 'text/plain;charset=utf-8') {
  const blob = new Blob([text], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  // Give the browser a tick to start the download before revoking.
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

/** Warn the proof-reader about subtitles that are physically hard to read. */
export function segmentWarnings(seg) {
  const warnings = []
  const dur = seg.end - seg.start
  const text = (seg.target || '').trim()
  if (dur <= 0) warnings.push('End time is before start time')
  if (text.length > 84) warnings.push('Longer than 84 characters')
  if (dur > 0 && text.length / dur > 21) warnings.push('Reading speed above 21 chars/sec')
  if (dur > 0 && dur < 0.7 && text) warnings.push('On screen under 0.7s')
  if (!text) warnings.push('Empty translation')
  return warnings
}

export function baseName(filename = 'subtitles') {
  return filename.replace(/\.[^.]+$/, '') || 'subtitles'
}

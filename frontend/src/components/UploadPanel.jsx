import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Button, Card, Field, Select, ProgressBar, formatBytes, cx } from './ui.jsx'
import { ACCEPTED_EXTENSIONS, LANGUAGES, MAX_FILE_BYTES, kindOf } from '../lib/constants.js'

export default function UploadPanel({ onSubmit }) {
  const [queue, setQueue] = useState([]) // File[]
  const [sourceLang, setSourceLang] = useState('mr')
  const [targetLang, setTargetLang] = useState('hi')
  const targetLangs = LANGUAGES.filter((l) => l.code !== sourceLang)

  // Keep targetLang valid whenever sourceLang changes out from under it.
  useEffect(() => {
    if (sourceLang === targetLang) {
      setTargetLang(targetLangs[0]?.code ?? '')
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceLang])

  const [dragging, setDragging] = useState(false)
  const [busy, setBusy] = useState(false)
  const [uploadPct, setUploadPct] = useState(0)
  const [rejected, setRejected] = useState([])
  const inputRef = useRef(null)
  const dragDepth = useRef(0)

  const accept = useCallback((files) => {
    const ok = []
    const bad = []
    for (const f of files) {
      if (kindOf(f.name) === 'unknown') bad.push(`${f.name} — unsupported file type`)
      else if (f.size > MAX_FILE_BYTES) bad.push(`${f.name} — larger than 2 GB`)
      else ok.push(f)
    }
    setRejected(bad)
    setQueue((prev) => {
      const seen = new Set(prev.map((f) => f.name + f.size))
      return [...prev, ...ok.filter((f) => !seen.has(f.name + f.size))]
    })
  }, [])

  const onDrop = (e) => {
    e.preventDefault()
    dragDepth.current = 0
    setDragging(false)
    accept([...e.dataTransfer.files])
  }

  const submit = async () => {
    if (!queue.length || busy) return
    setBusy(true)
    try {
      for (const file of queue) {
        setUploadPct(0)
        await onSubmit(file, { sourceLang, targetLang, onProgress: setUploadPct })
      }
      setQueue([])
    } finally {
      setBusy(false)
      setUploadPct(0)
    }
  }

  const totalBytes = queue.reduce((sum, f) => sum + f.size, 0)

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-ink-200">New translation job</h2>
        <span className="text-xs text-ink-400">Runs on this machine — nothing leaves the device</span>
      </div>

      <div
        onDragEnter={(e) => {
          e.preventDefault()
          dragDepth.current += 1
          setDragging(true)
        }}
        onDragLeave={() => {
          dragDepth.current -= 1
          if (dragDepth.current <= 0) setDragging(false)
        }}
        onDragOver={(e) => e.preventDefault()}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
        className={cx(
          'flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
          dragging
            ? 'border-leaf-500 bg-leaf-500/5'
            : 'border-ink-700 hover:border-ink-600 hover:bg-ink-800/40'
        )}
      >
        <div className="text-2xl text-ink-600">⬆</div>
        <p className="text-sm font-medium text-ink-200">
          Drop English, Hindi or Marathi video, audio or documents here
        </p>
        <p className="text-xs text-ink-400">
          MP4, MKV, MOV, MP3, WAV, M4A, PDF, DOCX, PPTX, XLSX, CSV · up to 2 GB each
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_EXTENSIONS.join(',')}
          className="hidden"
          onChange={(e) => {
            accept([...e.target.files])
            e.target.value = ''
          }}
        />
      </div>

      {rejected.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-red-300">
          {rejected.map((r) => (
            <li key={r}>✕ {r}</li>
          ))}
        </ul>
      )}

      {queue.length > 0 && (
        <ul className="mt-4 divide-y divide-ink-800 rounded-lg border border-ink-800">
          {queue.map((f, i) => (
            <li key={f.name + f.size} className="flex items-center gap-3 px-3 py-2 text-sm">
              <span className="truncate text-ink-200">{f.name}</span>
              <span className="ml-auto shrink-0 text-xs text-ink-400">{formatBytes(f.size)}</span>
              <button
                onClick={() => setQueue((q) => q.filter((_, j) => j !== i))}
                disabled={busy}
                className="shrink-0 text-ink-400 hover:text-red-300 disabled:opacity-30"
                aria-label={`Remove ${f.name}`}
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 flex flex-wrap items-end gap-4">
        <Field label="From">
          <Select value={sourceLang} onChange={(e) => setSourceLang(e.target.value)} disabled={busy}>
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label} ({l.native})
              </option>
            ))}
          </Select>
        </Field>

        <Field label="To">
          <Select value={targetLang} onChange={(e) => setTargetLang(e.target.value)} disabled={busy}>
            {targetLangs.map((l) => (
              <option key={l.code} value={l.code}>
                {l.label} ({l.native})
              </option>
            ))}
          </Select>
        </Field>

        <div className="ml-auto flex items-center gap-3">
          {queue.length > 0 && (
            <span className="text-xs text-ink-400">
              {queue.length} file{queue.length > 1 ? 's' : ''} · {formatBytes(totalBytes)}
            </span>
          )}
          <Button variant="primary" size="lg" disabled={!queue.length || busy} onClick={submit}>
            {busy ? 'Uploading…' : 'Start processing'}
          </Button>
        </div>
      </div>

      {busy && <ProgressBar value={uploadPct} className="mt-4" />}
    </Card>
  )
}

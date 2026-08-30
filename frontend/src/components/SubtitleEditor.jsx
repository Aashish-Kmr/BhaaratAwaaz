import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api/index.js'
import { Badge, Button, Card, EmptyState, cx } from './ui.jsx'
import { languageLabel } from '../lib/constants.js'
import {
  baseName,
  downloadText,
  formatShort,
  segmentWarnings,
  toBilingualTXT,
  toSRT,
  toTXT,
  toVTT,
} from '../lib/subtitles.js'

/**
 * Two-pane proof-reading view: media on the left, segment list on the right.
 * The list follows playback; clicking a segment seeks. Edits are local until
 * saved, so a proof-reader can work through a file and commit once.
 */
export default function SubtitleEditor({ job, onBack }) {
  const [segments, setSegments] = useState([])
  const [loading, setLoading] = useState(true)
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [savedAt, setSavedAt] = useState(null)
  const [activeId, setActiveId] = useState(null)
  const [follow, setFollow] = useState(true)
  const [showSource, setShowSource] = useState(true)
  const [error, setError] = useState(null)

  const mediaRef = useRef(null)
  const listRef = useRef(null)
  const rowRefs = useRef(new Map())

  const mediaUrl = useMemo(() => api.mediaUrl(job), [job])
  const isPlayable = job.kind === 'video' || job.kind === 'audio'

  useEffect(() => {
    let alive = true
    setLoading(true)
    api
      .getSegments(job.id)
      .then((segs) => {
        if (!alive) return
        setSegments(segs)
        setActiveId(segs[0]?.id ?? null)
        setError(null)
      })
      .catch((err) => alive && setError(err.message || 'Could not load segments'))
      .finally(() => alive && setLoading(false))
    return () => {
      alive = false
    }
  }, [job.id])

  // Warn before losing unsaved edits.
  useEffect(() => {
    if (!dirty) return
    const handler = (e) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [dirty])

  const onTimeUpdate = useCallback(() => {
    const t = mediaRef.current?.currentTime ?? 0
    const hit = segments.find((s) => t >= s.start && t < s.end)
    if (hit && hit.id !== activeId) {
      setActiveId(hit.id)
      if (follow) {
        rowRefs.current.get(hit.id)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
      }
    }
  }, [segments, activeId, follow])

  const seekTo = (seg) => {
    setActiveId(seg.id)
    if (mediaRef.current) {
      mediaRef.current.currentTime = seg.start + 0.01
      mediaRef.current.play?.().catch(() => {})
    }
  }

  const patchSegment = (id, patch) => {
    setSegments((prev) => prev.map((s) => (s.id === id ? { ...s, ...patch, edited: true } : s)))
    setDirty(true)
  }

  const splitSegment = (id) => {
    setSegments((prev) => {
      const i = prev.findIndex((s) => s.id === id)
      if (i < 0) return prev
      const s = prev[i]
      const mid = (s.start + s.end) / 2
      if (mid <= s.start || mid >= s.end) return prev
      const a = { ...s, end: mid, edited: true }
      const b = { ...s, id: `${s.id}_b${Date.now()}`, start: mid, target: '', edited: true }
      return [...prev.slice(0, i), a, b, ...prev.slice(i + 1)]
    })
    setDirty(true)
  }

  const mergeWithNext = (id) => {
    setSegments((prev) => {
      const i = prev.findIndex((s) => s.id === id)
      if (i < 0 || i === prev.length - 1) return prev
      const a = prev[i]
      const b = prev[i + 1]
      const merged = {
        ...a,
        end: b.end,
        source: [a.source, b.source].filter(Boolean).join(' '),
        target: [a.target, b.target].filter(Boolean).join(' '),
        edited: true,
      }
      return [...prev.slice(0, i), merged, ...prev.slice(i + 2)]
    })
    setDirty(true)
  }

  const save = async () => {
    setSaving(true)
    try {
      const res = await api.saveSegments(job.id, segments)
      setDirty(false)
      setSavedAt(res?.savedAt || new Date().toISOString())
      setError(null)
    } catch (err) {
      setError(err.message || 'Save failed')
    } finally {
      setSaving(false)
    }
  }

  const stem = baseName(job.filename)
  const lang = job.targetLang

  const exports = [
    { label: 'SRT', run: () => downloadText(`${stem}.${lang}.srt`, toSRT(segments)) },
    { label: 'VTT', run: () => downloadText(`${stem}.${lang}.vtt`, toVTT(segments)) },
    { label: 'Transcript', run: () => downloadText(`${stem}.${lang}.txt`, toTXT(segments)) },
    {
      label: 'Bilingual review',
      run: () =>
        downloadText(`${stem}.${job.sourceLang}-${lang}.review.txt`, toBilingualTXT(segments)),
    },
  ]

  const dubbedAudioUrl =
    (job.kind === 'audio' || job.kind === 'video') && job.dubbedAudioReady ? api.dubbedAudioUrl(job) : null

  // Burn-in is a video-only, on-demand render: it re-encodes the whole
  // file with ffmpeg, so it runs against the subtitles as saved right now
  // rather than automatically on the raw transcript.
  const canBurnIn = job.kind === 'video' && segments.length > 0
  const burnInStatus = job.burnInStatus ?? 'idle'
  const burnedInUrl = burnInStatus === 'ready' ? api.burnedInVideoUrl(job) : null

  const startBurnIn = async () => {
    setError(null)
    try {
      await api.startBurnIn(job.id)
    } catch (err) {
      setError(err.message || 'Could not start the burn-in render')
    }
  }

  const flagged = segments.filter((s) => segmentWarnings(s).length > 0).length

  return (
    <div className="flex h-full flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" onClick={onBack}>
          ← Queue
        </Button>
        <div className="min-w-0">
          <h1 className="truncate text-base font-semibold text-ink-200">{job.filename}</h1>
          <p className="text-xs text-ink-400">
            {languageLabel(job.sourceLang)} → {languageLabel(job.targetLang)} · {segments.length}{' '}
            segments
            {flagged > 0 && <span className="text-amber-300"> · {flagged} flagged</span>}
          </p>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-2">
          {savedAt && !dirty && <span className="text-xs text-leaf-300">Saved</span>}
          {dirty && <Badge tone="warn">Unsaved changes</Badge>}
          <Button variant="primary" onClick={save} disabled={!dirty || saving}>
            {saving ? 'Saving…' : 'Save edits'}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-400/25 bg-red-500/10 px-4 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]">
        {/* Left: media + exports */}
        <div className="flex flex-col gap-4">
          <Card className="overflow-hidden">
            {isPlayable && mediaUrl ? (
              job.kind === 'video' ? (
                <video
                  ref={mediaRef}
                  src={mediaUrl}
                  controls
                  onTimeUpdate={onTimeUpdate}
                  className="aspect-video w-full bg-black"
                />
              ) : (
                <div className="p-4">
                  <audio
                    ref={mediaRef}
                    src={mediaUrl}
                    controls
                    onTimeUpdate={onTimeUpdate}
                    className="w-full"
                  />
                </div>
              )
            ) : (
              <div className="flex aspect-video items-center justify-center bg-ink-950/60 px-6 text-center text-xs text-ink-400">
                {isPlayable
                  ? 'Media preview is unavailable for this demo job. Upload a file to play it here.'
                  : 'Document job — no media preview.'}
              </div>
            )}

            {isPlayable && mediaUrl && (
              <div className="border-t border-ink-700/70 px-4 py-2.5">
                <ActiveCaption segments={segments} activeId={activeId} />
              </div>
            )}
          </Card>

          <Card className="p-4">
            <h3 className="mb-3 text-xs font-semibold uppercase tracking-wide text-ink-400">
              Export
            </h3>
            <div className="flex flex-wrap gap-2">
              {exports.map((e) => (
                <Button key={e.label} size="sm" onClick={e.run} disabled={!segments.length}>
                  {e.label}
                </Button>
              ))}
              {dubbedAudioUrl && (
                <Button size="sm" onClick={() => window.open(dubbedAudioUrl, '_blank')}>
                  Dubbed audio (AI voice)
                </Button>
              )}
            </div>
            <p className="mt-3 text-xs text-ink-400">
              Files download to this machine. Burn-in and re-mux happen on the backend.
            </p>

            {canBurnIn && (
              <div className="mt-4 border-t border-ink-700/70 pt-3">
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-ink-400">
                  Burned-in video
                </h3>

                {burnedInUrl ? (
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => window.open(burnedInUrl, '_blank')}
                    >
                      Download MP4
                    </Button>
                    <Button size="sm" onClick={startBurnIn} disabled={dirty}>
                      Re-render
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={startBurnIn}
                    disabled={burnInStatus === 'rendering' || dirty}
                  >
                    {burnInStatus === 'rendering'
                      ? 'Rendering…'
                      : 'Render burned-in video'}
                  </Button>
                )}

                <p className="mt-2 text-xs text-ink-400">
                  {dirty
                    ? 'Save your edits first — the render uses the saved subtitles.'
                    : 'Re-encodes the video with these subtitles burned in. Slow on CPU.'}
                </p>

                {burnInStatus === 'failed' && job.burnInError && (
                  <p className="mt-2 rounded-md bg-red-500/10 px-3 py-1.5 text-xs text-red-300">
                    {job.burnInError}
                  </p>
                )}
              </div>
            )}
          </Card>

          <Card className="p-4">
            <label className="flex items-center gap-2 text-xs text-ink-200">
              <input
                type="checkbox"
                checked={follow}
                onChange={(e) => setFollow(e.target.checked)}
                className="accent-leaf-500"
              />
              Scroll list with playback
            </label>
            <label className="mt-2 flex items-center gap-2 text-xs text-ink-200">
              <input
                type="checkbox"
                checked={showSource}
                onChange={(e) => setShowSource(e.target.checked)}
                className="accent-leaf-500"
              />
              Show {languageLabel(job.sourceLang)} source
            </label>
          </Card>
        </div>

        {/* Right: segment list */}
        <Card className="flex min-h-0 flex-col overflow-hidden">
          <div className="flex items-center gap-2 border-b border-ink-700/70 px-4 py-2.5 text-xs text-ink-400">
            <span className="w-24">Time</span>
            {showSource && <span className="flex-1">{languageLabel(job.sourceLang)} (source)</span>}
            <span className="flex-1">{languageLabel(job.targetLang)} (editable)</span>
          </div>

          <div ref={listRef} className="scroll-thin min-h-0 flex-1 overflow-y-auto">
            {loading ? (
              <EmptyState title="Loading segments…" icon="◌" />
            ) : segments.length === 0 ? (
              <EmptyState
                title="No segments"
                hint="This job produced no subtitle segments. Retry it from the queue."
              />
            ) : (
              <ul className="divide-y divide-ink-800">
                {segments.map((seg, i) => (
                  <SegmentRow
                    key={seg.id}
                    seg={seg}
                    index={i}
                    active={seg.id === activeId}
                    showSource={showSource}
                    innerRef={(el) => {
                      if (el) rowRefs.current.set(seg.id, el)
                      else rowRefs.current.delete(seg.id)
                    }}
                    onSeek={() => seekTo(seg)}
                    onChange={(patch) => patchSegment(seg.id, patch)}
                    onSplit={() => splitSegment(seg.id)}
                    onMerge={() => mergeWithNext(seg.id)}
                    canMerge={i < segments.length - 1}
                  />
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>
    </div>
  )
}

function ActiveCaption({ segments, activeId }) {
  const seg = segments.find((s) => s.id === activeId)
  if (!seg) return <p className="text-xs text-ink-400">—</p>
  return (
    <div className="deva">
      <p className="text-sm text-ink-200">{seg.target || '…'}</p>
      <p className="mt-0.5 text-xs text-ink-400">{seg.source}</p>
    </div>
  )
}

function SegmentRow({
  seg,
  index,
  active,
  showSource,
  innerRef,
  onSeek,
  onChange,
  onSplit,
  onMerge,
  canMerge,
}) {
  const warnings = segmentWarnings(seg)
  const low = seg.confidence != null && seg.confidence < 0.75

  return (
    <li
      ref={innerRef}
      className={cx(
        'flex gap-3 px-4 py-3 transition-colors',
        active ? 'bg-leaf-500/10' : 'hover:bg-ink-800/40'
      )}
    >
      <div className="w-24 shrink-0">
        <button
          onClick={onSeek}
          className="text-left text-xs tabular-nums text-ink-400 hover:text-leaf-300"
          title="Jump to this segment"
        >
          {formatShort(seg.start)}
          <br />
          {formatShort(seg.end)}
        </button>
        <div className="mt-1 text-[10px] text-ink-600">#{index + 1}</div>
      </div>

      {showSource && (
        <p className="deva flex-1 text-sm text-ink-400">{seg.source}</p>
      )}

      <div className="flex-1">
        <textarea
          value={seg.target}
          onChange={(e) => onChange({ target: e.target.value })}
          onFocus={onSeek}
          rows={Math.max(2, Math.ceil((seg.target?.length || 0) / 46))}
          className={cx(
            'deva w-full resize-y rounded-lg border bg-ink-800/70 px-3 py-2 text-sm text-ink-200 focus:outline-none',
            warnings.length ? 'border-amber-400/40' : 'border-ink-700',
            'focus:border-leaf-500'
          )}
          placeholder="Translation…"
        />

        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[11px] text-ink-400">
          <span>{(seg.target || '').length} chars</span>
          {low && <span className="text-amber-300">low confidence</span>}
          {seg.edited && <span className="text-leaf-300">edited</span>}
          {warnings.map((w) => (
            <span key={w} className="text-amber-300">
              ⚠ {w}
            </span>
          ))}
          <span className="ml-auto flex gap-1">
            <button onClick={onSplit} className="hover:text-ink-200" title="Split at midpoint">
              split
            </button>
            {canMerge && (
              <button onClick={onMerge} className="hover:text-ink-200" title="Merge with next">
                merge
              </button>
            )}
          </span>
        </div>
      </div>
    </li>
  )
}

import React from 'react'

export function cx(...parts) {
  return parts.filter(Boolean).join(' ')
}

export function Button({ variant = 'default', size = 'md', className, ...props }) {
  const base =
    'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus-visible:ring-2 focus-visible:ring-leaf-300/70'
  const variants = {
    default: 'bg-ink-700 text-ink-200 hover:bg-ink-600',
    primary: 'bg-leaf-500 text-ink-950 hover:bg-leaf-300',
    ghost: 'bg-transparent text-ink-400 hover:text-ink-200 hover:bg-ink-800',
    danger: 'bg-transparent text-red-300 hover:bg-red-500/10',
  }
  const sizes = {
    sm: 'px-2.5 py-1 text-xs',
    md: 'px-3.5 py-2 text-sm',
    lg: 'px-5 py-2.5 text-sm',
  }
  return <button className={cx(base, variants[variant], sizes[size], className)} {...props} />
}

export function Card({ className, ...props }) {
  return (
    <div
      className={cx('rounded-xl border border-ink-700/70 bg-ink-900/60 backdrop-blur-sm', className)}
      {...props}
    />
  )
}

const TONES = {
  idle: 'bg-ink-700 text-ink-200',
  busy: 'bg-sky-500/15 text-sky-300 border border-sky-400/25',
  good: 'bg-leaf-500/15 text-leaf-300 border border-leaf-500/30',
  bad: 'bg-red-500/15 text-red-300 border border-red-400/30',
  warn: 'bg-amber-500/15 text-amber-300 border border-amber-400/30',
}

export function Badge({ tone = 'idle', children, className }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap',
        TONES[tone],
        className
      )}
    >
      {tone === 'busy' && <span className="h-1.5 w-1.5 rounded-full bg-sky-300 pulse-soft" />}
      {children}
    </span>
  )
}

export function ProgressBar({ value = 0, tone = 'busy', className }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100)
  const fill = tone === 'good' ? 'bg-leaf-500' : tone === 'bad' ? 'bg-red-400' : 'bg-sky-400'
  return (
    <div className={cx('h-1.5 w-full overflow-hidden rounded-full bg-ink-800', className)}>
      <div
        className={cx('h-full rounded-full transition-[width] duration-500 ease-out', fill)}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function EmptyState({ title, hint, icon = '◇', action }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
      <div className="text-3xl text-ink-600">{icon}</div>
      <p className="text-sm font-medium text-ink-200">{title}</p>
      {hint && <p className="max-w-sm text-xs text-ink-400">{hint}</p>}
      {action}
    </div>
  )
}

export function Field({ label, children, hint }) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-xs font-medium uppercase tracking-wide text-ink-400">{label}</span>
      {children}
      {hint && <span className="text-xs text-ink-400">{hint}</span>}
    </label>
  )
}

export function Checkbox({ label, checked, onChange, disabled, hint, className }) {
  return (
    <label className={cx('flex items-center gap-2 text-sm text-ink-200', disabled && 'opacity-40', className)}>
      <input
        type="checkbox"
        checked={checked}
        onChange={onChange}
        disabled={disabled}
        className="accent-leaf-500"
      />
      {label}
      {hint && <span className="text-xs text-ink-400">{hint}</span>}
    </label>
  )
}

export function Select({ className, ...props }) {
  return (
    <select
      className={cx(
        'rounded-lg border border-ink-700 bg-ink-800 px-3 py-2 text-sm text-ink-200 focus:border-leaf-500 focus:outline-none',
        className
      )}
      {...props}
    />
  )
}

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return '—'
  const units = ['B', 'KB', 'MB', 'GB']
  let n = bytes
  let i = 0
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024
    i++
  }
  return `${n < 10 && i > 0 ? n.toFixed(1) : Math.round(n)} ${units[i]}`
}

export function formatDuration(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return '—'
  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m`
  return `${m}m ${String(s).padStart(2, '0')}s`
}

/** Wall-clock time a job has spent processing: createdAt to finishedAt, or to now if still running. */
export function elapsedLabel(job) {
  if (!job.createdAt) return null
  const start = new Date(job.createdAt).getTime()
  const end = job.finishedAt ? new Date(job.finishedAt).getTime() : Date.now()
  const sec = Math.max(0, (end - start) / 1000)

  const m = Math.floor(sec / 60)
  const s = Math.round(sec % 60)
  if (m >= 60) return `${Math.floor(m / 60)}h ${m % 60}m elapsed`
  if (m > 0) return `${m}m ${String(s).padStart(2, '0')}s elapsed`
  return `${s}s elapsed`
}

export function relativeTime(iso) {
  if (!iso) return '—'
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return `${Math.floor(diff / 60)} min ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)} hr ago`
  return `${Math.floor(diff / 86400)} d ago`
}

export const KindIcon = ({ kind, className }) => {
  const map = { video: '▶', audio: '♪', document: '▤', unknown: '?' }
  return (
    <span
      className={cx(
        'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-ink-800 text-sm text-ink-400',
        className
      )}
      aria-hidden="true"
    >
      {map[kind] ?? map.unknown}
    </span>
  )
}

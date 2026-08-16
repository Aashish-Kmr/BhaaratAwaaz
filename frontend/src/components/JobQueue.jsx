import React, { useMemo, useState } from 'react'
import {
  Badge,
  Button,
  Card,
  EmptyState,
  KindIcon,
  ProgressBar,
  cx,
  formatBytes,
  formatDuration,
  relativeTime,
} from './ui.jsx'
import { JOB_STATUS, isRunning, isTerminal, languageLabel } from '../lib/constants.js'
import { api } from '../api/index.js'

const FILTERS = [
  { id: 'all', label: 'All' },
  { id: 'active', label: 'In progress' },
  { id: 'done', label: 'Ready' },
  { id: 'failed', label: 'Needs attention' },
]

function matches(job, filter) {
  if (filter === 'all') return true
  if (filter === 'active') return !isTerminal(job.status)
  if (filter === 'done') return job.status === 'done'
  return job.status === 'failed'
}

export default function JobQueue({ jobs, loading, error, onOpen, onCancel, onRetry, onDelete }) {
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')

  const visible = useMemo(
    () =>
      jobs.filter(
        (j) => matches(j, filter) && j.filename.toLowerCase().includes(query.trim().toLowerCase())
      ),
    [jobs, filter, query]
  )

  const counts = useMemo(
    () => ({
      all: jobs.length,
      active: jobs.filter((j) => !isTerminal(j.status)).length,
      done: jobs.filter((j) => j.status === 'done').length,
      failed: jobs.filter((j) => j.status === 'failed').length,
    }),
    [jobs]
  )

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-ink-700/70 px-5 py-3">
        <h2 className="text-sm font-semibold text-ink-200">Job queue</h2>
        <div className="flex gap-1">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              onClick={() => setFilter(f.id)}
              className={cx(
                'rounded-md px-2.5 py-1 text-xs transition-colors',
                filter === f.id ? 'bg-ink-700 text-ink-200' : 'text-ink-400 hover:text-ink-200'
              )}
            >
              {f.label}
              <span className="ml-1.5 text-ink-400">{counts[f.id]}</span>
            </button>
          ))}
        </div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search files…"
          className="ml-auto w-44 rounded-lg border border-ink-700 bg-ink-800 px-3 py-1.5 text-xs text-ink-200 placeholder:text-ink-600 focus:border-leaf-500 focus:outline-none"
        />
      </div>

      {error && (
        <div className="border-b border-red-400/20 bg-red-500/10 px-5 py-2 text-xs text-red-300">
          {error}
        </div>
      )}

      {loading && jobs.length === 0 ? (
        <EmptyState title="Loading jobs…" icon="◌" />
      ) : visible.length === 0 ? (
        <EmptyState
          title={jobs.length === 0 ? 'No jobs yet' : 'Nothing matches this filter'}
          hint={
            jobs.length === 0
              ? 'Drop a Marathi recording above to create the first job.'
              : 'Try a different filter or clear the search.'
          }
        />
      ) : (
        <ul className="divide-y divide-ink-800">
          {visible.map((job) => (
            <JobRow
              key={job.id}
              job={job}
              onOpen={onOpen}
              onCancel={onCancel}
              onRetry={onRetry}
              onDelete={onDelete}
            />
          ))}
        </ul>
      )}
    </Card>
  )
}

function JobRow({ job, onOpen, onCancel, onRetry, onDelete }) {
  const meta = JOB_STATUS[job.status] ?? { label: job.status, tone: 'idle' }
  const running = isRunning(job.status)

  return (
    <li className="group px-5 py-3.5 transition-colors hover:bg-ink-800/40">
      <div className="flex items-center gap-3">
        <KindIcon kind={job.kind} />

        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium text-ink-200">{job.filename}</p>
            <Badge tone={meta.tone}>{running ? job.stage || meta.label : meta.label}</Badge>
          </div>
          <p className="mt-0.5 truncate text-xs text-ink-400">
            {languageLabel(job.sourceLang)} → {languageLabel(job.targetLang)} ·{' '}
            {formatBytes(job.bytes)}
            {job.durationSec ? ` · ${formatDuration(job.durationSec)}` : ''} ·{' '}
            {relativeTime(job.createdAt)}
            {job.status === 'done' && job.segmentCount
              ? ` · ${job.segmentCount} segments`
              : ''}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-1.5">
          {job.status === 'done' && job.kind === 'document' && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => window.open(api.downloadUrl(job), '_blank')}
              disabled={!api.downloadUrl(job)}
            >
              Download
            </Button>
          )}
          {job.status === 'done' && job.kind !== 'document' && (
            <Button variant="primary" size="sm" onClick={() => onOpen(job)}>
              Open editor
            </Button>
          )}
          {job.status === 'failed' && (
            <Button size="sm" onClick={() => onRetry(job.id)}>
              Retry
            </Button>
          )}
          {!isTerminal(job.status) && (
            <Button variant="ghost" size="sm" onClick={() => onCancel(job.id)}>
              Cancel
            </Button>
          )}
          {isTerminal(job.status) && (
            <Button
              variant="danger"
              size="sm"
              className="opacity-0 group-hover:opacity-100 focus:opacity-100"
              onClick={() => onDelete(job.id)}
              aria-label={`Delete ${job.filename}`}
            >
              Delete
            </Button>
          )}
        </div>
      </div>

      {!isTerminal(job.status) && (
        <div className="mt-2.5 flex items-center gap-3">
          <ProgressBar value={job.progress} className="flex-1" />
          <span className="w-9 text-right text-xs tabular-nums text-ink-400">
            {Math.round((job.progress || 0) * 100)}%
          </span>
        </div>
      )}

      {job.status === 'failed' && job.error && (
        <p className="mt-2 rounded-md bg-red-500/10 px-3 py-1.5 text-xs text-red-300">{job.error}</p>
      )}
    </li>
  )
}

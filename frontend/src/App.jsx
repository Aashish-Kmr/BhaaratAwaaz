import React, { useCallback, useEffect, useState } from 'react'
import { api, USING_MOCK } from './api/index.js'
import { useJobs } from './hooks/useJobs.js'
import UploadPanel from './components/UploadPanel.jsx'
import JobQueue from './components/JobQueue.jsx'
import SubtitleEditor from './components/SubtitleEditor.jsx'
import { Badge, Card, Checkbox } from './components/ui.jsx'

export default function App() {
  const { jobs, loading, error, createJob, cancelJob, retryJob, deleteJob } = useJobs()
  const [openJobId, setOpenJobId] = useState(null)
  const [status, setStatus] = useState(null)

  const refreshStatus = useCallback(() => {
    return api
      .getStatus()
      .then((s) => setStatus(s))
      .catch(() => setStatus({ online: false }))
  }, [])

  useEffect(() => {
    let alive = true
    const load = () => api.getStatus().then((s) => alive && setStatus(s)).catch(() => alive && setStatus({ online: false }))
    load()
    const t = setInterval(load, 20000)
    return () => {
      alive = false
      clearInterval(t)
    }
  }, [])

  const openJob = jobs.find((j) => j.id === openJobId) || null

  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-10 border-b border-ink-700/70 bg-ink-950/85 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-3 px-6 py-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-leaf-500 text-sm font-bold text-ink-950">
            भा
          </div>
          <div>
            <h1 className="text-sm font-semibold text-ink-200">BAIF Bhasha</h1>
            <p className="text-[11px] text-ink-400">
              English · Hindi · Marathi, any pair · runs entirely on this machine
            </p>
          </div>

          <div className="ml-auto flex items-center gap-2">
            {USING_MOCK && <Badge tone="warn">Mock data</Badge>}
            <Badge tone={status?.online === false ? 'bad' : 'good'}>
              {status?.online === false ? 'Backend unreachable' : 'Offline mode · models loaded'}
            </Badge>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-6">
        {openJob ? (
          <div className="h-[calc(100vh-9rem)]">
            <SubtitleEditor job={openJob} onBack={() => setOpenJobId(null)} />
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            <UploadPanel onSubmit={createJob} />
            <JobQueue
              jobs={jobs}
              loading={loading}
              error={error}
              onOpen={(job) => setOpenJobId(job.id)}
              onCancel={cancelJob}
              onRetry={retryJob}
              onDelete={deleteJob}
            />
            <MachineStrip status={status} onRefresh={refreshStatus} />
          </div>
        )}
      </main>
    </div>
  )
}

function MachineStrip({ status, onRefresh }) {
  const [switching, setSwitching] = useState(false)

  if (!status || status.online === false) return null

  const toggleGpu = async (e) => {
    setSwitching(true)
    try {
      await api.setDevice(e.target.checked)
      await onRefresh()
    } finally {
      setSwitching(false)
    }
  }

  return (
    <Card className="flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3 text-xs text-ink-400">
      <span className="font-medium text-ink-200">This machine</span>
      {status.models?.map((m) => (
        <span key={m.name}>
          <span className={m.loaded ? 'text-leaf-300' : 'text-ink-600'}>●</span> {m.name}
          {m.sizeMb ? ` · ${m.sizeMb} MB` : ''}
        </span>
      ))}
      {status.queueLength != null && <span>Queue: {status.queueLength}</span>}
      {status.ramTotalGb && <span>RAM: {status.ramTotalGb} GB</span>}
      {status.diskFreeGb && <span>Disk free: {status.diskFreeGb} GB</span>}
      <Checkbox
        label={switching ? 'Switching…' : 'Process on GPU'}
        hint={
          !status.gpuAvailable
            ? '(no GPU detected)'
            : '(transcription + translation only — dubbing always runs on CPU)'
        }
        checked={!!status.gpuEnabled}
        onChange={toggleGpu}
        disabled={!status.gpuAvailable || switching}
      />
    </Card>
  )
}

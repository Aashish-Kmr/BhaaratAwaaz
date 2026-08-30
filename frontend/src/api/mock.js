/**
 * In-memory fake backend. Mirrors http.js exactly so the UI cannot tell them
 * apart. It simulates the pipeline a local Whisper + NMT setup would run on a
 * 16 GB i5: slow, single-worker, one job at a time.
 *
 * Nothing here should be imported outside api/. Delete once the real backend
 * is ready.
 */
import { kindOf, isRunning } from '../lib/constants.js'
import { SAMPLE_SEGMENTS } from './sampleContent.js'

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))
const uid = () => 'job_' + Math.random().toString(36).slice(2, 10)

// --- store ------------------------------------------------------------
const jobs = new Map() // id -> job
const segmentsByJob = new Map() // id -> segments[]
const objectUrls = new Map() // id -> blob url for local preview

function seed() {
  const now = Date.now()
  const finished = {
    id: 'job_demo01',
    filename: 'sendriya-sheti-part1.mp4',
    kind: 'video',
    bytes: 84_233_216,
    durationSec: 52,
    sourceLang: 'mr',
    targetLang: 'hi',
    status: 'done',
    progress: 1,
    stage: 'Completed',
    createdAt: new Date(now - 1000 * 60 * 42).toISOString(),
    finishedAt: new Date(now - 1000 * 60 * 31).toISOString(),
    error: null,
    segmentCount: SAMPLE_SEGMENTS.length,
  }
  jobs.set(finished.id, finished)
  segmentsByJob.set(
    finished.id,
    SAMPLE_SEGMENTS.map((s, i) => ({
      id: `${finished.id}_s${i}`,
      start: s.start,
      end: s.end,
      source: s.source,
      target: s.hi,
      confidence: 0.72 + ((i * 7) % 25) / 100,
      edited: false,
    }))
  )

  const failed = {
    id: 'job_demo02',
    filename: 'pashupalan-radio-talk.mp3',
    kind: 'audio',
    bytes: 12_884_901,
    durationSec: 640,
    sourceLang: 'mr',
    targetLang: 'en',
    status: 'failed',
    progress: 0.34,
    stage: 'Transcribing',
    createdAt: new Date(now - 1000 * 60 * 15).toISOString(),
    finishedAt: new Date(now - 1000 * 60 * 12).toISOString(),
    error: 'Audio stream unreadable at 03:12 — file may be truncated.',
    segmentCount: 0,
  }
  jobs.set(failed.id, failed)
  segmentsByJob.set(failed.id, [])
}
seed()

// --- pipeline simulation ---------------------------------------------
// One worker, because the target machine can only run one model at a time.
let workerBusy = false

const STAGES = [
  { status: 'extracting', label: 'Extracting audio', share: 0.12 },
  { status: 'transcribing', label: 'Transcribing Marathi', share: 0.58 },
  { status: 'translating', label: 'Translating', share: 0.30 },
]

async function runPipeline(id) {
  // Wait our turn in the single-worker queue.
  while (workerBusy) {
    if (jobs.get(id)?.status === 'cancelled') return
    await sleep(300)
  }
  workerBusy = true
  try {
    const job = jobs.get(id)
    if (!job || job.status === 'cancelled') return

    const isDoc = job.kind === 'document'
    const stages = isDoc
      ? [
          { status: 'extracting', label: 'Extracting text', share: 0.25 },
          { status: 'translating', label: 'Translating', share: 0.75 },
        ]
      : STAGES

    let base = 0
    for (const stage of stages) {
      const steps = 14
      for (let i = 1; i <= steps; i++) {
        const current = jobs.get(id)
        if (!current || current.status === 'cancelled') return
        await sleep(220)
        update(id, {
          status: stage.status,
          stage: stage.label,
          progress: Math.min(0.999, base + (stage.share * i) / steps),
        })
      }
      base += stage.share
    }

    // Materialise output segments.
    const job2 = jobs.get(id)
    const target = job2.targetLang === 'en' ? 'en' : 'hi'
    const segs = SAMPLE_SEGMENTS.map((s, i) => ({
      id: `${id}_s${i}`,
      start: s.start,
      end: s.end,
      source: s.source,
      target: s[target],
      confidence: 0.68 + ((i * 11) % 30) / 100,
      edited: false,
    }))
    segmentsByJob.set(id, segs)
    update(id, {
      segmentCount: segs.length,
      durationSec: segs[segs.length - 1]?.end ?? 0,
    })

    // Dubbing (if requested) is part of processing, not a background
    // afterthought -- the job only reaches "done" once it finishes, same as
    // the real backend.
    if (job2.includeDubbing && (job2.kind === 'video' || job2.kind === 'audio')) {
      update(id, { status: 'dubbing', stage: 'Dubbing audio', progress: 0.97 })
      await sleep(1500)
      if (jobs.get(id)?.status === 'cancelled') return
      update(id, { dubbedAudioReady: true })
    }

    update(id, {
      status: 'done',
      stage: 'Completed',
      progress: 1,
      finishedAt: new Date().toISOString(),
    })
  } finally {
    workerBusy = false
  }
}

function update(id, patch) {
  const job = jobs.get(id)
  if (!job) return
  jobs.set(id, { ...job, ...patch })
}

// --- public interface -------------------------------------------------
export const mockApi = {
  async getStatus() {
    await sleep(120)
    return {
      online: true,
      offlineMode: true,
      models: [
        { name: 'IndicTrans2 (documents)', task: 'translation', loaded: true, sizeMb: 812 },
        { name: 'faster-whisper medium (audio)', task: 'asr', loaded: true, sizeMb: 1530 },
        { name: 'IndicTrans2 (audio)', task: 'translation', loaded: true, sizeMb: 812 },
        { name: 'Indic Parler-TTS (dubbing)', task: 'tts', loaded: false, sizeMb: 3600 },
        { name: 'faster-whisper medium (video)', task: 'asr', loaded: true, sizeMb: 1530 },
        { name: 'NLLB-200 distilled 600M (video)', task: 'translation', loaded: false, sizeMb: 2400 },
      ],
      queueLength: [...jobs.values()].filter((j) => isRunning(j.status) || j.status === 'queued').length,
      diskFreeGb: 41.6,
      cpuOnly: true,
      mock: true,
    }
  },

  async listJobs() {
    await sleep(80)
    return [...jobs.values()].sort((a, b) => b.createdAt.localeCompare(a.createdAt))
  },

  async getJob(id) {
    await sleep(40)
    const job = jobs.get(id)
    if (!job) throw new Error('Job not found')
    return job
  },

  async createJob(file, { sourceLang = 'mr', targetLang = 'hi', includeDubbing = false, onProgress } = {}) {
    // Fake the upload byte progress.
    for (let p = 0; p <= 1.0001; p += 0.2) {
      onProgress?.(Math.min(1, p))
      await sleep(90)
    }

    const id = uid()
    const job = {
      id,
      filename: file.name,
      kind: kindOf(file.name),
      bytes: file.size,
      durationSec: null,
      sourceLang,
      targetLang,
      includeDubbing,
      dubbedAudioReady: false,
      burnInStatus: 'idle',
      burnInError: null,
      status: 'queued',
      progress: 0,
      stage: 'Waiting for worker',
      createdAt: new Date().toISOString(),
      finishedAt: null,
      error: null,
      segmentCount: 0,
    }
    jobs.set(id, job)
    segmentsByJob.set(id, [])

    // Keep a local blob URL so the editor can actually play the file the
    // user just picked, even with no backend running.
    if (job.kind === 'video' || job.kind === 'audio') {
      objectUrls.set(id, URL.createObjectURL(file))
    }

    runPipeline(id)
    return job
  },

  async cancelJob(id) {
    update(id, { status: 'cancelled', stage: 'Cancelled', finishedAt: new Date().toISOString() })
    return jobs.get(id)
  },

  async retryJob(id) {
    update(id, { status: 'queued', stage: 'Waiting for worker', progress: 0, error: null, finishedAt: null })
    runPipeline(id)
    return jobs.get(id)
  },

  async deleteJob(id) {
    const url = objectUrls.get(id)
    if (url) URL.revokeObjectURL(url)
    objectUrls.delete(id)
    jobs.delete(id)
    segmentsByJob.delete(id)
    return null
  },

  async getSegments(id) {
    await sleep(120)
    return (segmentsByJob.get(id) ?? []).map((s) => ({ ...s }))
  },

  async saveSegments(id, segments) {
    await sleep(200)
    segmentsByJob.set(id, segments.map((s) => ({ ...s })))
    update(id, { segmentCount: segments.length })
    return { saved: segments.length, savedAt: new Date().toISOString() }
  },

  mediaUrl(job) {
    // Real uploads get a blob URL; the seeded demo job has no bytes at all.
    return objectUrls.get(job.id) ?? null
  },

  // No real backend behind the mock, so there's nothing to download —
  // callers treat a falsy URL as "not available" and hide the action.
  downloadUrl() {
    return null
  },

  // No real TTS behind the mock -- stand in with the original upload's blob
  // URL so the "Dubbed audio" action is exercisable once a job opts in and
  // finishes, same as it would be against the real backend.
  dubbedAudioUrl(job) {
    if (!job?.dubbedAudioReady) return null
    return objectUrls.get(job.id) ?? null
  },

  // No ffmpeg behind the mock, so the render is simulated: it moves
  // through the same idle -> rendering -> ready states the real backend
  // reports, and hands back the original upload to stand in for the
  // burned-in file.
  async startBurnIn(id) {
    update(id, { burnInStatus: 'rendering', burnInError: null })
    sleep(2500).then(() => {
      if (jobs.has(id)) update(id, { burnInStatus: 'ready' })
    })
    return jobs.get(id)
  },

  burnedInVideoUrl(job) {
    if (job?.burnInStatus !== 'ready') return null
    return objectUrls.get(job.id) ?? null
  },
}

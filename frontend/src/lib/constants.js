export const LANGUAGES = [
  { code: 'mr', label: 'Marathi', native: 'मराठी' },
  { code: 'hi', label: 'Hindi', native: 'हिन्दी' },
  { code: 'en', label: 'English', native: 'English' },
]

export const languageLabel = (code) =>
  LANGUAGES.find((l) => l.code === code)?.label ?? code

/**
 * Job lifecycle. The backend must report exactly one of these in `status`.
 * queued -> transcribing -> translating -> [dubbing] -> done
 * dubbing only occurs for audio/video jobs with includeDubbing set; a job
 * only reaches "done" after dubbing has actually finished.
 * any state -> failed | cancelled
 */
export const JOB_STATUS = {
  queued: { label: 'Queued', tone: 'idle' },
  extracting: { label: 'Extracting audio', tone: 'busy' },
  transcribing: { label: 'Transcribing', tone: 'busy' },
  translating: { label: 'Translating', tone: 'busy' },
  dubbing: { label: 'Dubbing audio', tone: 'busy' },
  done: { label: 'Ready', tone: 'good' },
  failed: { label: 'Failed', tone: 'bad' },
  cancelled: { label: 'Cancelled', tone: 'idle' },
}

export const isTerminal = (status) =>
  status === 'done' || status === 'failed' || status === 'cancelled'

export const isRunning = (status) =>
  status === 'extracting' ||
  status === 'transcribing' ||
  status === 'translating' ||
  status === 'dubbing'

export const KIND_BY_EXT = {
  mp4: 'video', mkv: 'video', mov: 'video', avi: 'video', webm: 'video',
  mp3: 'audio', wav: 'audio', m4a: 'audio', aac: 'audio', ogg: 'audio', flac: 'audio',
  pdf: 'document', docx: 'document', pptx: 'document', xlsx: 'document', csv: 'document',
}

export function kindOf(filename = '') {
  const ext = filename.split('.').pop()?.toLowerCase()
  return KIND_BY_EXT[ext] ?? 'unknown'
}

export const ACCEPTED_EXTENSIONS = Object.keys(KIND_BY_EXT).map((e) => '.' + e)

// Rough guard so a hackathon demo does not choke the 16 GB box.
export const MAX_FILE_BYTES = 2 * 1024 * 1024 * 1024 // 2 GB

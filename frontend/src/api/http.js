/**
 * Real backend implementation. Talks to the local FastAPI/Flask server over
 * plain REST + polling. Deliberately no websockets — polling survives a
 * restarted backend on a single-machine deployment.
 *
 * See API_CONTRACT.md for the exact payloads.
 */

const BASE = import.meta.env.VITE_API_BASE || '/api'

class ApiError extends Error {
  constructor(message, status, body) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

async function request(path, { method = 'GET', body, signal, headers } = {}) {
  const isForm = body instanceof FormData
  const res = await fetch(`${BASE}${path}`, {
    method,
    signal,
    headers: {
      ...(isForm || body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
    body: isForm ? body : body === undefined ? undefined : JSON.stringify(body),
  })

  if (!res.ok) {
    let detail = null
    try {
      detail = await res.json()
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(detail?.message || `${method} ${path} failed (${res.status})`, res.status, detail)
  }
  if (res.status === 204) return null
  return res.json()
}

export const httpApi = {
  async getStatus() {
    return request('/status')
  },

  async listJobs() {
    const data = await request('/jobs')
    return data.jobs ?? data
  },

  async getJob(id) {
    return request(`/jobs/${encodeURIComponent(id)}`)
  },

  /**
   * @param {File} file
   * @param {{sourceLang:string, targetLang:string, includeDubbing?:boolean, onProgress?:(fraction:number)=>void}} opts
   */
  createJob(file, { sourceLang, targetLang, includeDubbing, onProgress } = {}) {
    // XHR rather than fetch: it is the only way to get upload progress,
    // which matters for 500 MB field recordings on a slow local disk.
    return new Promise((resolve, reject) => {
      const form = new FormData()
      form.append('file', file, file.name)
      form.append('source_lang', sourceLang)
      form.append('target_lang', targetLang)
      form.append('include_dubbing', includeDubbing ? 'true' : 'false')

      const xhr = new XMLHttpRequest()
      xhr.open('POST', `${BASE}/jobs`)
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total)
      }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText))
          } catch (err) {
            reject(new ApiError('Malformed job response', xhr.status, xhr.responseText))
          }
        } else {
          reject(new ApiError(`Upload failed (${xhr.status})`, xhr.status, xhr.responseText))
        }
      }
      xhr.onerror = () => reject(new ApiError('Network error during upload', 0, null))
      xhr.send(form)
    })
  },

  async cancelJob(id) {
    return request(`/jobs/${encodeURIComponent(id)}/cancel`, { method: 'POST' })
  },

  async retryJob(id) {
    return request(`/jobs/${encodeURIComponent(id)}/retry`, { method: 'POST' })
  },

  async deleteJob(id) {
    return request(`/jobs/${encodeURIComponent(id)}`, { method: 'DELETE' })
  },

  async getSegments(id) {
    const data = await request(`/jobs/${encodeURIComponent(id)}/segments`)
    return data.segments ?? data
  },

  async saveSegments(id, segments) {
    return request(`/jobs/${encodeURIComponent(id)}/segments`, {
      method: 'PUT',
      body: { segments },
    })
  },

  /** Backend streams the original media with range support. */
  mediaUrl(job) {
    return `${BASE}/jobs/${encodeURIComponent(job.id)}/media`
  },

  /** Document jobs only: the translated file, formatting preserved. */
  downloadUrl(job) {
    return `${BASE}/jobs/${encodeURIComponent(job.id)}/download`
  },

  /** Audio and video jobs: bonus AI-voiced dubbed track, once ready. */
  dubbedAudioUrl(job) {
    return `${BASE}/jobs/${encodeURIComponent(job.id)}/dubbed-audio`
  },

  /**
   * Video jobs: kick off the subtitle burn-in render. Runs against the
   * subtitles saved right now, so save edits first. Poll the job's
   * burnInStatus for progress.
   */
  async startBurnIn(id) {
    return request(`/jobs/${encodeURIComponent(id)}/burn-in`, { method: 'POST' })
  },

  /** Video jobs: the burned-in MP4, once burnInStatus is "ready". */
  burnedInVideoUrl(job) {
    return `${BASE}/jobs/${encodeURIComponent(job.id)}/burned-in-video`
  },
}

export { ApiError }

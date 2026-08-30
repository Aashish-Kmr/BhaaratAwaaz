import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api/index.js'
import { isTerminal } from '../lib/constants.js'

/**
 * Owns the job list. Polls while anything is still running, backs off to a
 * slow heartbeat when everything is terminal so an idle tab does not keep the
 * single-worker machine busy answering HTTP.
 */
export function useJobs() {
  const [jobs, setJobs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const timer = useRef(null)
  const mounted = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const next = await api.listJobs()
      if (!mounted.current) return next
      setJobs(next)
      setError(null)
      return next
    } catch (err) {
      if (mounted.current) setError(err.message || 'Could not reach the backend')
      return null
    } finally {
      if (mounted.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    mounted.current = true

    const tick = async () => {
      const next = await refresh()
      if (!mounted.current) return
      // A burn-in render leaves the job itself "done", so poll on that
      // too -- otherwise the render would appear frozen until the slow
      // idle heartbeat came round.
      const busy = (next ?? []).some(
        (j) => !isTerminal(j.status) || j.burnInStatus === 'rendering'
      )
      timer.current = setTimeout(tick, busy ? 1000 : 8000)
    }
    tick()

    return () => {
      mounted.current = false
      clearTimeout(timer.current)
    }
  }, [refresh])

  const createJob = useCallback(
    async (file, opts) => {
      const job = await api.createJob(file, opts)
      await refresh()
      return job
    },
    [refresh]
  )

  const act = useCallback(
    async (fn, id) => {
      await fn(id)
      await refresh()
    },
    [refresh]
  )

  return {
    jobs,
    loading,
    error,
    refresh,
    createJob,
    cancelJob: (id) => act(api.cancelJob, id),
    retryJob: (id) => act(api.retryJob, id),
    deleteJob: (id) => act(api.deleteJob, id),
  }
}

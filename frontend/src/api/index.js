/**
 * Single seam between the UI and the backend.
 *
 * The whole app imports `api` from here and nothing else. Flip one env var
 * to swap the in-memory fake for the real local server:
 *
 *   VITE_USE_MOCK=false npm run dev
 *
 * Both implementations satisfy the same interface, documented in
 * API_CONTRACT.md at the repo root.
 */
import { mockApi } from './mock.js'
import { httpApi } from './http.js'

const flag = import.meta.env.VITE_USE_MOCK
// Default to the mock so the frontend runs with no backend present.
export const USING_MOCK = flag === undefined ? true : String(flag) !== 'false'

export const api = USING_MOCK ? mockApi : httpApi

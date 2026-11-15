import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// The engine can be briefly unreachable (restart, laptop waking up): retry network failures quietly for ~6 s
// before any panel shows "Failed to fetch". Only network errors are retried; HTTP errors pass through untouched.
const _fetch = window.fetch.bind(window)
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  for (let i = 0; ; i++) {
    try {
      return await _fetch(input, init)
    } catch (e) {
      if (i >= 4 || (init?.signal && init.signal.aborted)) throw e
      await new Promise((r) => setTimeout(r, 600 * (i + 1)))
    }
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

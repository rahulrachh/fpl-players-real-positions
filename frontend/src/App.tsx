import { useEffect, useState } from 'react'

import TeamList from './TeamList'

type Health = {
  status: string
  database: { file: string; ok: boolean; read_only?: boolean; error?: string }
}

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json() as Promise<Health>
      })
      .then(setHealth)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <main>
      <h1>FPL Real Shape</h1>
      <TeamList />
      <footer className="muted">
        API:{' '}
        {error
          ? `backend unreachable (${error})`
          : health
            ? `${health.status}, ${health.database.file}${
                health.database.ok
                  ? health.database.read_only
                    ? ' (read-only)'
                    : ' (NOT read-only)'
                  : ` (error: ${health.database.error})`
              }`
            : 'checking…'}
      </footer>
    </main>
  )
}

export default App

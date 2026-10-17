import { useEffect, useState } from 'react'

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
      <h2>API health</h2>
      {error && <p className="error">Backend unreachable: {error}</p>}
      {!error && !health && <p>Checking…</p>}
      {health && (
        <dl>
          <dt>Status</dt>
          <dd>{health.status}</dd>
          <dt>Database</dt>
          <dd>
            {health.database.file}{' '}
            {health.database.ok
              ? health.database.read_only
                ? '(opened read-only)'
                : '(NOT read-only)'
              : `(error: ${health.database.error})`}
          </dd>
        </dl>
      )}
    </main>
  )
}

export default App

import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fileUrl, fmt, getRuns, SPECIES_SHORT, timeAgo, type RunSummary } from '../api'

export default function History() {
  const [runs, setRuns] = useState<RunSummary[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getRuns().then(setRuns).catch((e) => setError(String(e.message ?? e)))
  }, [])

  if (error) return <div className="error">{error}</div>
  if (!runs) return <p className="muted">Loading…</p>

  return (
    <div className="history">
      <div className="history-head">
        <div>
          <h1>All results</h1>
          <p className="muted">{runs.length} image{runs.length === 1 ? '' : 's'} analyzed so far</p>
        </div>
        {runs.length > 0 && (
          <a className="button" href="/api/runs.xlsx">
            Download everything (.xlsx)
          </a>
        )}
      </div>
      {runs.length === 0 ? (
        <div className="card empty">
          <p>No images analyzed yet.</p>
          <Link to="/" className="button">
            Analyze your first image
          </Link>
        </div>
      ) : (
        <div className="run-grid">
          {runs.map((r) => (
            <Link to={`/runs/${r.id}`} key={r.id} className="run-card">
              <img src={fileUrl(r.id, 'overlay.png')} alt="" loading="lazy" />
              <div className="run-meta">
                <div className="run-name" title={r.filename}>
                  {r.filename}
                </div>
                <div className="muted small">
                  {SPECIES_SHORT[r.sample_type ?? ''] ?? r.sample_type ?? 'unsure'} · {fmt(r.n_frustules)} frustules ·{' '}
                  {fmt(r.n_pores)} pores
                </div>
                <div className="muted small">{timeAgo(r.created_at)}</div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

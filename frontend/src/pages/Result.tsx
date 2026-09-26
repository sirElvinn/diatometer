import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fileUrl, fmt, getRun, SPECIES_SHORT, type Config, type Run } from '../api'
import DataTable from '../components/DataTable'

const FRUSTULE_COLS = [
  { key: 'frustule_id', label: '#' },
  { key: 'species', label: 'Species' },
  { key: 'length_um', label: 'Length µm' },
  { key: 'width_um', label: 'Width µm' },
  { key: 'area_um2', label: 'Area µm²' },
  { key: 'view', label: 'View' },
  { key: 'orientation_deg', label: 'Angle °' },
  { key: 'head_direction_deg', label: 'Head °' },
  { key: 'damage', label: 'Damage' },
  { key: 'n_pores', label: 'Pores' },
  { key: 'mean_pore_diameter_um', label: 'Mean pore µm' },
  { key: 'solidity', label: 'Solidity' },
  { key: 'x_um', label: 'x µm' },
  { key: 'y_um', label: 'y µm' },
]
const PORE_COLS = [
  { key: 'frustule_id', label: 'Frustule #' },
  { key: 'x_um', label: 'x µm' },
  { key: 'y_um', label: 'y µm' },
  { key: 'diameter_um', label: 'Diameter µm' },
]
const PROBS = [
  { key: 'p_Thalassiosira', label: 'Thaps' },
  { key: 'p_Didymosphenia', label: 'Didymo' },
  { key: 'p_Richmond', label: 'Richmond fossil' },
]
const DAMAGE = [
  { key: 'n_intact', label: 'Intact', cls: 'intact' },
  { key: 'n_cracked', label: 'Cracked', cls: 'cracked' },
  { key: 'n_fragmented', label: 'Fragmented', cls: 'fragmented' },
]

function num(v: unknown): number {
  return typeof v === 'number' ? v : 0
}

export default function Result({ config }: { config: Config | null }) {
  const { id = '' } = useParams()
  const [run, setRun] = useState<Run | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'overlay' | 'preview'>('overlay')
  const [tab, setTab] = useState<'frustules' | 'pores'>('frustules')

  useEffect(() => {
    setRun(null)
    getRun(id).then(setRun).catch((e) => setError(String(e.message ?? e)))
  }, [id])

  // the Google Sheet sync runs in the background; poll until it reports back
  useEffect(() => {
    if (run?.sheet_status !== 'pending') return
    const t = setTimeout(() => getRun(id).then(setRun).catch(() => {}), 2000)
    return () => clearTimeout(t)
  }, [run, id])

  if (error) return <div className="error">{error}</div>
  if (!run) return <p className="muted">Loading…</p>

  const im = run.image
  const total = num(im.n_frustules)
  const partial = total - num(im.n_intact) - num(im.n_cracked) - num(im.n_fragmented)
  const confidence = num(im.sample_type_confidence)

  return (
    <div className="result">
      <div className="result-head">
        <div>
          <Link to="/history" className="muted small">
            ← All results
          </Link>
          <h1 className="filename">{run.filename}</h1>
          <p className="muted small">
            {new Date(run.created_at).toLocaleString()} · analyzed in {fmt(im.seconds, 1)} s · {String(im.backend)}
          </p>
        </div>
        <div className="downloads">
          <a className="button" href={fileUrl(run.id, 'results.xlsx')}>
            Download .xlsx
          </a>
          <a className="button ghost" href={fileUrl(run.id, 'frustules.csv')}>
            Frustules .csv
          </a>
          <a className="button ghost" href={fileUrl(run.id, 'pores.csv')}>
            Pores .csv
          </a>
          <SheetBadge status={run.sheet_status} url={config?.sheet_url ?? null} />
        </div>
      </div>

      <div className="result-grid">
        <section className="card viewer">
          <div className="viewer-bar">
            <div className="segmented small">
              <button className={view === 'overlay' ? 'on' : ''} onClick={() => setView('overlay')}>
                Outlines
              </button>
              <button className={view === 'preview' ? 'on' : ''} onClick={() => setView('preview')}>
                Original
              </button>
            </div>
            <a className="muted small" href={fileUrl(run.id, `${view}.png`)} target="_blank" rel="noreferrer">
              Open full size ↗
            </a>
          </div>
          <a href={fileUrl(run.id, `${view}.png`)} target="_blank" rel="noreferrer">
            <img src={fileUrl(run.id, `${view}.png`)} alt={`${view} of ${run.filename}`} className="sem" />
          </a>
          <div className="legend">
            <span><i className="sw intact" />intact</span>
            <span><i className="sw cracked" />cracked</span>
            <span><i className="sw fragmented" />fragmented</span>
            <span><i className="sw partial" />cut by edge</span>
            <span><i className="sw pore" />pore</span>
          </div>
        </section>

        <aside className="stats">
          <div className="card stat-big">
            <div className="stat-label">Frustules in frame</div>
            <div className="stat-value">{fmt(im.n_frustules)}</div>
            <div className="muted small">{fmt(im.n_whole_in_frame)} fully inside the image</div>
            {total > 0 && (
              <>
                <div className="bar" aria-label="damage breakdown">
                  {DAMAGE.map((d) => (
                    <span key={d.key} className={d.cls} style={{ flexGrow: num(im[d.key]) }} />
                  ))}
                  <span className="partial" style={{ flexGrow: partial }} />
                </div>
                <div className="bar-legend">
                  {DAMAGE.map((d) => (
                    <span key={d.key}>
                      <i className={`sw ${d.cls}`} />
                      {d.label} <b>{fmt(im[d.key])}</b>
                    </span>
                  ))}
                  <span>
                    <i className="sw partial" />
                    Partial <b>{partial}</b>
                  </span>
                </div>
              </>
            )}
          </div>

          <div className="card">
            <div className="stat-label">Sample type</div>
            <div className="stat-value md">
              {SPECIES_SHORT[String(im.sample_type)] ?? fmt(im.sample_type)}
              {im.sample_type_confidence != null && (
                <span className="conf">{Math.round(confidence * 100)}%</span>
              )}
            </div>
            <div className="muted small">{fmt(im.sample_type_source)}</div>
            {PROBS.some((p) => im[p.key] != null) && (
              <div className="probs">
                {PROBS.map((p) => (
                  <div key={p.key} className="prob">
                    <span>{p.label}</span>
                    <div className="prob-track">
                      <div className="prob-fill" style={{ width: `${num(im[p.key]) * 100}%` }} />
                    </div>
                    <span className="mono">{Math.round(num(im[p.key]) * 100)}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card mini-grid">
            <Mini label="Median length" value={im.median_length_um} unit="µm" />
            <Mini label="Pores found" value={im.n_pores} />
            <Mini label="Thaps" value={im.n_Thaps} />
            <Mini label="Didymo" value={im.n_Didymo} />
            <Mini label="Unknown species" value={im.n_unknown_species} />
            <Mini label="Scale" value={im.um_per_px} unit="µm/px" />
          </div>

          <div className="card notes">
            <div>
              <b>Scale source:</b> {fmt(im.scale_source)}
              {im.scale_check ? <> · {String(im.scale_check)}</> : null}
            </div>
            <div>
              <b>Pores:</b> {fmt(im.pore_note)}
            </div>
          </div>
        </aside>
      </div>

      <section className="card">
        <div className="tabs">
          <button className={tab === 'frustules' ? 'on' : ''} onClick={() => setTab('frustules')}>
            Frustules <span className="count">{run.frustules.length}</span>
          </button>
          <button className={tab === 'pores' ? 'on' : ''} onClick={() => setTab('pores')}>
            Pores <span className="count">{run.pores.length.toLocaleString()}</span>
          </button>
        </div>
        {tab === 'frustules' ? (
          <DataTable rows={run.frustules} columns={FRUSTULE_COLS} empty="No frustules found in this image." />
        ) : (
          <DataTable
            rows={run.pores}
            columns={PORE_COLS}
            empty={`No pores measured. ${im.pore_note ? String(im.pore_note) : ''}`}
          />
        )}
      </section>
    </div>
  )
}

function Mini({ label, value, unit }: { label: string; value: unknown; unit?: string }) {
  return (
    <div className="mini">
      <div className="stat-label">{label}</div>
      <div className="mini-value">
        {fmt(value, 2)}
        {unit && value != null && <small> {unit}</small>}
      </div>
    </div>
  )
}

function SheetBadge({ status, url }: { status: string | null; url: string | null }) {
  if (!status || status === 'off') return null
  const ok = status.startsWith('synced')
  const failed = status.startsWith('failed')
  const text = ok ? 'Added to public sheet' : failed ? 'Sheet sync failed' : 'Adding to sheet…'
  const cls = `badge ${ok ? 'ok' : failed ? 'bad' : 'wait'}`
  return url && ok ? (
    <a className={cls} href={url} target="_blank" rel="noreferrer" title={status}>
      {text} ↗
    </a>
  ) : (
    <span className={cls} title={status}>
      {text}
    </span>
  )
}

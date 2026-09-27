import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { analyze } from '../api'

const SAMPLE_TYPES = [
  { value: 'auto', label: 'Auto-detect', hint: 'Predicted from the pixels + scale' },
  { value: 'thaps', label: 'Thaps', hint: 'Thalassiosira pseudonana' },
  { value: 'didymo', label: 'Didymo', hint: 'Didymosphenia geminata' },
  { value: 'mixed', label: 'Mixed / unknown', hint: 'Generic size rules' },
]

const STEPS = [
  'Reading the scale from metadata',
  'Predicting the sample type',
  'Outlining every object with FastSAM',
  'Measuring size, orientation & damage',
  'Finding pores',
  'Writing the spreadsheet',
]

const IMAGE_EXT = ['.jpg', '.jpeg', '.tif', '.tiff', '.png']

export default function Analyze() {
  const nav = useNavigate()
  const [image, setImage] = useState<File | null>(null)
  const [sidecar, setSidecar] = useState<File | null>(null)
  const [sampleType, setSampleType] = useState('auto')
  const [backend, setBackend] = useState('fastsam')
  const [umPerPx, setUmPerPx] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [busy, setBusy] = useState(false)
  const [step, setStep] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [needsScale, setNeedsScale] = useState(false)
  const [dragging, setDragging] = useState(false)
  const input = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!busy) return
    setStep(0)
    const t = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 2600)
    return () => clearInterval(t)
  }, [busy])

  function takeFiles(files: FileList | File[]) {
    const list = Array.from(files)
    const img = list.find((f) => IMAGE_EXT.some((e) => f.name.toLowerCase().endsWith(e)))
    const txt = list.find((f) => f.name.toLowerCase().endsWith('.txt'))
    const stem = (f: File) => f.name.replace(/\.[^.]+$/, '').toLowerCase()
    if (img) {
      setImage(img)
      setError(null)
      setNeedsScale(false)
      // a .txt left over from the previous photo would give this one the wrong scale
      if (!txt) setSidecar((old) => (old && stem(old) === stem(img) ? old : null))
    }
    if (txt) setSidecar(txt)
    if (!img && !txt) setError('Drop a .tif, .jpg or .png SEM image (plus its .txt file for Hitachi images).')
  }

  async function run() {
    if (!image) return
    setBusy(true)
    setError(null)
    try {
      const res = await analyze({ image, sidecar, sampleType, backend, umPerPx })
      nav(`/runs/${res.id}`)
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      if (msg.startsWith('NO_SCALE')) {
        setNeedsScale(true)
        setShowAdvanced(true)
        setError(msg.replace('NO_SCALE: ', ''))
      } else {
        setError(msg)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="analyze">
      <section className="hero">
        <p className="eyebrow">Nano &amp; Biomaterials Lab · Challenge #1</p>
        <h1>SEM image in, measurements out.</h1>
        <p className="lede">
          Drop in a scanning-electron-microscope image of diatoms. DiatoMeter counts every frustule, names the
          species, measures it in µm, reports which way it faces, grades damage, and maps every pore, then adds
          the numbers to a shared spreadsheet.
        </p>
      </section>

      <section className="card upload-card">
        <div
          className={`dropzone ${dragging ? 'dragging' : ''} ${image ? 'has-file' : ''}`}
          onClick={() => input.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            takeFiles(e.dataTransfer.files)
          }}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
        >
          <input
            ref={input}
            type="file"
            multiple
            accept={[...IMAGE_EXT, '.txt'].join(',')}
            hidden
            onChange={(e) => e.target.files && takeFiles(e.target.files)}
          />
          {image ? (
            <>
              <div className="file-name">{image.name}</div>
              <div className="muted small">
                {(image.size / 1024 / 1024).toFixed(1)} MB
                {sidecar && <> · scale file: {sidecar.name}</>}
                {' · '}click to change
              </div>
            </>
          ) : (
            <>
              <div className="drop-icon" aria-hidden>
                <svg viewBox="0 0 48 48" width="44" height="44">
                  <ellipse cx="24" cy="24" rx="17" ry="9" transform="rotate(-30 24 24)" fill="none" stroke="currentColor" strokeWidth="2" />
                  <g fill="currentColor">
                    <circle cx="18" cy="27" r="1.8" />
                    <circle cx="24" cy="24" r="1.8" />
                    <circle cx="30" cy="21" r="1.8" />
                  </g>
                </svg>
              </div>
              <div className="file-name">Drop an SEM image here</div>
              <div className="muted small">TIFF, JPG or PNG · Hitachi users: drop the matching .txt too</div>
            </>
          )}
        </div>

        <div className="field">
          <label>Sample type</label>
          <div className="segmented">
            {SAMPLE_TYPES.map((s) => (
              <button
                key={s.value}
                className={sampleType === s.value ? 'on' : ''}
                onClick={() => setSampleType(s.value)}
                title={s.hint}
                type="button"
              >
                {s.label}
              </button>
            ))}
          </div>
          <p className="muted small">{SAMPLE_TYPES.find((s) => s.value === sampleType)?.hint}</p>
        </div>

        <button className="link-button" type="button" onClick={() => setShowAdvanced((v) => !v)}>
          {showAdvanced ? '− Hide' : '+ Show'} advanced options
        </button>

        {showAdvanced && (
          <div className="advanced">
            <div className="field">
              <label htmlFor="backend">Outlining method</label>
              <select id="backend" value={backend} onChange={(e) => setBackend(e.target.value)}>
                <option value="fastsam">FastSAM (recommended, finds any shape)</option>
                <option value="circles">Circle finder (fast, round Thaps only)</option>
              </select>
            </div>
            <div className={`field ${needsScale ? 'attention' : ''}`}>
              <label htmlFor="scale">µm per pixel (only if the file has no scale)</label>
              <input
                id="scale"
                inputMode="decimal"
                placeholder="e.g. 0.0331"
                value={umPerPx}
                onChange={(e) => setUmPerPx(e.target.value)}
              />
              <p className="muted small">
                Normally read automatically from Phenom metadata, the Hitachi .txt, or the printed field width.
              </p>
            </div>
            <div className="field">
              <label>Hitachi scale file (.txt)</label>
              <input type="file" accept=".txt" onChange={(e) => setSidecar(e.target.files?.[0] ?? null)} />
            </div>
          </div>
        )}

        {error && <div className="error">{error}</div>}

        <button className="primary" disabled={!image || busy} onClick={run}>
          {busy ? 'Analyzing…' : 'Analyze image'}
        </button>

        {busy && (
          <ol className="steps">
            {STEPS.map((s, i) => (
              <li key={s} className={i < step ? 'done' : i === step ? 'active' : ''}>
                {s}
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="how">
        <h2>What you get</h2>
        <div className="how-grid">
          <div><b>Count</b><span>every frustule, and how many are whole vs. cut off by the frame</span></div>
          <div><b>Species</b><span>from literature sizes + a size-fingerprint model</span></div>
          <div><b>Size</b><span>length, width, area in µm, never a hard-coded pixel size</span></div>
          <div><b>Orientation</b><span>valve vs. girdle view, long-axis angle, head direction</span></div>
          <div><b>Damage</b><span>intact, cracked, fragmented or partial</span></div>
          <div><b>Pores</b><span>x, y and diameter of every pore, when the zoom resolves them</span></div>
        </div>
      </section>
    </div>
  )
}

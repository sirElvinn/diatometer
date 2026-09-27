import { useMemo } from 'react'
import { fileUrl, type Run } from '../api'

interface Props {
  run: Run
  mode: 'overlay' | 'preview'
  selected: number | null
  onSelect: (id: number | null) => void
  zoom: boolean
}

const MAX_ZOOM = 3.5
const MAX_PORES = 5000

export function damageClass(damage: unknown): string {
  return String(damage ?? '').split(' ')[0] || 'partial'
}

/**
 * The SEM image with every frustule drawn as a clickable outline.
 * Selecting one dims the rest of the image, zooms onto it and shows only its pores.
 */
export default function FrustuleViewer({ run, mode, selected, onSelect, zoom }: Props) {
  const W = Number(run.image.width_px) || 1
  const H = Number(run.image.height_px) || 1
  const umPerPx = Number(run.image.um_per_px) || 1

  const shapes = useMemo(() => {
    const out: { id: number; d: string; cls: string; box: [number, number, number, number] }[] = []
    for (const f of run.frustules) {
      const id = Number(f.frustule_id)
      const polys = run.outlines?.[String(id)] ?? []
      if (!polys.length) continue
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity
      const d = polys
        .map((poly) => {
          for (const [x, y] of poly) {
            x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y)
          }
          return 'M' + poly.map(([x, y]) => `${x},${y}`).join('L') + 'Z'
        })
        .join('')
      out.push({ id, d, cls: damageClass(f.damage), box: [x0, y0, x1, y1] })
    }
    return out
  }, [run])

  const pores = useMemo(() => {
    const list = selected == null ? run.pores : run.pores.filter((p) => Number(p.frustule_id) === selected)
    return list.slice(0, MAX_PORES).map((p) => ({
      cx: Number(p.x_um) / umPerPx,
      cy: Number(p.y_um) / umPerPx,
      r: Math.max(0.8, Number(p.diameter_um) / umPerPx / 2),
    }))
  }, [run, selected, umPerPx])

  const sel = shapes.find((s) => s.id === selected) ?? null

  // zoom: scale around the selected shape, then clamp so no empty border shows
  let transform = 'none'
  if (sel && zoom) {
    const [x0, y0, x1, y1] = sel.box
    const bw = Math.max(x1 - x0, 1) * 1.8
    const bh = Math.max(y1 - y0, 1) * 1.8
    const s = Math.max(1, Math.min(MAX_ZOOM, W / bw, H / bh))
    const cx = (x0 + x1) / 2
    const cy = (y0 + y1) / 2
    const tx = Math.min(0, Math.max(W - W * s, W / 2 - cx * s))
    const ty = Math.min(0, Math.max(H - H * s, H / 2 - cy * s))
    transform = `translate(${(tx / W) * 100}%, ${(ty / H) * 100}%) scale(${s})`
  }

  const legacy = !run.outlines || shapes.length === 0
  if (mode === 'preview' || (legacy && run.frustules.length === 0)) {
    return <img src={fileUrl(run.id, mode === 'preview' ? 'preview.png' : 'overlay.png')} alt="" className="sem" />
  }
  if (legacy) {
    // runs analyzed before outlines were saved: static overlay only
    return (
      <>
        <img src={fileUrl(run.id, 'overlay.png')} alt="" className="sem" />
        <p className="muted small">Analyze this image again to click individual frustules.</p>
      </>
    )
  }

  return (
    <div className="stage-frame" style={{ aspectRatio: `${W} / ${H}` }}>
      <div className="stage" style={{ transform }}>
        <img src={fileUrl(run.id, 'preview.png')} alt={`SEM image ${run.filename}`} draggable={false} />
        <svg
          viewBox={`0 0 ${W} ${H}`}
          preserveAspectRatio="none"
          className={`outlines ${sel ? 'has-focus' : ''}`}
          onClick={() => onSelect(null)}
        >
          <defs>
            <mask id="focus-hole">
              <rect width={W} height={H} fill="white" />
              {sel && <path d={sel.d} fill="black" />}
            </mask>
          </defs>

          {shapes.map((s) => (
            <path
              key={s.id}
              d={s.d}
              className={`fr ${s.cls} ${s.id === selected ? 'is-selected' : ''}`}
              vectorEffect="non-scaling-stroke"
              onClick={(e) => {
                e.stopPropagation()
                onSelect(s.id === selected ? null : s.id)
              }}
            >
              <title>{`Frustule #${s.id} · ${s.cls}`}</title>
            </path>
          ))}

          <rect width={W} height={H} className="dim" mask="url(#focus-hole)" />

          {sel && (
            <path
              d={sel.d}
              className={`fr-focus ${sel.cls}`}
              vectorEffect="non-scaling-stroke"
              onClick={(e) => {
                e.stopPropagation()
                onSelect(null)
              }}
            />
          )}

          <g className={`pores ${sel ? 'focused' : ''}`}>
            {pores.map((p, i) => (
              <circle key={i} cx={p.cx} cy={p.cy} r={p.r} vectorEffect="non-scaling-stroke" />
            ))}
          </g>
        </svg>
      </div>
    </div>
  )
}

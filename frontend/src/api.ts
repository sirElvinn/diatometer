export type Row = Record<string, string | number | boolean | null>

export interface Run {
  id: string
  created_at: string
  filename: string
  sheet_status: string | null
  image: Row
  frustules: Row[]
  pores: Row[]
}

export interface RunSummary {
  id: string
  created_at: string
  filename: string
  sample_type: string | null
  n_frustules: number | null
  n_pores: number | null
  seconds: number | null
  sheet_status: string | null
}

export interface Config {
  sheets_enabled: boolean
  sheet_url: string | null
}

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      /* not JSON */
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const getConfig = () => fetch('/api/config').then((r) => json<Config>(r))
export const getRuns = () => fetch('/api/runs').then((r) => json<RunSummary[]>(r))
export const getRun = (id: string) => fetch(`/api/runs/${id}`).then((r) => json<Run>(r))
export const fileUrl = (id: string, name: string) => `/api/runs/${id}/${name}`

export interface AnalyzeOptions {
  image: File
  sidecar?: File | null
  sampleType: string
  backend: string
  umPerPx?: string
}

export function analyze(o: AnalyzeOptions): Promise<Run> {
  const fd = new FormData()
  fd.append('image', o.image)
  if (o.sidecar) fd.append('sidecar', o.sidecar)
  fd.append('sample_type', o.sampleType)
  fd.append('backend', o.backend)
  if (o.umPerPx?.trim()) fd.append('um_per_px', o.umPerPx.trim())
  return fetch('/api/analyze', { method: 'POST', body: fd }).then((r) => json<Run>(r))
}

export const SPECIES_SHORT: Record<string, string> = {
  'Thalassiosira pseudonana': 'Thaps',
  'Didymosphenia geminata': 'Didymo',
  'Richmond fossil diatomite (mixed)': 'Richmond fossil',
}

export function fmt(v: unknown, digits = 2): string {
  if (v === null || v === undefined || v === '') return '—'
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return v.toLocaleString()
    const abs = Math.abs(v)
    if (abs !== 0 && abs < 0.01) return v.toPrecision(3)
    return v.toFixed(digits)
  }
  if (typeof v === 'boolean') return v ? 'yes' : 'no'
  return String(v)
}

export function timeAgo(iso: string): string {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  return new Date(iso).toLocaleDateString()
}

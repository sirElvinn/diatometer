import { useEffect, useState } from 'react'
import { NavLink, Route, Routes } from 'react-router-dom'
import { getConfig, type Config } from './api'
import Analyze from './pages/Analyze'
import History from './pages/History'
import Result from './pages/Result'

export default function App() {
  const [config, setConfig] = useState<Config | null>(null)
  useEffect(() => {
    getConfig().then(setConfig).catch(() => setConfig(null))
  }, [])

  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span>DiatoMeter</span>
        </NavLink>
        <nav>
          <NavLink to="/" end>Analyze</NavLink>
          <NavLink to="/history">History</NavLink>
          {config?.sheet_url && (
            <a href={config.sheet_url} target="_blank" rel="noreferrer" className="sheet-link">
              Public sheet ↗
            </a>
          )}
        </nav>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<Analyze />} />
          <Route path="/history" element={<History />} />
          <Route path="/runs/:id" element={<Result config={config} />} />
          <Route path="*" element={<p className="muted">Page not found.</p>} />
        </Routes>
      </main>
      <footer>
        Built at &amp;hacks XII for the W&amp;M Nano &amp; Biomaterials Lab · open-source · FastSAM + scikit-image
      </footer>
    </div>
  )
}

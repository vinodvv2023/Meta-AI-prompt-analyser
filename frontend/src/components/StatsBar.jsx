import { useEffect, useState } from 'react'

export default function StatsBar() {
  const [stats, setStats] = useState(null)
  const [ingesting, setIngesting] = useState(false)

  useEffect(() => {
    fetch('/api/stats')
      .then(r => r.json())
      .then(setStats)
      .catch(() => {})

    // Refresh stats every 30s (in case ingest is running)
    const iv = setInterval(() => {
      fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {})
    }, 30_000)
    return () => clearInterval(iv)
  }, [])

  const triggerIngest = () => {
    setIngesting(true)
    fetch('/api/ingest', { method: 'POST' })
      .then(() => {
        // Poll stats after a delay
        setTimeout(() => {
          fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {})
          setIngesting(false)
        }, 4000)
      })
      .catch(() => setIngesting(false))
  }

  if (!stats) return <span className="stats-loading">Connecting…</span>

  const f = stats.facets || {}
  const types = f.type || {}
  const total = stats.total_documents || 0
  const srcFacets = f.source_file || {}
  const metaCount = srcFacets['prompts.json'] || 0
  const grokCount = srcFacets['prod-grok-backend.json'] || 0

  const items = [
    { label: 'Total',  val: total,                       color: 'var(--clr-brand)' },
    { label: 'Image',  val: types.image_prompt || 0,     color: 'var(--clr-image)' },
    { label: 'Video',  val: types.video_prompt || 0,     color: 'var(--clr-video)' },
    { label: 'Both',   val: types.both || 0,             color: 'var(--clr-both)' },
    { label: 'Failed', val: (f.llm_failed || {})['true'] || 0, color: 'var(--clr-failed)' },
    ...(metaCount > 0 ? [{ label: 'Meta AI', val: metaCount, color: 'var(--clr-convo)' }] : []),
    ...(grokCount > 0 ? [{ label: 'Grok', val: grokCount, color: '#f97316' }] : []),
  ]

  return (
    <div className="stats-bar">
      {items.map(({ label, val, color }) => val > 0 && (
        <div key={label} className="stat-item">
          <span className="stat-dot" style={{ background: color }} />
          <span className="stat-val">{val.toLocaleString()}</span>
          <span>{label}</span>
        </div>
      ))}
      <button
        id="ingest-btn"
        className={`ingest-btn ${ingesting ? 'ingesting' : ''}`}
        onClick={triggerIngest}
        title="Re-scan source folder"
      >
        {ingesting ? '⟳ Ingesting…' : '↺ Re-ingest'}
      </button>
    </div>
  )
}

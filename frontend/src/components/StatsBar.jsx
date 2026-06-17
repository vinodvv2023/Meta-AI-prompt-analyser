import { useEffect, useState } from 'react'

export default function StatsBar({ refreshTrigger, onRefresh }) {
  const [stats, setStats] = useState(null)
  const [ingesting, setIngesting] = useState(false)
  const [extracting, setExtracting] = useState(false)

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
  }, [refreshTrigger])

  const triggerIngest = () => {
    setIngesting(true)
    fetch('/api/ingest', { method: 'POST' })
      .then(() => {
        if (onRefresh) onRefresh()
        // Poll stats after a delay
        setTimeout(() => {
          fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {})
          setIngesting(false)
        }, 4000)
      })
      .catch(() => setIngesting(false))
  }

  const triggerExtractThreads = () => {
    setExtracting(true)
    fetch('/api/extract-threads', { method: 'POST' })
      .then(r => {
        if (!r.ok) throw new Error('Extraction failed')
        return r.json()
      })
      .then(() => {
        if (onRefresh) onRefresh()
        // Fetch stats immediately
        fetch('/api/stats').then(r => r.json()).then(setStats).catch(() => {})
        setExtracting(false)
      })
      .catch((err) => {
        console.error(err)
        alert('Failed to extract threads prompts. Make sure backend and threads API services are running.')
        setExtracting(false)
      })
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

  const threadsLive = stats?.threads_api_live ?? false

  return (
    <div className="stats-bar">
      {items.map(({ label, val, color }) => val > 0 && (
        <div key={label} className="stat-item">
          <span className="stat-dot" style={{ background: color }} />
          <span className="stat-val">{val.toLocaleString()}</span>
          <span>{label}</span>
        </div>
      ))}
      {!threadsLive ? (
        <span 
          className="threads-offline-msg" 
          title="Threads API is offline (port 8002). Synchronization disabled."
          style={{
            fontSize: '11px',
            color: '#ef4444',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            fontWeight: '500',
            marginRight: '8px',
            background: 'rgba(239, 68, 68, 0.1)',
            padding: '3px 8px',
            borderRadius: '4px',
            border: '1px solid rgba(239, 68, 68, 0.2)',
            height: '24px',
            boxSizing: 'border-box'
          }}
        >
          ⚠️ Threads API offline
        </span>
      ) : (
        <button
          id="extract-threads-btn"
          className={`ingest-btn ${extracting ? 'ingesting' : ''}`}
          onClick={triggerExtractThreads}
          title="Extract prompts from Threads API"
          style={{ marginRight: '4px' }}
        >
          {extracting ? '⟳ Extracting…' : '📥 Extract Threads'}
        </button>
      )}
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

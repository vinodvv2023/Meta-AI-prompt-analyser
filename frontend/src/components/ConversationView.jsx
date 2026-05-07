import { useEffect, useState, useMemo } from 'react'
import TurnCard from './TurnCard'
import { CopyButton } from './TurnCard'
import FavoriteButton from './FavoriteButton'
import TagManager from './TagManager'

const TYPE_LABELS = {
  image_prompt: { label: 'Image Prompt', cls: 'badge-image' },
  video_prompt: { label: 'Video Prompt', cls: 'badge-video' },
  both:         { label: 'Image + Video', cls: 'badge-both' },
  conversation: { label: 'Chat',         cls: 'badge-convo' },
  media:        { label: 'Media',        cls: 'badge-media' },
}

const VIDEO_RE = /\b(animate|create.*?video|make.*?video|1080p|seconds video|hd video)\b/i
const IMAGE_RE = /\b(portrait|create|generate|image|photo|illustration|--v|--stylize|--ar)\b/i

export default function ConversationView({ id }) {
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    setError(null)
    fetch(`/api/conversation/${id}`)
      .then(r => {
        if (!r.ok) throw new Error('Not found')
        return r.json()
      })
      .then(data => { setDoc(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [id])

  // ── Derive "copy all image prompts" and "copy all video prompts" text ─────
  const { allImageText, allVideoText } = useMemo(() => {
    if (!doc?.turns) return { allImageText: '', allVideoText: '' }

    const imageTurns = []
    const videoTurns = []

    doc.turns.forEach(t => {
      if (t.speaker !== 'You') return
      const txt = t.text || ''
      if (VIDEO_RE.test(txt)) videoTurns.push(txt.trim())
      else if (IMAGE_RE.test(txt)) imageTurns.push(txt.trim())
      else if (doc.type === 'image_prompt' || doc.type === 'both') imageTurns.push(txt.trim())
    })

    // If no differentiation, fall back to all user prompts
    const fallbackAll = doc.all_user_prompts || ''
    return {
      allImageText: imageTurns.join('\n\n---\n\n') || (doc.type !== 'video_prompt' ? fallbackAll : ''),
      allVideoText: videoTurns.join('\n\n---\n\n') || (doc.type === 'video_prompt' ? fallbackAll : ''),
    }
  }, [doc])

  if (loading) return (
    <div className="loading-spinner">
      <div className="spinner" /> Loading conversation…
    </div>
  )
  if (error) return (
    <div className="empty-state">
      <div className="empty-icon">⚠️</div>
      <h2>Failed to load</h2>
      <p>{error}</p>
    </div>
  )
  if (!doc) return null

  const typeMeta = TYPE_LABELS[doc.type] || { label: doc.type, cls: '' }
  const aspects = doc.image_aspects || {}
  const hasAspects = Object.keys(aspects).length > 0

  const hasImageContent = allImageText.length > 0
  const hasVideoContent = allVideoText.length > 0

  return (
    <div className="conv-view">
      {/* Header */}
      <div className="conv-header">
        <div className="conv-title">{doc.label}</div>
        <div className="conv-meta">
          {doc.date && <span className="conv-date">📅 {doc.date}</span>}
          <span className={`badge ${typeMeta.cls}`}>{typeMeta.label}</span>
          {doc.is_midjourney_style && (
            <span className="badge badge-mj">🎯 MidJourney Style</span>
          )}
          {doc.llm_failed && (
            <span className="badge badge-failed">❌ LLM Failed</span>
          )}
          <FavoriteButton docId={doc.id} isFavorite={doc.is_favorite} />
        </div>

        {/* ── Bulk copy buttons ───────────────────────────────────────────── */}
        {(hasImageContent || hasVideoContent) && (
          <div className="conv-copy-row">
            {hasImageContent && (
              <CopyButton
                text={allImageText}
                label="Copy image prompt"
                size="md"
              />
            )}
            {hasVideoContent && (
              <CopyButton
                text={allVideoText}
                label="Copy video prompt"
                size="md"
              />
            )}
            {hasImageContent && hasVideoContent && (
              <CopyButton
                text={[allImageText, allVideoText].join('\n\n═══ VIDEO ═══\n\n')}
                label="Copy all prompts"
                size="md"
              />
            )}
          </div>
        )}
      </div>

      {/* Aspects panel */}
      {hasAspects && (
        <div className="conv-aspects">
          <div className="aspects-title">Detected Aspects</div>
          <div className="aspects-grid">
            {Object.entries(aspects).map(([cat, vals]) => (
              <div className="aspect-row" key={cat}>
                <span className="aspect-label">{cat}</span>
                <div className="aspect-chips">
                  {vals.map((v, i) => (
                    <span key={i} className="aspect-chip">{v}</span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tag manager */}
      <TagManager
        docId={doc.id}
        tags={doc.tags || []}
        customTags={doc.custom_tags || []}
      />

      {/* MJ flags summary */}
      {doc.mj_flags?.length > 0 && !aspects.technical && (
        <div className="conv-aspects">
          <div className="aspects-title">MidJourney Flags</div>
          <div className="aspect-chips" style={{ paddingTop: 4 }}>
            {[...doc.mj_flags].sort((a, b) => {
              const order = {'--ar':0,'--raw':1,'--chaos':2,'--stylize':3,'--profile':4,'--p':4,'--sref':5,'--niji':6}
              const ka = a.split(/\s/)[0], kb = b.split(/\s/)[0]
              return (order[ka]??7) - (order[kb]??7)
            }).map((f, i) => (
              <span key={i} className="flag-chip">{f}</span>
            ))}
          </div>
        </div>
      )}

      {/* Turn timeline */}
      {doc.type === 'media' ? (
        <div className="turn-card">
          <div className="turn-body">
            <p className="turn-text" style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
              📎 Media file — URL only
            </p>
            <p className="turn-text" style={{ wordBreak: 'break-all', fontSize: 11, marginTop: 8, color: 'var(--text-secondary)' }}>
              {doc.all_user_prompts}
            </p>
          </div>
        </div>
      ) : (
        <div className="conv-turns">
          {(doc.turns || []).map((turn, i) => (
            <TurnCard
              key={i}
              turn={turn}
              convType={doc.type}
              isMj={doc.is_midjourney_style}
              mjFlags={doc.mj_flags}
            />
          ))}
        </div>
      )}
    </div>
  )
}

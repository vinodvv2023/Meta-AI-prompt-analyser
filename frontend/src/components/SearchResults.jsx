import { useEffect, useState, useCallback } from 'react'
import { useDebounce } from '../hooks/useDebounce'
import { filterToParams } from './FilterBar'

const TYPE_COLOR = {
  image_prompt: 'var(--clr-image)',
  video_prompt: 'var(--clr-video)',
  both:         'var(--clr-both)',
  conversation: 'var(--clr-convo)',
  media:        'var(--clr-media)',
}

const TYPE_BADGE_CLS = {
  image_prompt: 'badge-image',
  video_prompt: 'badge-video',
  both:         'badge-both',
  conversation: 'badge-convo',
  media:        'badge-media',
}

const TYPE_LABELS = {
  image_prompt: 'Image',
  video_prompt: 'Video',
  both:         'Image+Video',
  conversation: 'Chat',
  media:        'Media',
}

function buildQueryString(q, filterId, offset, limit, activeTags) {
  const params = new URLSearchParams({ q, limit, offset })
  const fp = filterToParams(filterId)
  if (fp) {
    if (fp.type)     params.set('type', fp.type)
    if (fp.mj)       params.set('mj', 'true')
    if (fp.failed)   params.set('failed', 'true')
    if (fp.favorite) params.set('favorite', 'true')
  }
  if (activeTags && activeTags.length > 0) {
    params.set('tags', activeTags.join(','))
  }
  return params.toString()
}

export default function SearchResults({ query, filter, onSelectConv, activeTags }) {
  const debouncedQ = useDebounce(query, 220)
  const [hits, setHits] = useState([])
  const [total, setTotal] = useState(0)
  const [facets, setFacets] = useState(null)
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const LIMIT = 20

  const fetchResults = useCallback((q, f, off, append = false, tgs) => {
    setLoading(true)
    setError(null)
    const qs = buildQueryString(q, f, off, LIMIT, tgs)
    fetch(`/api/search?${qs}`)
      .then(r => {
        if (!r.ok) throw new Error(`Server error (${r.status})`)
        return r.json()
      })
      .then(data => {
        setTotal(data.total || 0)
        setFacets(data.facets || null)
        setHits(prev => append ? [...prev, ...data.hits] : data.hits)
        setLoading(false)
      })
      .catch(err => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  // Reset + re-fetch when query or filter changes
  useEffect(() => {
    setOffset(0)
    fetchResults(debouncedQ, filter, 0, false)
  }, [debouncedQ, filter, activeTags, fetchResults])

  const loadMore = () => {
    const newOffset = offset + LIMIT
    setOffset(newOffset)
    fetchResults(debouncedQ, filter, newOffset, true, activeTags)
  }

  // Safely render highlighted HTML from Meilisearch _formatted
  function getHighlighted(hit, field) {
    return hit._formatted?.[field] || hit[field] || ''
  }

  return (
    <div className="search-results">
      <div className="search-results-header">
        <p className="search-results-title">
          {loading && offset === 0
            ? 'Searching…'
            : <><strong>{total.toLocaleString()}</strong> results for "<strong>{query}</strong>"</>}
        </p>
      </div>

      {hits.map(hit => (
        <div
          key={hit.id}
          id={`result-${hit.id}`}
          className="search-result-card"
          style={{ '--type-color': TYPE_COLOR[hit.type] || 'var(--clr-brand)' }}
          onClick={() => onSelectConv(hit.id)}
          role="button"
          tabIndex={0}
        >
          <div className="src-header">
            <span className="src-label">{hit.label}</span>
            {hit.date && <span className="src-date">{hit.date}</span>}
          </div>

          <div className="src-badges">
            {hit.type && (
              <span className={`badge ${TYPE_BADGE_CLS[hit.type] || ''}`}>
                {TYPE_LABELS[hit.type] || hit.type}
              </span>
            )}
            {hit.is_midjourney_style && (
              <span className="badge badge-mj">🎯 MJ</span>
            )}
            {hit.llm_failed && (
              <span className="badge badge-failed">❌ Failed</span>
            )}
          </div>

          {/* Highlighted prompt text */}
          <div
            className="src-prompt"
            dangerouslySetInnerHTML={{ __html: getHighlighted(hit, 'all_user_prompts') }}
          />

          {/* Highlighted AI response snippet */}
          {getHighlighted(hit, 'all_ai_responses') && (
            <div
              className="src-response"
              dangerouslySetInnerHTML={{ __html: getHighlighted(hit, 'all_ai_responses') }}
            />
          )}
        </div>
      ))}

      {loading && offset > 0 && (
        <div className="loading-spinner">
          <div className="spinner" /> Loading more…
        </div>
      )}

      {!loading && hits.length < total && (
        <button className="load-more-btn" onClick={loadMore}>
          Load more ({total - hits.length} remaining)
        </button>
      )}

      {!loading && hits.length === 0 && (
        <div className="empty-state">
          {error
            ? <><div className="empty-icon">⚠️</div><h2>Search failed</h2><p>{error}</p></>
            : <><div className="empty-icon">🔎</div><h2>No results</h2><p>Try a different keyword or clear filters</p></>
          }
        </div>
      )}
    </div>
  )
}

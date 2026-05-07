import { useEffect, useState } from 'react'

const FILTERS = [
  { id: 'all',          label: 'All',         icon: '✦',  cls: 'f-all',   param: null },
  { id: 'image_prompt', label: 'Image',        icon: '🖼',  cls: 'f-image', param: { type: 'image_prompt' } },
  { id: 'video_prompt', label: 'Video',        icon: '🎬',  cls: 'f-video', param: { type: 'video_prompt' } },
  { id: 'both',         label: 'Image+Video',  icon: '✨',  cls: 'f-both',  param: { type: 'both' } },
  { id: 'conversation', label: 'Chat',         icon: '💬',  cls: 'f-convo', param: { type: 'conversation' } },
  { id: 'mj',           label: 'MidJourney',   icon: '🎯',  cls: 'f-mj',   param: { mj: true } },
  { id: 'failed',       label: 'LLM Failed',   icon: '❌',  cls: 'f-failed',param: { failed: true } },
  { id: 'favorites',    label: 'Favorites',    icon: '★',  cls: 'f-fav',   param: { favorite: true } },
]

export default function FilterBar({ active, onChange, facets }) {
  // Build count map from facets
  const counts = {}
  if (facets) {
    const t = facets.type || {}
    counts.image_prompt = t.image_prompt || 0
    counts.video_prompt = t.video_prompt || 0
    counts.both         = t.both || 0
    counts.conversation = t.conversation || 0
  counts.mj     = (facets.is_midjourney_style || {})['true'] || 0
  counts.failed = (facets.llm_failed || {})['true'] || 0
  counts.favorites = (facets.is_favorite || {})['true'] || 0
  counts.all    = Object.values(t).reduce((s, v) => s + v, 0)
  }

  return (
    <div className="filter-bar-wrapper" role="toolbar" aria-label="Filter conversations">
      {FILTERS.map(f => (
        <button
          key={f.id}
          id={`filter-${f.id}`}
          className={`filter-btn ${f.cls} ${active === f.id ? 'active' : ''}`}
          onClick={() => onChange(f.id)}
        >
          <span>{f.icon}</span>
          <span>{f.label}</span>
          {counts[f.id] > 0 && (
            <span className="filter-count">{counts[f.id]}</span>
          )}
        </button>
      ))}
    </div>
  )
}

// Helper: convert filter id → API query params object
export function filterToParams(filterId) {
  const f = FILTERS.find(x => x.id === filterId)
  return f?.param || null
}

import { useEffect, useState } from 'react'

const TYPE_FILTERS = [
  { id: 'all',          label: 'All',         icon: '✦',  cls: 'f-all',   param: null },
  { id: 'image_prompt', label: 'Image',        icon: '🖼',  cls: 'f-image', param: { type: 'image_prompt' } },
  { id: 'video_prompt', label: 'Video',        icon: '🎬',  cls: 'f-video', param: { type: 'video_prompt' } },
  { id: 'both',         label: 'Image+Video',  icon: '✨',  cls: 'f-both',  param: { type: 'both' } },
  { id: 'conversation', label: 'Chat',         icon: '💬',  cls: 'f-convo', param: { type: 'conversation' } },
  { id: 'mj',           label: 'MidJourney',   icon: '🎯',  cls: 'f-mj',   param: { mj: true } },
  { id: 'failed',       label: 'LLM Failed',   icon: '❌',  cls: 'f-failed',param: { failed: true } },
  { id: 'favorites',    label: 'Favorites',    icon: '★',  cls: 'f-fav',   param: { favorite: true } },
]

const SOURCE_FILTERS = [
  { id: 'all',     label: 'All Sources', value: null },
  { id: 'meta',    label: 'Meta AI',     value: 'prompts.json' },
  { id: 'grok',    label: 'Grok',        value: 'prod-grok-backend.json' },
]

export default function FilterBar({ active, onChange, source, onSourceChange, facets }) {
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

  const srcFacet = facets?.source_file || {}
  const srcCounts = {
    all:  Object.values(srcFacet).reduce((s, v) => s + v, 0),
    meta: srcFacet['prompts.json'] || 0,
    grok: srcFacet['prod-grok-backend.json'] || 0,
  }

  return (
    <div className="filter-bar-wrapper" role="toolbar" aria-label="Filter conversations">
      <div className="filter-bar-type">
        {TYPE_FILTERS.map(f => (
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
      <div className="filter-bar-source">
        <span className="source-divider">|</span>
        {SOURCE_FILTERS.map(f => (
          <button
            key={f.id}
            id={`source-${f.id}`}
            className={`filter-btn f-source ${source === f.id ? 'active' : ''}`}
            onClick={() => onSourceChange(f.id)}
          >
            <span>{f.label}</span>
            {srcCounts[f.id] > 0 && (
              <span className="filter-count">{srcCounts[f.id]}</span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}

export function filterToParams(filterId) {
  const f = TYPE_FILTERS.find(x => x.id === filterId)
  return f?.param || null
}

export function sourceToValue(sourceId) {
  const f = SOURCE_FILTERS.find(x => x.id === sourceId)
  return f?.value || null
}

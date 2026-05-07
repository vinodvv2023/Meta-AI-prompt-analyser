import { useEffect, useState, useMemo } from 'react'

const CATEGORY_LABELS = {
  medium_style: 'Medium / Style',
  lighting: 'Lighting',
  composition: 'Composition',
  color_palette: 'Color Palette',
  environment: 'Environment',
  artist_reference: 'Artist / Reference',
}

const CATEGORY_ICONS = {
  medium_style: '🎨',
  lighting: '💡',
  composition: '📷',
  color_palette: '🌈',
  environment: '🌿',
  artist_reference: '🖼',
}

const INITIAL_SHOWN = 8

export default function KeywordExplorer({ activeTags, onToggleTag }) {
  const [keywords, setKeywords] = useState(null)
  const [loading, setLoading] = useState(true)
  const [panelOpen, setPanelOpen] = useState(false)
  const [collapsed, setCollapsed] = useState({})
  const [expanded, setExpanded] = useState({})

  useEffect(() => {
    setLoading(true)
    fetch('/api/keywords')
      .then(r => r.json())
      .then(data => { setKeywords(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const toggleCategory = (cat) =>
    setCollapsed(prev => ({ ...prev, [cat]: !prev[cat] }))

  const toggleExpand = (cat) =>
    setExpanded(prev => ({ ...prev, [cat]: !prev[cat] }))

  const totalKeywords = useMemo(() => {
    if (!keywords) return 0
    return Object.values(keywords).reduce((s, v) => s + Object.keys(v).length, 0)
  }, [keywords])

  if (loading || !keywords) return null

  const categoriesWithData = Object.entries(CATEGORY_LABELS).filter(
    ([cat]) => Object.keys(keywords[cat] || {}).length > 0
  )

  if (categoriesWithData.length === 0) return null

  return (
    <div className="keyword-explorer">
      <div className="ke-header" onClick={() => setPanelOpen(p => !p)}>
        <span className="ke-title">Explore by Keyword</span>
        <span className="ke-header-meta">
          {totalKeywords} keywords
        </span>
        <span className={`ke-toggle ${panelOpen ? 'ke-toggle-open' : ''}`}>▸</span>
      </div>

      {panelOpen && (
        <>
          <div className="ke-cat-list">
            {categoriesWithData.map(([cat, label]) => {
              const catKeywords = keywords[cat] || {}
              const allEntries = Object.entries(catKeywords)
              const isCollapsed = collapsed[cat]
              const isExpanded = expanded[cat]
              const visibleEntries = isExpanded ? allEntries : allEntries.slice(0, INITIAL_SHOWN)
              const remainingCount = allEntries.length - INITIAL_SHOWN

              return (
                <div className="ke-category" key={cat}>
                  <div className="ke-cat-header" onClick={() => toggleCategory(cat)}>
                    <span className="ke-cat-icon">{CATEGORY_ICONS[cat]}</span>
                    <span className="ke-cat-label">{label}</span>
                    <span className="ke-cat-count">{allEntries.length}</span>
                    <span className={`ke-cat-arrow ${isCollapsed ? '' : 'ke-cat-arrow-open'}`}>▸</span>
                  </div>

                  {!isCollapsed && (
                    <>
                      <div className="ke-chips">
                        {visibleEntries.map(([kw, count]) => {
                          const isActive = activeTags.includes(kw)
                          return (
                            <button
                              key={kw}
                              className={`ke-chip ${isActive ? 'ke-chip-active' : ''}`}
                              onClick={() => onToggleTag(kw)}
                            >
                              {kw}
                              <span className="ke-chip-count">{count}</span>
                            </button>
                          )
                        })}
                      </div>
                      {remainingCount > 0 && (
                        <button
                          className="ke-expand-btn"
                          onClick={() => toggleExpand(cat)}
                        >
                          {isExpanded ? 'Show less' : `+${remainingCount} more`}
                        </button>
                      )}
                    </>
                  )}
                </div>
              )
            })}
          </div>

          {activeTags.length > 0 && (
            <div className="ke-active-bar">
              <span className="ke-active-label">Active filters:</span>
              <div className="ke-active-chips">
                {activeTags.map(tag => (
                  <button
                    key={tag}
                    className="ke-chip ke-chip-active"
                    onClick={() => onToggleTag(tag)}
                  >
                    {tag} ×
                  </button>
                ))}
                <button
                  className="ke-clear-all"
                  onClick={() => activeTags.forEach(t => onToggleTag(t))}
                >
                  Clear all
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

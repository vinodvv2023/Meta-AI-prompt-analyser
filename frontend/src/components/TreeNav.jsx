import { useEffect, useState } from 'react'
import { sourceToValue } from './FilterBar'

const TYPE_ICON = {
  image_prompt: '🖼',
  video_prompt: '🎬',
  both:         '✨',
  conversation: '💬',
  media:        '📎',
}

const SOURCE_ICON = {
  'prompts.json': '🟦',
  'prod-grok-backend.json': '🟧',
  'threads-prompts.json': '🟩',
  'user-prompts.json': '🔮',
}

function buildApiParams(filterId, activeTags, sourceId) {
  let params = ''
  if (filterId === 'mj')       params += '&mj=true'
  if (filterId === 'failed')   params += '&failed=true'
  if (filterId === 'favorites') params += '&favorite=true'
  if (filterId === 'xx')        params += '&xx=true'
  if (filterId === 'xxx')       params += '&xxx=true'
  if (filterId && filterId !== 'all' && filterId !== 'mj' && filterId !== 'failed' && filterId !== 'favorites' && filterId !== 'xx' && filterId !== 'xxx') {
    params += `&type=${filterId}`
  }
  if (activeTags && activeTags.length > 0) {
    params += `&tags=${encodeURIComponent(activeTags.join(','))}`
  }
  const srcVal = sourceToValue(sourceId || 'all')
  if (srcVal) {
    params += `&source=${encodeURIComponent(srcVal)}`
  }
  return params
}

export default function TreeNav({ activeFilter, activeSource, selectedId, onSelect, activeTags, refreshTrigger }) {
  const [tree, setTree] = useState({})
  const [loading, setLoading] = useState(true)
  const [collapsed, setCollapsed] = useState({})
  const [treeSearch, setTreeSearch] = useState('')

  useEffect(() => {
    setLoading(true)
    const params = buildApiParams(activeFilter, activeTags, activeSource)
    fetch(`/api/tree?${params}`)
      .then(r => r.json())
      .then(data => { setTree(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [activeFilter, activeTags, activeSource, refreshTrigger])

  const toggleDate = (date) =>
    setCollapsed(prev => ({ ...prev, [date]: !prev[date] }))

  const filtered = Object.entries(tree).reduce((acc, [date, items]) => {
    if (!treeSearch) { acc[date] = items; return acc }
    const q = treeSearch.toLowerCase()
    const hits = items.filter(i =>
      (i.preview || '').toLowerCase().includes(q) ||
      (i.label || '').toLowerCase().includes(q)
    )
    if (hits.length) acc[date] = hits
    return acc
  }, {})

  return (
    <>
      <div className="tree-search">
        <input
          id="tree-search"
          type="text"
          placeholder="Filter tree…"
          value={treeSearch}
          onChange={e => setTreeSearch(e.target.value)}
        />
      </div>

      <div className="tree-scroll">
        {loading && (
          <div className="loading-spinner">
            <div className="spinner" /> Loading…
          </div>
        )}

        {!loading && Object.keys(filtered).length === 0 && (
          <div className="tree-empty">No conversations found</div>
        )}

        {!loading && Object.entries(filtered).map(([date, items]) => (
          <div className="tree-date-group" key={date}>
            <div
              className={`tree-date-header ${collapsed[date] ? 'collapsed' : ''}`}
              onClick={() => toggleDate(date)}
              role="button"
              tabIndex={0}
            >
              <span>📅 {date}</span>
              <span>
                <span className="tree-date-count">{items.length}</span>
                <span className="chevron"> ▾</span>
              </span>
            </div>

            {!collapsed[date] && (
              <div className="tree-items">
                {items.map(item => (
                  <div
                    key={item.id}
                    id={`tree-item-${item.id}`}
                    className={`tree-item ${selectedId === item.id ? 'active' : ''}`}
                    onClick={() => onSelect(item.id)}
                    role="button"
                    tabIndex={0}
                  >
                    <span className="tree-item-icon">
                      {TYPE_ICON[item.type] || '💬'}
                    </span>
                    <div className="tree-item-text">
                      <div className="tree-item-preview">
                        {item.preview || item.label}
                      </div>
                      <div className="tree-item-badges">
                        {item.is_favorite && (
                          <span className="badge badge-fav">★</span>
                        )}
                        {item.is_xx && (
                          <span className="badge badge-xx">XX</span>
                        )}
                        {item.is_xxx && (
                          <span className="badge badge-xxx">XXX</span>
                        )}
                        {item.is_midjourney_style && (
                          <span className="badge badge-mj">MJ</span>
                        )}
                        {item.has_video && (
                          <span className="badge badge-video">Video</span>
                        )}
                        {item.llm_failed && (
                          <span className="badge badge-failed">Failed</span>
                        )}
                        {item.source_file && (
                          <span className="badge badge-source">
                            {SOURCE_ICON[item.source_file] || '📄'}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </>
  )
}

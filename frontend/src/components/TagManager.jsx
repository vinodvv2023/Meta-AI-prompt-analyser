import { useState, useCallback } from 'react'

export default function TagManager({ docId, tags, customTags: initialCustom }) {
  const [customTags, setCustomTags] = useState(initialCustom || [])
  const [input, setInput] = useState('')
  const [saving, setSaving] = useState(false)

  const addTag = useCallback(async () => {
    const tag = input.trim().toLowerCase()
    if (!tag || customTags.includes(tag)) { setInput(''); return }
    const next = [...customTags, tag]
    setCustomTags(next)
    setInput('')
    setSaving(true)
    try {
      await fetch(`/api/conversation/${docId}/tags`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ add: [tag] }),
      })
    } catch { setCustomTags(customTags) }
    finally { setSaving(false) }
  }, [input, customTags, docId])

  const removeTag = useCallback(async (tag) => {
    const next = customTags.filter(t => t !== tag)
    setCustomTags(next)
    setSaving(true)
    try {
      await fetch(`/api/conversation/${docId}/tags`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ remove: [tag] }),
      })
    } catch { setCustomTags(customTags) }
    finally { setSaving(false) }
  }, [customTags, docId])

  const handleKey = (e) => {
    if (e.key === 'Enter') addTag()
  }

  const autoTags = (tags || []).filter(t => !customTags.includes(t))

  if (!autoTags.length && !customTags.length) return null

  return (
    <div className="conv-tags">
      <div className="tags-title">Tags</div>
      <div className="tags-chips">
        {autoTags.map((tag, i) => (
          <span key={`a-${i}`} className="tag-chip tag-auto">{tag}</span>
        ))}
        {customTags.map((tag, i) => (
          <span key={`c-${i}`} className="tag-chip tag-custom">
            {tag}
            <button
              className="tag-remove"
              onClick={(e) => { e.stopPropagation(); removeTag(tag) }}
              aria-label={`Remove tag ${tag}`}
              disabled={saving}
            >×</button>
          </span>
        ))}
      </div>
      <div className="tag-add-row">
        <input
          className="tag-input"
          type="text"
          placeholder="Add custom tag..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKey}
          disabled={saving}
        />
        <button
          className="tag-add-btn"
          onClick={addTag}
          disabled={!input.trim() || saving}
        >
          {saving ? '…' : '+'}
        </button>
      </div>
    </div>
  )
}

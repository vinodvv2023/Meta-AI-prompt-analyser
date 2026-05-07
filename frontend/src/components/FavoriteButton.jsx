import { useState, useCallback } from 'react'

export default function FavoriteButton({ docId, isFavorite: initialFavorite }) {
  const [isFavorite, setIsFavorite] = useState(initialFavorite || false)
  const [saving, setSaving] = useState(false)

  const toggle = useCallback(async (e) => {
    e.stopPropagation()
    if (saving) return
    const next = !isFavorite
    setIsFavorite(next)
    setSaving(true)
    try {
      const res = await fetch(`/api/conversation/${docId}/favorite`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_favorite: next }),
      })
      if (!res.ok) throw new Error()
    } catch {
      setIsFavorite(!next)
    } finally {
      setSaving(false)
    }
  }, [docId, isFavorite, saving])

  return (
    <button
      className={`fav-btn ${isFavorite ? 'fav-active' : ''} ${saving ? 'fav-saving' : ''}`}
      onClick={toggle}
      title={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
      aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
    >
      <span className="fav-icon">{isFavorite ? '★' : '☆'}</span>
    </button>
  )
}

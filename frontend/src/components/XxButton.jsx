import { useState, useCallback, useEffect } from 'react'

export default function XxButton({ docId, isXx: initialXx }) {
  const [isXx, setIsXx] = useState(initialXx || false)
  const [saving, setSaving] = useState(false)

  // Sync state if initialXx changes (e.g. switching between different conversations)
  useEffect(() => {
    setIsXx(initialXx || false)
  }, [initialXx])

  const toggle = useCallback(async (e) => {
    e.stopPropagation()
    if (saving) return
    const next = !isXx
    setIsXx(next)
    setSaving(true)
    try {
      const res = await fetch(`/api/conversation/${docId}/xx`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_xx: next }),
      })
      if (!res.ok) throw new Error()
    } catch {
      setIsXx(!next)
    } finally {
      setSaving(false)
    }
  }, [docId, isXx, saving])

  return (
    <button
      className={`fav-btn xx-btn ${isXx ? 'xx-active' : ''} ${saving ? 'fav-saving' : ''}`}
      onClick={toggle}
      title={isXx ? 'Remove from XX' : 'Save to XX'}
      aria-label={isXx ? 'Remove from XX' : 'Save to XX'}
    >
      <span className="fav-icon">XX</span>
    </button>
  )
}

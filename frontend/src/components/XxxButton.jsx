import { useState, useCallback, useEffect } from 'react'

export default function XxxButton({ docId, isXxx: initialXxx }) {
  const [isXxx, setIsXxx] = useState(initialXxx || false)
  const [saving, setSaving] = useState(false)

  // Sync state if initialXxx changes (e.g. switching between different conversations)
  useEffect(() => {
    setIsXxx(initialXxx || false)
  }, [initialXxx])

  const toggle = useCallback(async (e) => {
    e.stopPropagation()
    if (saving) return
    const next = !isXxx
    setIsXxx(next)
    setSaving(true)
    try {
      const res = await fetch(`/api/conversation/${docId}/xxx`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_xxx: next }),
      })
      if (!res.ok) throw new Error()
    } catch {
      setIsXxx(!next)
    } finally {
      setSaving(false)
    }
  }, [docId, isXxx, saving])

  return (
    <button
      className={`fav-btn xxx-btn ${isXxx ? 'xxx-active' : ''} ${saving ? 'fav-saving' : ''}`}
      onClick={toggle}
      title={isXxx ? 'Remove from XXX' : 'Save to XXX'}
      aria-label={isXxx ? 'Remove from XXX' : 'Save to XXX'}
    >
      <span className="fav-icon">XXX</span>
    </button>
  )
}

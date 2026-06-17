import { useState } from 'react'

export default function AddPromptModal({ onClose, onAdd }) {
  const [prompt, setPrompt] = useState('')
  const [aiResponse, setAiResponse] = useState('')
  const [type, setType] = useState('image_prompt')
  const [label, setLabel] = useState('')
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0])
  const [isFavorite, setIsFavorite] = useState(false)
  const [isXx, setIsXx] = useState(false)
  const [isXxx, setIsXxx] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!prompt.trim()) return

    setSubmitting(true)
    setError(null)

    try {
      const res = await fetch('/api/conversation/custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: prompt.trim(),
          ai_response: aiResponse.trim(),
          type,
          label: label.trim() || null,
          date: date || null,
          is_favorite: isFavorite,
          is_xx: isXx,
          is_xxx: isXxx,
        }),
      })

      if (!res.ok) {
        throw new Error('Failed to save custom prompt')
      }

      const data = await res.json()
      onAdd(data)
      onClose()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Add Custom Prompt</h3>
          <button className="modal-close-btn" onClick={onClose}>&times;</button>
        </div>

        <form onSubmit={handleSubmit} className="modal-form">
          {error && <div className="modal-error">{error}</div>}

          <div className="form-group">
            <label htmlFor="prompt-text">Prompt Text <span className="req">*</span></label>
            <textarea
              id="prompt-text"
              required
              rows={4}
              placeholder="Describe your image or video prompt..."
              value={prompt}
              onChange={e => setPrompt(e.target.value)}
            />
          </div>

          <div className="form-group">
            <label htmlFor="ai-response">AI Response <span className="opt">(optional)</span></label>
            <textarea
              id="ai-response"
              rows={3}
              placeholder="What did the AI reply or output?"
              value={aiResponse}
              onChange={e => setAiResponse(e.target.value)}
            />
          </div>

          <div className="form-row">
            <div className="form-group half">
              <label htmlFor="prompt-type">Prompt Type</label>
              <select
                id="prompt-type"
                value={type}
                onChange={e => setType(e.target.value)}
              >
                <option value="image_prompt">🖼 Image</option>
                <option value="video_prompt">🎬 Video</option>
                <option value="both">✨ Image + Video</option>
              </select>
            </div>

            <div className="form-group half">
              <label htmlFor="prompt-date">Date</label>
              <input
                id="prompt-date"
                type="date"
                value={date}
                onChange={e => setDate(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="prompt-label">Label / Title <span className="opt">(optional)</span></label>
            <input
              id="prompt-label"
              type="text"
              placeholder="e.g. Dreamy Unicorn in Forest"
              value={label}
              onChange={e => setLabel(e.target.value)}
            />
          </div>

          <div className="form-group-checkboxes">
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={isFavorite}
                onChange={e => setIsFavorite(e.target.checked)}
              />
              <span>★ Add to Favorites</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={isXx}
                onChange={e => setIsXx(e.target.checked)}
              />
              <span>📁 Save to XX</span>
            </label>

            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={isXxx}
                onChange={e => setIsXxx(e.target.checked)}
              />
              <span>📁 Save to XXX</span>
            </label>
          </div>

          <div className="modal-actions">
            <button type="button" className="btn-secondary" onClick={onClose} disabled={submitting}>
              Cancel
            </button>
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? 'Adding...' : 'Add Prompt'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

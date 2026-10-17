import { useGetConversationQuery, useSetLabelMutation } from '../stores/labelsApi'

export default function LabelButton({ docId, field, initialValue }) {
  const { currentData: doc } = useGetConversationQuery(docId)
  const [setLabel, { isLoading, isError }] = useSetLabelMutation()
  const label = field === 'is_xx' ? 'XX' : 'XXX'
  const active = doc?.[field] ?? initialValue ?? false
  const manual = doc?.label_analysis?.manual_overrides?.[field]
  const overridden = manual === true || manual === false
  const save = value => setLabel({ id: docId, field, value })

  return (
    <div className="label-control" onClick={event => event.stopPropagation()}>
      <button
        type="button"
        className={`fav-btn ${label.toLowerCase()}-btn ${active ? `${label.toLowerCase()}-active` : ''}`}
        disabled={isLoading}
        aria-pressed={active}
        aria-label={`${active ? 'Remove from' : 'Save to'} ${label}`}
        title={`${active ? 'Remove from' : 'Save to'} ${label}${overridden ? ' (manual)' : ''}`}
        onClick={() => save(!active)}
      >
        {label}
      </button>
      {overridden && (
        <button type="button" className="label-reset" disabled={isLoading}
          onClick={() => save(null)} aria-label={`Use automatic ${label} labeling`}>
          Use automatic
        </button>
      )}
      {isLoading && <span className="label-note" role="status">Saving {label}…</span>}
      {isError && <span className="label-error" role="alert">Could not sync {label}. Retry or re-ingest.</span>}
    </div>
  )
}

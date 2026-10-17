import { labelKeywords } from './labelKeywords'

const STATUS = {
  not_analyzed: 'Not analyzed yet', disabled: 'Automatic analysis is off',
  complete: 'Analysis complete', needs_review: 'Review needed', error: 'Analysis unavailable',
}

export default function LabelAnalysis({ analysis, promptText = '', activeTerm = '', onSelectTerm }) {
  if (!analysis) return null
  return (
    <section className="label-analysis" aria-label="Prompt label analysis">
      <div className="label-analysis-heading">
        <strong>Prompt labels</strong>
        <span>{STATUS[analysis.status] || 'Not analyzed yet'}{analysis.mode === 'review' ? ' · Suggestions only' : ''}</span>
      </div>
      {analysis.mode === 'off' && analysis.status !== 'disabled' && <p>Automatic analysis is off. Showing the last result.</p>}
      {analysis.stale && <p role="status">Some labels come from an earlier analysis. Re-ingest or review this prompt.</p>}
      {analysis.projection_pending && <p role="status">Your decision is saved; search sync is pending. Retry or re-ingest.</p>}
      {analysis.status === 'error' && <p role="status">Labels were preserved. {analysis.error || 'Check Laya configuration and re-ingest to retry.'}</p>}
      <div className="label-analysis-results">
        {['is_xx', 'is_xxx'].map(field => {
          const suggestion = analysis.suggestions?.[field]
          const score = analysis.scores?.[field]
          const manual = analysis.manual_overrides?.[field]
          const terms = labelKeywords(promptText, field)
          return <div key={field}>
            <strong>{field === 'is_xx' ? 'XX' : 'XXX'}</strong>
            <span>{typeof suggestion === 'boolean' ? (suggestion ? 'Suggested' : 'Not suggested') : 'Undecided'}
              {typeof score === 'number' ? ` · score ${score.toFixed(2)}` : ''}</span>
            {typeof manual === 'boolean' && <span>Manual: {manual ? 'marked' : 'unmarked'}</span>}
            <div className="label-keywords" aria-label={`${field === 'is_xx' ? 'XX' : 'XXX'} matching terms`}>
              {terms.length ? terms.map(term => <button key={term} type="button"
                className="label-keyword" aria-pressed={activeTerm === term}
                onClick={() => onSelectTerm?.(activeTerm === term ? '' : term)}>{term}</button>)
                : <span>No matching label terms in the prompt.</span>}
            </div>
          </div>
        })}
      </div>
      <p>Click a term to highlight it below; click again to clear. Text matches can include exclusions and are not Laya’s reasoning.</p>
    </section>
  )
}

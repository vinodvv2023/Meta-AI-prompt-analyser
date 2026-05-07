import { useRef } from 'react'

export default function SearchBar({ value, onChange }) {
  const inputRef = useRef(null)

  return (
    <div className="search-bar">
      <span className="search-bar-icon">🔍</span>
      <input
        ref={inputRef}
        id="global-search"
        type="text"
        placeholder="Search prompts & AI responses…"
        value={value}
        onChange={e => onChange(e.target.value)}
        autoComplete="off"
        spellCheck={false}
      />
      {value && (
        <button
          className="search-clear"
          onClick={() => { onChange(''); inputRef.current?.focus() }}
          aria-label="Clear search"
        >
          ×
        </button>
      )}
    </div>
  )
}

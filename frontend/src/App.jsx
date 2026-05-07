import { useState, useCallback } from 'react'
import SearchBar from './components/SearchBar'
import FilterBar from './components/FilterBar'
import TreeNav from './components/TreeNav'
import ConversationView from './components/ConversationView'
import SearchResults from './components/SearchResults'
import StatsBar from './components/StatsBar'
import KeywordExplorer from './components/KeywordExplorer'

export default function App() {
  const [searchQuery, setSearchQuery] = useState('')
  const [activeFilter, setActiveFilter] = useState('all')
  const [selectedConvId, setSelectedConvId] = useState(null)
  const [activeTags, setActiveTags] = useState([])

  const isSearching = searchQuery.trim().length > 0

  const handleSearch = useCallback((q) => {
    setSearchQuery(q)
  }, [])

  const handleSelectFromSearch = useCallback((id) => {
    setSelectedConvId(id)
    setSearchQuery('')
  }, [])

  const handleToggleTag = useCallback((tag) => {
    setActiveTags(prev =>
      prev.includes(tag)
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    )
  }, [])

  return (
    <div className="app">
      {/* ── Header ────────────────────────────────── */}
      <header className="app-header">
        <div className="header-brand">
          <span className="brand-icon">🔮</span>
          <span className="brand-title">Prompt Explorer</span>
          <span className="brand-sub">Meta AI</span>
        </div>
        <div className="header-search">
          <SearchBar value={searchQuery} onChange={handleSearch} />
        </div>
        <StatsBar />
      </header>

      {/* ── Filter Bar ────────────────────────────── */}
      <FilterBar active={activeFilter} onChange={setActiveFilter} />

      {/* ── Keyword Explorer ─────────────────────── */}
      <KeywordExplorer activeTags={activeTags} onToggleTag={handleToggleTag} />

      {/* ── Body ──────────────────────────────────── */}
      <div className="app-body">
        {/* Left sidebar: tree nav */}
        <aside className="app-sidebar">
          <TreeNav
            activeFilter={activeFilter}
            selectedId={selectedConvId}
            onSelect={setSelectedConvId}
            activeTags={activeTags}
          />
        </aside>

        {/* Right main panel */}
        <main className="app-main">
          {isSearching ? (
            <SearchResults
              query={searchQuery}
              filter={activeFilter}
              onSelectConv={handleSelectFromSearch}
              activeTags={activeTags}
            />
          ) : selectedConvId ? (
            <ConversationView id={selectedConvId} />
          ) : (
            <div className="empty-state">
              <div className="empty-icon">🔮</div>
              <h2>Select a conversation</h2>
              <p>
                Pick an entry from the tree on the left, or type in the search
                bar to find prompts and AI responses instantly.
              </p>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

import { useMemo, useState, useCallback } from 'react'

// ─── Common English words to NOT treat as MJ reference codes ─────────────────
const COMMON_EN = new Set([
  // Prepositions, conjunctions
  'about','after','again','before','being','could','other','their','there',
  'these','think','using','where','which','would',
  // Nouns in prompts
  'image','photo','video','style','anime','model','child','woman','forest',
  'space','light','color','black','white','scene','ocean','night','dream',
  'queen','fairy','magic','water','earth','green','brown','stone','steel',
  'ghost','storm','blade','solar','micro','hyper','super','under','inner',
  // Adjectives
  'ultra','sharp','clean','clear','glass','metal','laser','bloom','swift',
  'neon','dark','gold','rich','warm','cool','soft','hard','deep','royal',
  'young','cyber','toxic','chaos','astro','lunar','glow','pulse',
  // Verbs / descriptors
  'create','render','design','imagine','facing','panel','heads','wearing',
  'standing','looking','holding','walking','running','flying','floating',
  // Scientific / long English words that pass regex
  'organic','chemistry','ancient','photon','carbon','silicon','neural',
  'cosmic','plasma','static','energy','matter','quantum','alpha','delta',
  'gamma','sigma','omega','theta','portrait','rustic','modern','future',
  'nature','urban','jungle','castle','street','studio','garden','battle',
  'palace','indoor','disco','retro','around',
  // UI / tech / context words appearing in prompts
  'display','panels','camera','surround','heads','screen','frame',
  'vision','window','hologram','digital','sphere','circle','spiral','prism',
  'shadow','silver','golden','copper','bronze','chrome','atomic',
  'matrix','galaxy','nebula','particle','crystal','mirror','tunnel','portal',
])

// Is a token a MJ reference code?
// True if: contains a digit (e.g. gtd2rcz has '2')
//       OR has ≤2 vowels in ≥5 chars (hash-like consonant cluster, e.g. igusadc)
function isMjCode(w) {
  if (COMMON_EN.has(w.toLowerCase())) return false
  if (/\d/.test(w)) return true                    // has a digit → always a code
  const vowels = (w.match(/[aeiou]/gi) || []).length
  return w.length >= 5 && vowels <= 2              // very few vowels = hash-like
}

/**
 * Parse a raw MidJourney prompt string into { prompt, flags }.
 *
 * Handles:
 *   - --sref with multiple space-separated values (numeric IDs, ::weights)
 *   - --profile with an alphanumeric code value
 *   - Orphaned codes/IDs appearing BEFORE the first --flag (moved back to their flag)
 */
function parseMjPrompt(rawText) {
  if (!rawText) return { prompt: '', flags: [] }

  // ── Step 1: Locate first --flag ──────────────────────────────────────────
  const firstFlagIdx = rawText.search(/--[a-z]/i)
  const preFlagPart = (firstFlagIdx >= 0 ? rawText.slice(0, firstFlagIdx) : rawText).trim()
  const flagsPart   = firstFlagIdx >= 0 ? rawText.slice(firstFlagIdx) : ''

  // ── Step 2: Collect orphaned tokens from pre-flag section ────────────────
  // Numeric IDs: 6+ digit numbers, optional ::weight suffix
  const numericIdRe = /\b(\d{6,}(?:::\d+)?)\b/g
  const orphanedNums = [...preFlagPart.matchAll(numericIdRe)].map(m => m[1])

  // Alphanumeric codes that look like MJ reference codes (digit-containing or consonant-heavy)
  const alphaCodeRe = /\b([a-z][a-z0-9]{4,9})\b/g
  const orphanedCodes = [...preFlagPart.matchAll(alphaCodeRe)]
    .map(m => m[1])
    .filter(w => isMjCode(w))

  // MJ ::weight tokens and :seed tokens
  const weightRe = /\s+:\d+\b/g

  // ── Step 3: Build clean display prompt ───────────────────────────────────
  let cleanPrompt = preFlagPart
  orphanedNums.forEach(id => {
    cleanPrompt = cleanPrompt.replace(id, ' ')
  })
  orphanedCodes.forEach(code => {
    cleanPrompt = cleanPrompt.replace(new RegExp(`\\b${code}\\b`, 'i'), ' ')
  })
  cleanPrompt = cleanPrompt.replace(weightRe, '').replace(/\s{2,}/g, ' ').trim()

  // ── Step 4: Parse --flags from the flags section ─────────────────────────
  // --sref takes multiple values; all other flags take at most one
  const parsedFlags = []
  const flagRe = /(--sref)((?:\s+(?!--)\S+)+)|(--[\w-]+)((?:\s+(?!--)\S+)?)/g
  let m
  while ((m = flagRe.exec(flagsPart)) !== null) {
    if (m[1]) {
      parsedFlags.push({ name: '--sref', value: m[2].trim() })
    } else {
      parsedFlags.push({ name: m[3], value: m[4]?.trim() || '' })
    }
  }

  // ── Step 5: Attach orphaned values to un-valued flags ────────────────────
  // --profile with no value → attach first orphaned alphanumeric code
  const profileFlag = parsedFlags.find(f => f.name === '--profile' && !f.value)
  if (profileFlag && orphanedCodes.length > 0) {
    profileFlag.value = orphanedCodes[0]
  }

  // --sref present → append any orphaned numeric IDs
  const srefFlag = parsedFlags.find(f => f.name === '--sref')
  if (srefFlag && orphanedNums.length > 0) {
    srefFlag.value = [srefFlag.value, ...orphanedNums].filter(Boolean).join(' ')
  } else if (!srefFlag && orphanedNums.length >= 2) {
    // Multiple orphaned numbers with no --sref flag → treat as --sref values
    parsedFlags.unshift({ name: '--sref', value: orphanedNums.join(' ') })
  }

  // ── Step 6: Sort flags into canonical MJ order ──────────────────────────
  const FLAG_ORDER = {
    '--ar':      0,
    '--raw':     1,
    '--chaos':   2,
    '--stylize': 3,
    '--profile': 4,
    '--p':       4,
    '--sref':    5,
    '--niji':    6,
  }
  const OTHER_FALLBACK = 7

  function flagSortKey(f) {
    const base = f.name.split(/\s/)[0]
    if (base === '--niji' && f.value) {
      const v = parseFloat(f.value)
      if (v >= 8.1) return 6.4
      if (v >= 8)   return 6.3
      if (v >= 7)   return 6.2
      if (v >= 6)   return 6.1
    }
    return FLAG_ORDER[base] ?? OTHER_FALLBACK
  }

  parsedFlags.sort((a, b) => flagSortKey(a) - flagSortKey(b))

  const flagStrings = parsedFlags.map(f => f.value ? `${f.name} ${f.value}` : f.name)

  return { prompt: cleanPrompt, flags: flagStrings }
}


// ─── Reusable copy button ────────────────────────────────────────────────────
export function CopyButton({ text, label = '', size = 'sm' }) {
  const [state, setState] = useState('idle') // idle | copied | error

  const handleCopy = useCallback(async (e) => {
    e.stopPropagation()
    try {
      await navigator.clipboard.writeText(text)
      setState('copied')
      setTimeout(() => setState('idle'), 2000)
    } catch {
      setState('error')
      setTimeout(() => setState('idle'), 2000)
    }
  }, [text])

  const icon = state === 'copied' ? '✓' : state === 'error' ? '✗' : '⎘'
  const tip  = state === 'copied' ? 'Copied!' : state === 'error' ? 'Failed' : (label || 'Copy prompt')

  return (
    <button
      className={`copy-btn copy-btn-${size} copy-btn-${state}`}
      onClick={handleCopy}
      title={tip}
      aria-label={tip}
    >
      <span className="copy-icon">{icon}</span>
      {label && <span className="copy-label">{label}</span>}
    </button>
  )
}


// ─── Detect turn type ────────────────────────────────────────────────────────
const VIDEO_RE  = /\b(animate|create.*?video|make.*?video|1080p|seconds video|hd video)\b/i
const IMAGE_RE  = /\b(portrait|create|generate|image|photo|illustration)\b/i
const FLAG_DETECT_RE = /--[a-z]/i

/**
 * Render one turn in the conversation timeline.
 */
export default function TurnCard({ turn, convType, isMj, mjFlags }) {
  const isYou = turn.speaker === 'You'

  // Parse MJ flags only for "You" turns in MJ conversations
  const { prompt: cleanPrompt, flags: parsedFlags } = useMemo(() => {
    if (!isYou || !isMj || !FLAG_DETECT_RE.test(turn.text)) {
      return { prompt: turn.text, flags: [] }
    }
    return parseMjPrompt(turn.text)
  }, [turn.text, isYou, isMj])

  // Copy text = reconstructed prompt + flags in proper order
  const copyText = useMemo(() => {
    if (!parsedFlags.length) return turn.text
    return `${cleanPrompt} ${parsedFlags.join(' ')}`
  }, [cleanPrompt, parsedFlags, turn.text])

  // Per-turn type detection (for badges)
  const isVideoTurn = isYou && VIDEO_RE.test(turn.text)
  const isImageTurn = isYou && (parsedFlags.length > 0 || IMAGE_RE.test(turn.text))

  return (
    <div className="turn-card">
      {/* Speaker row */}
      <div className={`turn-speaker ${isYou ? 'turn-speaker-you' : 'turn-speaker-metaai'}`}>
        <div className={`speaker-avatar ${isYou ? 'avatar-you' : 'avatar-metaai'}`}>
          {isYou ? '🧑' : '🤖'}
        </div>
        <span className="speaker-name">{isYou ? 'You' : 'Meta AI'}</span>
        <span className="turn-idx">#{turn.turn_index}</span>

        {isYou && (
          <div className="speaker-badges">
            {isImageTurn && !isVideoTurn && <span className="badge badge-image">Image</span>}
            {isVideoTurn && <span className="badge badge-video">Video</span>}
            {isImageTurn && isVideoTurn && <span className="badge badge-both">Image+Video</span>}
            {isMj && parsedFlags.length >= 2 && <span className="badge badge-mj">MJ Style</span>}
          </div>
        )}

        {/* Copy button — top-right of every speaker row */}
        <CopyButton text={copyText} size="sm" />
      </div>

      {/* Body */}
      <div className="turn-body">
        <div className="turn-text">{cleanPrompt}</div>

        {/* Flags rendered as code chips */}
        {parsedFlags.length > 0 && (
          <div className="turn-flags">
            {parsedFlags.map((f, i) => (
              <span key={i} className="flag-chip">{f}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// Text matches for display only; Laya's semantic scores do not provide attribution.
const TERMS = {
  is_xx: /(?<![\p{L}\p{N}_])(?:high[\s-]+slit|(?:large|deep)[\s-]+v[\s-]+neckline|(?:big|large)[\s-]+bust|curvy|s[\s-]+curve|curves?)(?![\p{L}\p{N}_])/giu,
  is_xxx: /(?<![\p{L}\p{N}_])(?:boobs?|nipples?|(?:exposed|bare|visible)[\s-]+breasts?)(?![\p{L}\p{N}_])/giu,
}

export function labelKeywords(text, field) {
  return [...new Set((text.match(TERMS[field]) || []).map(term => term.toLowerCase().replace(/\s+/g, ' ')))]
}

export function splitHighlight(text, term) {
  if (!term) return [text]
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&').replace(/\s+/g, '\\s+')
  return text.split(new RegExp(`(?<![\\p{L}\\p{N}_])(${escaped})(?![\\p{L}\\p{N}_])`, 'giu'))
}

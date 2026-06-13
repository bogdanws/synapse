/**
 * Extract the domain hostname from a URL, stripping the `www.` prefix.
 * Falls back to the raw string if the URL is invalid.
 */
export function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

/**
 * Map a credibility/relevance score (0–1) to a design-system colour token.
 * Thresholds match the Figma spec used by SourcePill and MarginPanel:
 *   > 0.9 → scout (high confidence)
 *   > 0.8 → scribe (mid-high)
 *   > 0.6 → muted (borderline)
 *   else  → critic (low)
 */
export function credibilityColor(score: number): string {
  if (score > 0.9) return 'var(--scout)'
  if (score > 0.8) return 'var(--scribe)'
  if (score > 0.6) return 'var(--muted)'
  return 'var(--critic)'
}

/**
 * Same thresholds as `credibilityColor`, but returns the inverse-surface
 * variant of each token. Use on tooltip popups and any other chip rendered
 * on `bg-fg`, where the page-context tokens fail AA against ivory in dark
 * mode (and read flat against ink in light mode).
 */
export function credibilityColorOnInverse(score: number): string {
  if (score > 0.9) return 'var(--scout-on-inverse)'
  if (score > 0.8) return 'var(--scribe-on-inverse)'
  if (score > 0.6) return 'var(--muted-on-inverse)'
  return 'var(--critic-on-inverse)'
}

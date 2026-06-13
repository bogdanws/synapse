import { describe, expect, it } from 'vitest'

import { credibilityColor, extractDomain } from './source-utils'

describe('extractDomain', () => {
  it('returns hostname without www prefix', () => {
    expect(extractDomain('https://www.example.com/path')).toBe('example.com')
    expect(extractDomain('https://dealroom.co/report')).toBe('dealroom.co')
  })

  it('returns hostname when www is absent', () => {
    expect(extractDomain('https://pitchbook.com/news')).toBe('pitchbook.com')
  })

  it('falls back to raw string on invalid URL', () => {
    expect(extractDomain('not-a-url')).toBe('not-a-url')
  })
})

describe('credibilityColor', () => {
  it('returns scout for scores above 0.9', () => {
    expect(credibilityColor(0.91)).toBe('var(--scout)')
    expect(credibilityColor(1.0)).toBe('var(--scout)')
  })

  it('returns scribe for scores above 0.8 up to 0.9', () => {
    expect(credibilityColor(0.85)).toBe('var(--scribe)')
    expect(credibilityColor(0.81)).toBe('var(--scribe)')
  })

  it('returns muted for scores above 0.6 up to 0.8', () => {
    expect(credibilityColor(0.75)).toBe('var(--muted)')
    expect(credibilityColor(0.61)).toBe('var(--muted)')
  })

  it('returns critic for scores at or below 0.6', () => {
    expect(credibilityColor(0.6)).toBe('var(--critic)')
    expect(credibilityColor(0.3)).toBe('var(--critic)')
    expect(credibilityColor(0.0)).toBe('var(--critic)')
  })
})

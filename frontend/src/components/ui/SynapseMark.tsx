interface SynapseMarkProps {
  size?: number
  className?: string
}

/*
 * The brand mark: three agent discs arranged in a triangle, joined by a
 * thin connecting line. Copied verbatim from example_frontend so the figma
 * stays the source of truth for the logo.
 */
export function SynapseMark({ size = 28, className }: SynapseMarkProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      className={className}
      aria-hidden
    >
      <circle cx="7" cy="7" r="3" fill="var(--scout)" />
      <circle cx="21" cy="9" r="3" fill="var(--scribe)" />
      <circle cx="14" cy="21" r="3" fill="var(--critic)" />
      <path d="M7 7 L21 9 L14 21 Z" stroke="var(--fg)" strokeWidth="0.8" fill="none" />
    </svg>
  )
}

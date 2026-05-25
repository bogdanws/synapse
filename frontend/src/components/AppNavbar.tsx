import type { CSSProperties, ReactNode } from 'react'
import { Link } from '@tanstack/react-router'

import { SynapseMark } from './ui/SynapseMark'

// Canonical spacing tokens for each layout tier. The variant owns py-* and
// border-b so those values are defined exactly once. Callers add px-*, flex
// layout, and any page-specific classes on top.
type NavVariant = 'marketing' | 'app'

const VARIANT_CX: Record<NavVariant, string> = {
  marketing: 'border-b border-line py-5 sm:py-6',
  app: 'border-b border-line py-3 sm:py-3.5 shrink-0',
}

interface AppNavbarProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
  variant?: NavVariant
}

interface SynapseBrandLinkProps {
  className?: string
  labelClassName?: string
  labelStyle?: CSSProperties
  markSize?: number
  style?: CSSProperties
}

interface AuthNavbarProps {
  /** Short tagline shown on the right, e.g. "Private beta · sign in". */
  tagline: string
}

export function AppNavbar({ children, className, style, variant }: AppNavbarProps) {
  const cx = [variant ? VARIANT_CX[variant] : '', className].filter(Boolean).join(' ')
  return (
    <header className={cx} style={style}>
      {children}
    </header>
  )
}

export function SynapseBrandLink({
  className,
  labelClassName,
  labelStyle,
  markSize = 28,
  style,
}: SynapseBrandLinkProps) {
  return (
    <Link
      to="/"
      className={className}
      style={{ textDecoration: 'none', color: 'inherit', ...style }}
      aria-label="Synapse home"
    >
      <SynapseMark size={markSize} />
      <span className={labelClassName} style={labelStyle}>
        Synapse
      </span>
    </Link>
  )
}

// Shared header for auth pages (sign-in / sign-up). Only the tagline differs.
export function AuthNavbar({ tagline }: AuthNavbarProps) {
  return (
    <AppNavbar
      variant="marketing"
      className="flex items-center justify-between px-4 sm:px-12 shrink-0"
    >
      <SynapseBrandLink
        className="flex items-center gap-3.5"
        labelClassName="serif text-xl font-medium tracking-tight"
      />
      <span className="micro" style={{ color: 'var(--muted)' }}>
        {tagline}
      </span>
    </AppNavbar>
  )
}

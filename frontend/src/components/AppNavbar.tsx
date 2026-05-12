import type { CSSProperties, ReactNode } from 'react'
import { Link } from '@tanstack/react-router'

import { SynapseMark } from './ui/SynapseMark'

interface AppNavbarProps {
  children: ReactNode
  className?: string
  style?: CSSProperties
}

interface SynapseBrandLinkProps {
  className?: string
  labelClassName?: string
  labelStyle?: CSSProperties
  markSize?: number
  style?: CSSProperties
}

export function AppNavbar({ children, className, style }: AppNavbarProps) {
  return (
    <header className={className} style={style}>
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

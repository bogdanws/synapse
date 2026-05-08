/**
 * Minimal class-name joiner. Filters out falsy values so callers can write
 * `cn('a', condition && 'b', undefined)` without thinking. This is the only
 * helper we need — at the size of this app, pulling in clsx + tailwind-merge
 * isn't worth it. Tailwind v4 also handles conflict resolution well enough at
 * the call site to make merge logic unnecessary in practice.
 */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}

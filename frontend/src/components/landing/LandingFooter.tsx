export function LandingFooter() {
  return (
    <footer className="bg-fg px-6 py-6 text-bg sm:px-10 lg:px-14">
      <div className="flex flex-col gap-3 border-t border-current pt-6 sm:flex-row sm:items-center sm:justify-between">
        <span className="micro" style={{ opacity: 0.7 }}>
          © 2026 Synapse
        </span>
        <div className="flex gap-4">
          <a
            href="/legal"
            className="micro transition-opacity hover:opacity-100"
            style={{ opacity: 0.7 }}
          >
            Legal
          </a>
          <a
            href="/privacy"
            className="micro transition-opacity hover:opacity-100"
            style={{ opacity: 0.7 }}
          >
            Privacy
          </a>
        </div>
      </div>
    </footer>
  )
}

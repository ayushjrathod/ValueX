import { Link } from 'react-router'

export default function NotFound() {
  return (
    <main className="min-h-screen bg-cx-obsidian text-cx-text-primary flex items-center justify-center px-6">
      <div className="text-center max-w-md">
        <p className="font-display text-cx-gold/30 leading-none mb-6" style={{ fontSize: 'clamp(6rem, 20vw, 12rem)' }}>
          404
        </p>
        <h1 className="text-cx-text-primary text-2xl font-medium mb-4">Page not found</h1>
        <p className="text-cx-text-secondary text-sm leading-relaxed mb-10">
          This page doesn't exist. It may have been moved, or the URL may be incorrect.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            to="/"
            className="inline-block bg-cx-gold text-cx-obsidian px-7 py-3 rounded-sm text-xs font-medium uppercase tracking-[0.08em] hover:bg-cx-gold-dim transition-colors"
          >
            Back to home
          </Link>
          <Link
            to="/chat"
            className="inline-block border border-white/15 text-cx-text-primary px-7 py-3 rounded-sm text-xs font-medium uppercase tracking-[0.08em] hover:border-white/25 hover:bg-white/5 transition-colors"
          >
            Open the assistant
          </Link>
        </div>
      </div>
    </main>
  )
}

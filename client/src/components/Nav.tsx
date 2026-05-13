import { useState, useEffect } from 'react'
import { Link } from 'react-router'
import { Menu, X } from 'lucide-react'

const links = [
  { label: 'Features', href: '#features' },
  { label: 'How It Works', href: '#how-it-works' },
  { label: 'Build Status', href: '#cta' },
]

export default function Nav() {
  const [scrolled, setScrolled] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? 'bg-cx-obsidian/90 backdrop-blur-md border-b border-white/[0.08]' : 'bg-transparent'
      }`}
    >
      <div className="max-w-[1200px] mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <Link
          to="/"
          className="text-cx-text-primary text-sm font-medium tracking-[0.06em] uppercase hover:text-cx-gold transition-colors"
        >
          Value<span className="text-cx-gold">X</span>
        </Link>

        {/* Desktop links */}
        <nav className="hidden md:flex items-center gap-8">
          {links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-cx-text-muted text-xs uppercase tracking-[0.1em] font-medium hover:text-cx-text-primary transition-colors"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Desktop CTA */}
        <div className="hidden md:block">
          <Link
            to="/chat"
            className="bg-cx-gold text-cx-obsidian px-5 py-2 rounded-sm text-xs font-medium uppercase tracking-[0.08em] transition-all duration-300 hover:bg-cx-gold-dim"
          >
            Try the Assistant
          </Link>
        </div>

        {/* Mobile menu toggle */}
        <button
          type="button"
          className="md:hidden text-cx-text-muted hover:text-cx-text-primary transition-colors"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label={menuOpen ? 'Close menu' : 'Open menu'}
        >
          {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile dropdown */}
      {menuOpen && (
        <div className="md:hidden bg-cx-obsidian/95 backdrop-blur-md border-b border-white/[0.08] px-6 pb-6 pt-2">
          <nav className="flex flex-col gap-5 mb-6">
            {links.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="text-cx-text-muted text-xs uppercase tracking-[0.1em] font-medium hover:text-cx-text-primary transition-colors"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <Link
            to="/chat"
            onClick={() => setMenuOpen(false)}
            className="inline-block bg-cx-gold text-cx-obsidian px-5 py-2.5 rounded-sm text-xs font-medium uppercase tracking-[0.08em] hover:bg-cx-gold-dim transition-colors"
          >
            Try the Assistant
          </Link>
        </div>
      )}
    </header>
  )
}

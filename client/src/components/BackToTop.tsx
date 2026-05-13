import { useState, useEffect } from 'react'
import { ArrowUp } from 'lucide-react'

export default function BackToTop() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 600)
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  if (!visible) return null

  return (
    <button
      type="button"
      onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
      aria-label="Back to top"
      className="fixed bottom-8 right-8 z-50 w-10 h-10 flex items-center justify-center rounded-sm bg-cx-surface border border-white/[0.12] text-cx-text-muted hover:text-cx-gold hover:border-white/[0.25] transition-all duration-300 shadow-card"
    >
      <ArrowUp className="w-4 h-4" strokeWidth={1.5} />
    </button>
  )
}

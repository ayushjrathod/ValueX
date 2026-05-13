import { motion } from 'framer-motion'
import { Suspense, lazy } from 'react'
import { Link } from 'react-router'

const GlobeCanvas = lazy(() => import('../components/Globe'))

export default function Hero() {
  return (
    <section
      id="hero"
      className="relative min-h-[100dvh] flex items-center justify-center overflow-hidden bg-cx-obsidian"
    >
      {/* Globe background */}
      <Suspense fallback={null}>
        <GlobeCanvas />
      </Suspense>

      {/* Decorative X marks */}
      <span className="absolute top-[15%] left-[8%] text-cx-text-muted text-xs select-none" style={{ fontSize: '8px' }}>×</span>
      <span className="absolute top-[15%] right-[12%] text-cx-text-muted text-xs select-none hidden md:block" style={{ fontSize: '8px' }}>×</span>
      <span className="absolute top-[15%] right-[12%] text-cx-text-muted text-xs select-none hidden md:block" style={{ fontSize: '8px', marginTop: '12px' }}>×</span>
      <span className="absolute top-[15%] right-[12%] text-cx-text-muted text-xs select-none hidden md:block" style={{ fontSize: '8px', marginTop: '24px' }}>×</span>
      <span className="absolute bottom-[20%] left-[10%] text-cx-text-muted text-xs select-none hidden md:block" style={{ fontSize: '8px' }}>×</span>
      <span className="absolute bottom-[20%] left-[10%] text-cx-text-muted text-xs select-none hidden md:block" style={{ fontSize: '8px', marginTop: '12px' }}>×</span>
      <span className="absolute bottom-[20%] left-[10%] text-cx-text-muted text-xs select-none hidden md:block" style={{ fontSize: '8px', marginTop: '24px' }}>×</span>

      {/* Decorative sparkles */}
      <span className="absolute top-[22%] left-[30%] w-1.5 h-1.5 bg-cx-stone-dim rotate-45 opacity-50 hidden md:block" />
      <span className="absolute top-[28%] right-[25%] w-1.5 h-1.5 bg-cx-stone-dim rotate-45 opacity-50 hidden md:block" />
      <span className="absolute bottom-[30%] left-[28%] w-1.5 h-1.5 bg-cx-stone-dim rotate-45 opacity-50 hidden md:block" />
      <span className="absolute bottom-[25%] right-[30%] w-1.5 h-1.5 bg-cx-stone-dim rotate-45 opacity-50 hidden md:block" />

      {/* Content */}
      <div className="relative z-10 text-center px-6 max-w-3xl mx-auto">
        {/* Eyebrow */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3, ease: 'easeOut' }}
          className="text-cx-gold text-xs tracking-[0.12em] uppercase font-medium mb-6"
        >
          PORTFOLIO HEALTH, PLAINLY EXPLAINED
        </motion.p>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.5, ease: 'easeOut' }}
          className="font-display text-cx-text-primary leading-[1.05] tracking-[-0.02em]"
          style={{ fontSize: 'clamp(3rem, 6vw, 6rem)' }}
        >
          Understand Your Portfolio With
        </motion.h1>
        <motion.h1
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.65, ease: 'easeOut' }}
          className="font-display text-cx-gold leading-[1.05] tracking-[-0.02em] mt-1"
          style={{ fontSize: 'clamp(3rem, 6vw, 6rem)' }}
        >
          Clarity, Not Noise.
        </motion.h1>

        {/* Subline */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.9, ease: 'easeOut' }}
          className="text-cx-text-secondary text-base leading-relaxed mt-8 max-w-[520px] mx-auto"
        >
          ValueX currently focuses on one job: turning portfolio-health metrics into plain-language observations you can review without finance jargon.
        </motion.p>

        {/* CTA Group */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 1.1, ease: 'easeOut' }}
          className="flex flex-col sm:flex-row items-center justify-center gap-4 mt-10"
        >
          <Link
            to="/chat"
            className="inline-block bg-cx-gold text-cx-obsidian px-8 py-3.5 rounded-sm text-xs font-medium uppercase tracking-[0.08em] transition-all duration-300 hover:bg-cx-gold-dim hover:shadow-card focus:outline-none focus:ring-2 focus:ring-cx-gold focus:ring-offset-2 focus:ring-offset-cx-obsidian"
          >
            Try The Assistant
          </Link>
          <a
            href="#features"
            className="inline-block bg-transparent border border-white/15 text-cx-text-primary px-8 py-3.5 rounded-sm text-xs font-medium uppercase tracking-[0.08em] transition-all duration-300 hover:border-white/25 hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-cx-gold focus:ring-offset-2 focus:ring-offset-cx-obsidian"
          >
            See Example Observations
          </a>
        </motion.div>
      </div>
    </section>
  )
}

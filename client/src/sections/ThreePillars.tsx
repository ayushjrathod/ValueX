import { motion } from 'framer-motion'
import { Brain, BarChart3, ShieldCheck, ArrowRight } from 'lucide-react'

const pillars = [
  {
    icon: Brain,
    title: 'Understand',
    body: 'Get plain-language observations grounded in computed portfolio metrics instead of opaque AI summaries.',
  },
  {
    icon: BarChart3,
    title: 'Compare',
    body: 'See your portfolio against a benchmark when one is available. The current build does not do peer-group analysis.',
  },
  {
    icon: ShieldCheck,
    title: 'Decide',
    body: 'Use the output to decide what deserves a closer look. ValueX does not place trades, monitor accounts, or send live alerts.',
  },
]

export default function ThreePillars() {
  return (
    <section className="bg-cx-obsidian border-t border-white/[0.08] py-16 md:py-24">
      <div className="max-w-[1200px] mx-auto px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-cx-gold text-xs tracking-[0.12em] uppercase font-medium mb-4">
            WHAT THIS PROTOTYPE PRIORITIZES
          </p>
          <h2
            className="text-cx-text-primary font-sans font-normal leading-[1.2] tracking-[-0.01em]"
            style={{ fontSize: 'clamp(1.75rem, 3vw, 2.5rem)' }}
          >
            Three Honest Product Promises
          </h2>
        </motion.div>

        {/* Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {pillars.map((pillar, i) => {
            const Icon = pillar.icon
            return (
              <motion.div
                key={pillar.title}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: i * 0.15, ease: 'easeOut' }}
                className="group bg-cx-surface border border-white/[0.08] rounded-sm p-8 md:p-10 transition-all duration-300 hover:-translate-y-1 hover:border-white/[0.15] hover:shadow-card-hover"
              >
                <Icon className="w-8 h-8 text-cx-gold mb-6" strokeWidth={1.5} />
                <h3 className="text-cx-text-primary text-xl font-medium mb-4">
                  {pillar.title}
                </h3>
                <p className="text-cx-text-secondary text-sm leading-relaxed mb-6">
                  {pillar.body}
                </p>
                <span className="inline-flex items-center gap-2 text-cx-gold text-sm group-hover:gap-3 transition-all duration-300 cursor-pointer">
                  Learn more
                  <ArrowRight className="w-4 h-4" strokeWidth={1.5} />
                </span>
              </motion.div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

import { motion } from 'framer-motion'

const highlights = [
  {
    title: 'Two working agents',
    body: 'portfolio_health handles concentration, return, and benchmark analysis. general_query covers definitions, greetings, and plain-language finance questions. Other intents (market research, planning, strategy) are classified but not yet implemented.',
  },
  {
    title: 'Deterministic portfolio math',
    body: 'Concentration, return, and benchmark comparison are computed in code before the model explains them.',
  },
  {
    title: 'No fake live product claims',
    body: 'This prototype does not connect brokerage accounts, send alerts, or show continuously updated portfolio views.',
  },
]

export default function Testimonials() {
  return (
    <section className="bg-cx-obsidian border-t border-white/[0.08] py-16 md:py-24">
      <div className="max-w-[800px] mx-auto px-6">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-12"
        >
          <p className="text-cx-gold text-xs tracking-[0.12em] uppercase font-medium mb-4">
            CURRENT BUILD
          </p>
          <h2
            className="text-cx-text-primary font-sans font-normal leading-[1.2] tracking-[-0.01em]"
            style={{ fontSize: 'clamp(1.75rem, 3vw, 2.5rem)' }}
          >
            What Exists Today
          </h2>
        </motion.div>

        {/* Current-state cards */}
        <div className="space-y-6">
          {highlights.map((item, i) => (
            <motion.div
              key={item.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.15, ease: 'easeOut' }}
              className="bg-cx-surface border border-white/[0.08] rounded-sm p-8"
            >
              <p className="font-display italic text-cx-text-primary text-base leading-relaxed mb-5">
                {item.title}
              </p>
              <div>
                <p className="text-cx-text-secondary text-sm leading-relaxed">{item.body}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}

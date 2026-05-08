import { motion } from 'framer-motion'

const scopeItems = ['Portfolio health', 'Benchmark context', 'Plain-language output', 'Prototype build']

export default function TrustBar() {
  return (
    <section className="border-t border-b border-white/[0.08] bg-cx-obsidian">
      <div className="max-w-[1200px] mx-auto px-6 py-4">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="flex flex-col md:flex-row items-center justify-between gap-4"
        >
          <p className="text-cx-text-muted text-sm">
            Current build focuses on
          </p>
          <div className="flex items-center gap-8">
            {scopeItems.map((name) => (
              <span
                key={name}
                className="text-cx-text-muted/60 text-xs tracking-[0.08em] uppercase font-medium"
              >
                {name}
              </span>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}

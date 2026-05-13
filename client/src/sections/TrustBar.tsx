import { motion } from 'framer-motion'

const stats = [
  { value: '2', label: 'Working agents' },
  { value: '5', label: 'Fixture users' },
  { value: 'Live', label: 'Market prices' },
  { value: 'No', label: 'Account required' },
]

export default function TrustBar() {
  return (
    <section className="border-t border-b border-white/[0.08] bg-cx-obsidian">
      <div className="max-w-[1200px] mx-auto px-6 py-5">
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="flex flex-col sm:flex-row items-center justify-between gap-6"
        >
          <p className="text-cx-text-muted text-sm shrink-0">Prototype · current build</p>
          <div className="flex items-center gap-10 sm:gap-12">
            {stats.map((s) => (
              <div key={s.label} className="text-center">
                <p className="text-cx-text-primary text-sm font-medium">{s.value}</p>
                <p className="text-cx-text-muted/60 text-[0.65rem] uppercase tracking-[0.08em] mt-0.5">{s.label}</p>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}

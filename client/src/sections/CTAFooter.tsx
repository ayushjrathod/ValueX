import { motion } from 'framer-motion'
import { Link } from 'react-router'

export default function CTAFooter() {
  return (
    <section id="cta" className="bg-cx-surface border-t border-white/[0.15] pt-16 md:pt-20 pb-10 md:pb-12">
      <div className="max-w-[1200px] mx-auto px-6">
        {/* CTA area */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center max-w-[600px] mx-auto mb-16 md:mb-20"
        >
          <h2
            className="text-cx-text-primary font-sans font-normal leading-[1.2] tracking-[-0.01em] mb-4"
            style={{ fontSize: 'clamp(1.75rem, 3vw, 2.5rem)' }}
          >
            Ready to Ask About a Real Portfolio?
          </h2>
          <p className="text-cx-text-secondary leading-relaxed mb-8">
            Open the assistant, choose a sample investor, and see how ValueX explains concentration, returns, and benchmark context in plain language.
          </p>
          <Link
            to="/chat"
            className="inline-block bg-cx-gold text-cx-obsidian px-8 py-3.5 rounded-sm text-xs font-medium uppercase tracking-[0.08em] transition-all duration-300 hover:bg-cx-gold-dim hover:shadow-card focus:outline-none focus:ring-2 focus:ring-cx-gold focus:ring-offset-2 focus:ring-offset-cx-surface"
          >
            Open The Assistant
          </Link>
        </motion.div>

        {/* Footer */}
        <div className="border-t border-white/[0.08] pt-8">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <p className="text-cx-text-muted text-sm">
              © 2025 ValueX. All rights reserved.
            </p>
            <div className="flex items-center gap-6">
              {['Privacy', 'Terms', 'Contact'].map((link) => (
                <a
                  key={link}
                  href="#"
                  className="text-cx-text-muted text-sm transition-colors duration-300 hover:text-cx-text-secondary"
                >
                  {link}
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

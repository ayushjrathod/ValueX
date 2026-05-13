import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle, Info } from 'lucide-react'

const features = [
  'Plain-English portfolio breakdown',
  'Concentration risk summary',
  'Benchmark comparison',
  'Total and annualized return context',
]

type Observation = {
  severity: 'warning' | 'info'
  text: string
}

const exampleObservations: Observation[] = [
  {
    severity: 'warning',
    text: 'NVDA makes up 41% of the portfolio — well above the 25% single-stock threshold. A sharp move in NVDA would dominate overall results.',
  },
  {
    severity: 'info',
    text: 'The portfolio returned +18.4% versus the S&P 500\'s +12.1% over the same period, an alpha of +6.3 percentage points.',
  },
  {
    severity: 'info',
    text: 'Annualized return sits at +14.2% since the earliest purchase date. The bond allocation (BND, 12%) is small relative to the aggressive risk profile.',
  },
]

export default function FeatureShowcase() {
  return (
    <section id="features" className="bg-cx-surface py-16 md:py-24">
      <div className="max-w-[1200px] mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-[55%_45%] gap-12 items-center">
          {/* Left column - Text */}
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, ease: 'easeOut' }}
          >
            <p className="text-cx-gold text-xs tracking-[0.12em] uppercase font-medium mb-4">
              WHAT THE CURRENT BUILD DOES
            </p>
            <h2
              className="text-cx-text-primary font-sans font-normal leading-[1.2] tracking-[-0.01em] mb-6"
              style={{ fontSize: 'clamp(1.75rem, 3vw, 2.5rem)' }}
            >
              Your Investments, Explained Simply
            </h2>
            <p className="text-cx-text-secondary leading-relaxed mb-8">
              The current ValueX build focuses on portfolio-health analysis. It explains concentration, return, and benchmark context in plain language based on the holdings data you provide.
            </p>

            <div className="space-y-5">
              {features.map((feature) => (
                <div key={feature} className="flex items-center gap-3">
                  <CheckCircle className="w-4 h-4 text-cx-gold flex-shrink-0" strokeWidth={1.5} />
                  <span className="text-cx-text-primary text-sm">{feature}</span>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Right column - Example observations */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay: 0.2, ease: 'easeOut' }}
          >
            <div className="bg-cx-surface-light border border-white/[0.08] rounded-sm p-6 shadow-card">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-1.5 h-1.5 rounded-full bg-cx-gold" />
                <h5 className="text-cx-text-primary text-sm font-medium">Example Assistant Output</h5>
              </div>
              <p className="text-cx-text-muted text-xs leading-relaxed mb-5">
                Illustrative observations from the portfolio-health workflow. Not a live connected account.
              </p>

              <div className="space-y-3">
                {exampleObservations.map((obs, i) => (
                  <div
                    key={i}
                    className={`flex gap-3 rounded-sm p-4 ${
                      obs.severity === 'warning'
                        ? 'bg-cx-gold/[0.07] border border-cx-gold/20'
                        : 'bg-cx-surface border border-white/[0.06]'
                    }`}
                  >
                    {obs.severity === 'warning' ? (
                      <AlertTriangle className="w-4 h-4 text-cx-gold flex-shrink-0 mt-0.5" strokeWidth={1.5} />
                    ) : (
                      <Info className="w-4 h-4 text-cx-stone-dim flex-shrink-0 mt-0.5" strokeWidth={1.5} />
                    )}
                    <p className="text-cx-text-secondary text-sm leading-relaxed">{obs.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}

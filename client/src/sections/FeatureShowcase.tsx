import { motion } from 'framer-motion'
import { CheckCircle } from 'lucide-react'

const features = [
  'Plain-English portfolio breakdown',
  'Concentration risk summary',
  'Benchmark comparison',
  'Total and annualized return context',
]

const tableData = [
  { asset: 'AAPL', allocation: '18.2%', return: '+12.4%', status: 'Strong', positive: true },
  { asset: 'VTI', allocation: '24.5%', return: '+8.1%', status: 'On Track', positive: true },
  { asset: 'BTC', allocation: '8.3%', return: '-3.2%', status: 'Review', positive: false },
  { asset: 'GOOGL', allocation: '14.7%', return: '+6.8%', status: 'On Track', positive: true },
  { asset: 'BND', allocation: '34.3%', return: '+2.1%', status: 'On Track', positive: true },
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

          {/* Right column - Showcase Table */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7, delay: 0.2, ease: 'easeOut' }}
          >
            <div className="bg-cx-surface-light border border-white/[0.08] rounded-sm p-6 shadow-card">
              <div className="flex items-center gap-2 mb-5">
                <span className="w-1.5 h-1.5 rounded-full bg-cx-gold" />
                <h5 className="text-cx-text-primary text-sm font-medium">Illustrative Portfolio Snapshot</h5>
              </div>
              <p className="text-cx-text-muted text-xs leading-relaxed mb-5">
                Example output for the current portfolio-health workflow, not a live connected account.
              </p>

              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-cx-charcoal">
                      {['Asset', 'Allocation', 'Return', 'Status'].map((h) => (
                        <th
                          key={h}
                          className="text-left text-cx-text-muted text-[0.7rem] uppercase tracking-[0.08em] font-medium px-3 py-2.5"
                        >
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.map((row, i) => (
                      <tr
                        key={row.asset}
                        className={i % 2 === 0 ? 'bg-cx-surface' : 'bg-cx-surface-light'}
                      >
                        <td className="px-3 py-2.5 text-cx-text-primary font-medium">{row.asset}</td>
                        <td className="px-3 py-2.5 text-cx-text-secondary">{row.allocation}</td>
                        <td className={`px-3 py-2.5 ${row.positive ? 'text-cx-positive' : 'text-cx-negative'}`}>
                          {row.return}
                        </td>
                        <td className="px-3 py-2.5">
                          <span
                            className={`inline-block text-[0.7rem] px-2 py-0.5 rounded-sm font-medium ${
                              row.status === 'Strong'
                                ? 'bg-cx-positive/10 text-cx-positive'
                                : row.status === 'Review'
                                ? 'bg-cx-gold/15 text-cx-gold'
                                : 'bg-cx-positive/10 text-cx-positive'
                            }`}
                          >
                            {row.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                    <tr className="border-t border-white/[0.08]">
                      <td className="px-3 py-3 text-cx-text-primary font-bold">Total Portfolio</td>
                      <td className="px-3 py-3 text-cx-text-secondary font-medium">100%</td>
                      <td className="px-3 py-3 text-cx-positive font-bold">+8.4%</td>
                      <td className="px-3 py-3">
                        <span className="inline-block text-[0.7rem] px-2 py-0.5 rounded-sm font-medium bg-cx-positive/10 text-cx-positive">
                          Strong
                        </span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  )
}

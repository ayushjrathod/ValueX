import { motion } from 'framer-motion'
import { Link, Cpu, Lightbulb } from 'lucide-react'

const steps = [
  {
    number: '01',
    title: 'Provide Holdings Data',
    body: 'Start with holdings data or a fixture portfolio. The current build does not connect to brokerages or sync accounts.',
    icon: Link,
  },
  {
    number: '02',
    title: 'Compute Portfolio Health',
    body: 'ValueX calculates concentration, return, and benchmark comparison in code, then uses the model to explain the results in plain language.',
    icon: Cpu,
  },
  {
    number: '03',
    title: 'Review the Output',
    body: 'You get structured observations and portfolio-health metrics for the current request. Live alerts and automatic monitoring are not part of this build.',
    icon: Lightbulb,
  },
]

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-cx-surface py-16 md:py-24">
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
            HOW IT WORKS
          </p>
          <h2
            className="text-cx-text-primary font-sans font-normal leading-[1.2] tracking-[-0.01em]"
            style={{ fontSize: 'clamp(1.75rem, 3vw, 2.5rem)' }}
          >
            What the Current Workflow Actually Does
          </h2>
        </motion.div>

        {/* Steps */}
        <div className="flex flex-col md:flex-row items-start gap-8 md:gap-0">
          {steps.map((step, i) => {
            const Icon = step.icon
            const isLast = i === steps.length - 1
            return (
              <div key={step.number} className="flex-1 flex items-start">
                <motion.div
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.5, delay: i * 0.2, ease: 'easeOut' }}
                  className="flex-1 text-center px-4"
                >
                  <span className="font-display text-cx-gold/60 text-5xl block mb-4">
                    {step.number}
                  </span>
                  <Icon className="w-6 h-6 text-cx-stone-dim mx-auto mb-4" strokeWidth={1.5} />
                  <h3 className="text-cx-text-primary text-lg font-medium mb-3">
                    {step.title}
                  </h3>
                  <p className="text-cx-text-secondary text-sm leading-relaxed max-w-[280px] mx-auto">
                    {step.body}
                  </p>
                </motion.div>

                {/* Connecting line (horizontal on desktop) */}
                {!isLast && (
                  <div className="hidden md:flex items-center justify-center w-20 flex-shrink-0 mt-12">
                    <div className="w-full h-px bg-white/[0.15] relative">
                      <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-1 bg-cx-gold rotate-45" />
                    </div>
                  </div>
                )}

                {/* Connecting line (vertical on mobile) */}
                {!isLast && (
                  <div className="flex md:hidden items-center justify-center w-full py-4">
                    <div className="h-10 w-px bg-white/[0.15] relative">
                      <span className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-1 h-1 bg-cx-gold rotate-45" />
                    </div>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

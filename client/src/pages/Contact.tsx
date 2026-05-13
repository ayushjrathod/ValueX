import { Link } from 'react-router'
import { ArrowLeft } from 'lucide-react'

const topics = [
  {
    heading: 'Bug reports and technical issues',
    body: 'Open an issue on the GitHub repository. Include the query you sent, the fixture user selected, and the response or error you received.',
  },
  {
    heading: 'Feature requests',
    body: 'Use GitHub Discussions to propose new agents, workflows, or output formats. Describe the use case and what existing tools fall short of solving it.',
  },
  {
    heading: 'Questions about the build',
    body: 'For questions about how the classifier, agents, or portfolio math work, start with the decisions log (decsions.md) and the fixtures README in the repository — most architectural choices are documented there.',
  },
  {
    heading: 'Everything else',
    body: 'Reach out via the repository. This is a prototype maintained by a small team, so responses may take a few days.',
  },
]

export default function Contact() {
  return (
    <main className="min-h-screen bg-cx-obsidian text-cx-text-primary">
      <div className="max-w-[720px] mx-auto px-6 py-16 md:py-24">
        <Link
          to="/"
          className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-cx-gold/80 hover:text-cx-gold transition-colors mb-12"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to home
        </Link>

        <p className="text-cx-gold text-xs tracking-[0.12em] uppercase font-medium mb-4">Get in touch</p>
        <h1
          className="font-display leading-[1.05] tracking-[-0.02em] mb-4"
          style={{ fontSize: 'clamp(2.5rem, 5vw, 4rem)' }}
        >
          Contact
        </h1>
        <p className="text-cx-text-muted text-sm mb-12">Prototype build</p>

        <p className="text-cx-text-secondary leading-relaxed mb-12">
          ValueX is a prototype. The best way to reach us is through the project repository on GitHub.
        </p>

        <div className="space-y-10">
          {topics.map((t) => (
            <div key={t.heading} className="border-t border-white/[0.08] pt-8">
              <h2 className="text-cx-text-primary text-base font-medium mb-3">{t.heading}</h2>
              <p className="text-cx-text-secondary text-sm leading-relaxed">{t.body}</p>
            </div>
          ))}
        </div>

        <div className="mt-16 border-t border-white/[0.08] pt-8">
          <p className="text-cx-text-muted text-sm">
            Looking to try the assistant?{' '}
            <Link to="/chat" className="text-cx-gold hover:text-cx-gold-dim transition-colors">
              Open ValueX
            </Link>
          </p>
        </div>
      </div>
    </main>
  )
}

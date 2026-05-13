import { Link } from 'react-router'
import { ArrowLeft } from 'lucide-react'

const sections = [
  {
    heading: 'What data we collect',
    body: 'ValueX does not collect personal data. The assistant runs against fixture user profiles stored locally in the backend. No account registration, login, or personal information is required or requested.',
  },
  {
    heading: 'Portfolio data',
    body: 'The portfolio holdings used in this build are pre-defined fixture datasets. You do not enter or upload real portfolio data. No brokerage accounts are connected, and no financial data you type into the chat is persisted between sessions.',
  },
  {
    heading: 'Conversation data',
    body: 'Chat messages are sent to an LLM API to generate observations. They are not stored server-side beyond the duration of the request. Conversation history is held in memory for the current session only and discarded when the session ends.',
  },
  {
    heading: 'Cookies and tracking',
    body: 'This prototype does not use cookies, analytics trackers, or third-party tracking scripts.',
  },
  {
    heading: 'Third-party services',
    body: 'Live price data is fetched from public market data sources (yfinance). LLM inference is provided by OpenAI. Neither service receives your identity — requests contain only ticker symbols and the text of your query.',
  },
  {
    heading: 'Changes to this policy',
    body: 'This is a prototype. If the product evolves into a live service with real user data, this policy will be updated before launch.',
  },
]

export default function Privacy() {
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

        <p className="text-cx-gold text-xs tracking-[0.12em] uppercase font-medium mb-4">Legal</p>
        <h1
          className="font-display leading-[1.05] tracking-[-0.02em] mb-4"
          style={{ fontSize: 'clamp(2.5rem, 5vw, 4rem)' }}
        >
          Privacy Policy
        </h1>
        <p className="text-cx-text-muted text-sm mb-12">Prototype build — last updated May 2025</p>

        <p className="text-cx-text-secondary leading-relaxed mb-12">
          ValueX is a prototype. It is not a live financial product and does not process real user accounts or real portfolio data. This policy describes how data is handled in the current build.
        </p>

        <div className="space-y-10">
          {sections.map((s) => (
            <div key={s.heading} className="border-t border-white/[0.08] pt-8">
              <h2 className="text-cx-text-primary text-base font-medium mb-3">{s.heading}</h2>
              <p className="text-cx-text-secondary text-sm leading-relaxed">{s.body}</p>
            </div>
          ))}
        </div>
      </div>
    </main>
  )
}

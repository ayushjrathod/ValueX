import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { Link } from 'react-router'
import { ArrowLeft, Check, Copy, LoaderCircle, RefreshCcw, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { buildApiUrl, streamChat, type ChatEventPayload, type ChatStreamEvent } from '@/lib/chat'

// ─── Types ───────────────────────────────────────────────────────────────────

type PortfolioProfile = {
  userId: string
  name: string
  label: string
  summary: string
  outlook: string
  riskProfile?: string
  preferredBenchmark?: string
  positionsCount?: number
}

type Observation = {
  severity?: string
  text?: string
}

type ConcentrationRisk = {
  top_position_pct?: number
  top_3_positions_pct?: number
  flag?: string
  notes?: string
}

type Performance = {
  total_return_pct?: number
  annualized_return_pct?: number | null
  notes?: string
}

type BenchmarkComparison = {
  benchmark?: string
  portfolio_return_pct?: number
  benchmark_return_pct?: number
  alpha_pct?: number
}

type Meta = {
  input_tokens?: number
  output_tokens?: number
}

type AgentResponse = {
  status?: string
  agent?: string
  intent?: string
  message?: string
  disclaimer?: string
  benchmark_note?: string
  observations?: Observation[]
  concentration_risk?: ConcentrationRisk
  performance?: Performance
  benchmark_comparison?: BenchmarkComparison
  _meta?: Meta
}

type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  content: string
  tone?: 'default' | 'error'
  agent?: string
}

type BackendUser = {
  user_id: string
  name: string
  country?: string
  risk_profile?: string
  positions_count?: number
  preferred_benchmark?: string
}

// ─── Constants ───────────────────────────────────────────────────────────────

const SESSION_KEY = 'valuex_chat'

const fallbackProfiles: PortfolioProfile[] = [
  {
    userId: 'usr_001',
    name: 'Alex Chen',
    label: 'Aggressive US investor',
    summary: 'Tech-heavy sample account with a growth-oriented risk profile.',
    outlook: 'A useful starting point for concentration, benchmark, and momentum questions.',
    riskProfile: 'aggressive',
  },
]

// ─── Module-level request caches ─────────────────────────────────────────────

let usersRequest: Promise<PortfolioProfile[]> | null = null
const userSummaryRequests = new Map<string, Promise<string>>()

function loadProfiles(): Promise<PortfolioProfile[]> {
  if (usersRequest) return usersRequest
  usersRequest = fetch(buildApiUrl('/users'))
    .then(async (res) => {
      if (!res.ok) throw new Error(`Users request failed with status ${res.status}`)
      const payload = (await res.json()) as { users?: BackendUser[] }
      const next = (payload.users ?? []).map(mapUserToProfile)
      return next.length > 0 ? next : fallbackProfiles
    })
    .catch((err) => { usersRequest = null; throw err })
  return usersRequest
}

function loadUserSummaryFor(userId: string, fallbackSummary: string): Promise<string> {
  const existing = userSummaryRequests.get(userId)
  if (existing) return existing
  const req = fetch(buildApiUrl(`/user-summary?user_id=${encodeURIComponent(userId)}`))
    .then(async (res) => {
      if (!res.ok) throw new Error(`User summary request failed with status ${res.status}`)
      const payload = (await res.json()) as { summary?: string }
      return payload.summary ?? fallbackSummary
    })
    .catch((err) => { userSummaryRequests.delete(userId); throw err })
  userSummaryRequests.set(userId, req)
  return req
}

// ─── Session storage helpers ──────────────────────────────────────────────────

type StoredSession = {
  sessionId?: string
  messages?: ChatMessage[]
  selectedProfileId?: string
}

function readStorage(): StoredSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY)
    return raw ? (JSON.parse(raw) as StoredSession) : null
  } catch {
    return null
  }
}

function writeStorage(data: StoredSession) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(data))
  } catch {}
}

// ─── Component ───────────────────────────────────────────────────────────────

export default function Chat() {
  const stored = useRef(readStorage())

  const [profiles, setProfiles] = useState<PortfolioProfile[]>(fallbackProfiles)
  const [selectedProfileId, setSelectedProfileId] = useState<string>(
    () => stored.current?.selectedProfileId ?? fallbackProfiles[0].userId,
  )
  const [query, setQuery] = useState('')
  const [sessionId, setSessionId] = useState<string>(
    () => stored.current?.sessionId ?? crypto.randomUUID(),
  )
  const [status, setStatus] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [latestResponse, setLatestResponse] = useState<AgentResponse | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>(
    () => stored.current?.messages ?? [createWelcomeMessage(fallbackProfiles[0])],
  )
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [usersLoading, setUsersLoading] = useState(true)
  const [userSummary, setUserSummary] = useState(fallbackProfiles[0].summary)
  const [userSummaryLoading, setUserSummaryLoading] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)

  const abortControllerRef = useRef<AbortController | null>(null)
  const conversationEndRef = useRef<HTMLDivElement | null>(null)

  const selectedProfile =
    profiles.find((p) => p.userId === selectedProfileId) ?? profiles[0] ?? fallbackProfiles[0]
  const latestObservations = latestResponse?.observations?.filter((o) => Boolean(o.text)) ?? []
  const totalTokens =
    (latestResponse?._meta?.input_tokens ?? 0) + (latestResponse?._meta?.output_tokens ?? 0)

  // Persist session to storage
  useEffect(() => {
    writeStorage({ sessionId, messages, selectedProfileId })
  }, [sessionId, messages, selectedProfileId])

  // Cleanup on unmount
  useEffect(() => {
    return () => { abortControllerRef.current?.abort() }
  }, [])

  // Load profiles
  useEffect(() => {
    let active = true
    async function load() {
      try {
        const next = await loadProfiles()
        if (!active || next.length === 0) return
        setProfiles(next)
        setSelectedProfileId((cur) =>
          next.some((p) => p.userId === cur) ? cur : next[0].userId,
        )
        // Only reset welcome message if no real conversation
        setMessages((cur) => (cur.length <= 1 ? [createWelcomeMessage(next[0])] : cur))
      } catch {
        if (active) setProfiles(fallbackProfiles)
      } finally {
        if (active) setUsersLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [])

  // Scroll to bottom
  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isStreaming])

  // Load user summary
  useEffect(() => {
    let active = true
    async function load() {
      setUserSummaryLoading(true)
      try {
        const summary = await loadUserSummaryFor(selectedProfile.userId, selectedProfile.summary)
        if (active) setUserSummary(summary)
      } catch {
        if (active) setUserSummary(selectedProfile.summary)
      } finally {
        if (active) setUserSummaryLoading(false)
      }
    }
    void load()
    return () => { active = false }
  }, [selectedProfile.userId])

  // ─── Submission ────────────────────────────────────────────────────────────

  async function submitQuery(trimmedQuery: string) {
    if (!trimmedQuery || isStreaming) return

    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setIsStreaming(true)
    setStatus('Reviewing your request')
    setErrorMessage(null)
    setMessages((cur) => [...cur, { id: crypto.randomUUID(), role: 'user', content: trimmedQuery }])
    setQuery('')

    try {
      await streamChat(
        { query: trimmedQuery, user_id: selectedProfile.userId, session_id: sessionId },
        { signal: controller.signal, onEvent: handleEvent },
      )
    } catch (err) {
      if (controller.signal.aborted) {
        setStatus('Conversation paused')
      } else {
        const msg = err instanceof Error ? err.message : 'Unknown error'
        setErrorMessage(msg)
        setMessages((cur) => [
          ...cur,
          { id: crypto.randomUUID(), role: 'assistant', content: msg, tone: 'error' },
        ])
        setStatus('We hit a snag')
      }
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void submitQuery(query.trim())
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      void submitQuery(query.trim())
    }
  }

  function handleEvent(event: ChatStreamEvent) {
    switch (event.event) {
      case 'metadata':
      case 'progress':
        setStatus(readableStage(event.data.stage) ?? 'Working on it')
        break
      case 'message': {
        const response = event.data as AgentResponse
        setLatestResponse(response)
        setErrorMessage(null)
        setMessages((cur) => [
          ...cur,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: responseToCopy(response),
            agent: response.agent,
          },
        ])
        setStatus('Answer ready')
        break
      }
      case 'error':
      case 'safety_blocked': {
        const msg = errorToCopy(event.data)
        setErrorMessage(msg)
        setMessages((cur) => [
          ...cur,
          { id: crypto.randomUUID(), role: 'assistant', content: msg, tone: 'error' },
        ])
        setStatus('Unable to answer that')
        break
      }
      case 'done':
        setStatus(
          (event.data.status as string | undefined) === 'ok'
            ? 'Ready for a follow-up'
            : 'Try another question',
        )
        break
    }
  }

  function stopStreaming() {
    abortControllerRef.current?.abort()
  }

  function resetConversation(profile: PortfolioProfile) {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setSelectedProfileId(profile.userId)
    setSessionId(crypto.randomUUID())
    setQuery('')
    setLatestResponse(null)
    setErrorMessage(null)
    setIsStreaming(false)
    setStatus('')
    setMessages([createWelcomeMessage(profile)])
  }

  async function copyMessage(id: string, content: string) {
    try {
      await navigator.clipboard.writeText(content)
      setCopiedId(id)
      setTimeout(() => setCopiedId((prev) => (prev === id ? null : prev)), 2000)
    } catch {}
  }

  // ─── Render ────────────────────────────────────────────────────────────────

  const prompts = starterPromptsFor(selectedProfile)

  return (
    <main className="min-h-screen bg-[#0a0c0f] text-cx-text-primary">
      <div className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 lg:px-10">

        {/* Header */}
        <header className="grid gap-6 border-b border-white/10 pb-8 lg:grid-cols-[1.3fr_0.7fr] lg:items-end">
          <div className="max-w-3xl space-y-4">
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-xs uppercase tracking-[0.22em] text-cx-gold/80 transition-colors hover:text-cx-gold"
            >
              <ArrowLeft className="size-3.5" />
              Back to overview
            </Link>
            <p className="text-xs font-medium uppercase tracking-[0.24em] text-cx-gold/80">
              ValueX Assistant
            </p>
            <h1 className="font-display text-4xl leading-none tracking-[-0.04em] text-white md:text-6xl">
              Ask clear questions. Get direct financial answers.
            </h1>
            <p className="max-w-2xl text-sm leading-7 text-cx-text-secondary md:text-base">
              Pick a sample context, ask what matters, and get a plain-language answer routed through the
              right workflow for this build.
            </p>
          </div>

          <div className="grid gap-4 rounded-[28px] border border-white/10 bg-[linear-gradient(160deg,rgba(201,169,110,0.08),rgba(255,255,255,0.03))] p-5 text-sm backdrop-blur">
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-cx-text-muted">Selected user</p>
              <label className="mt-3 grid gap-2 text-sm text-cx-text-secondary">
                User
                <select
                  value={selectedProfile.userId}
                  onChange={(e) => {
                    const next = profiles.find((p) => p.userId === e.target.value)
                    if (next) resetConversation(next)
                  }}
                  className="h-12 rounded-[18px] border border-white/10 bg-black/20 px-4 text-sm text-cx-text-primary outline-none transition focus:border-cx-gold/40 focus:ring-2 focus:ring-cx-gold/20"
                  disabled={usersLoading || profiles.length === 0}
                >
                  {profiles.map((p) => (
                    <option key={p.userId} value={p.userId}>
                      {p.name} · {p.label}
                    </option>
                  ))}
                </select>
              </label>
              <p className="mt-2 text-lg font-medium text-white">{selectedProfile.label}</p>
              <p className="mt-1 text-sm leading-6 text-cx-text-secondary">{selectedProfile.summary}</p>
            </div>
            <p className="text-sm leading-6 text-cx-text-secondary">{selectedProfile.outlook}</p>
          </div>
        </header>

        {/* Main grid */}
        <section className="grid gap-6 py-8 lg:grid-cols-[1.18fr_0.82fr]">

          {/* Chat panel */}
          <Card className="border-white/10 bg-white/[0.03] py-0 shadow-[0_20px_80px_rgba(0,0,0,0.35)]">
            <CardContent className="flex h-full flex-col gap-6 px-0 py-0">

              {/* Starter prompts */}
              <div className="flex flex-col gap-5 border-b border-white/10 px-6 py-6">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-lg font-medium text-white">Talk through an investing question</p>
                    <p className="mt-1 text-sm leading-6 text-cx-text-secondary">
                      Pick a fixture user, then keep asking follow-up questions in the same conversation.
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="h-11 rounded-full border-white/15 bg-transparent px-5 text-cx-text-primary hover:bg-white/5"
                    onClick={() => resetConversation(selectedProfile)}
                    disabled={isStreaming}
                  >
                    <RefreshCcw className="size-4" />
                    New conversation
                  </Button>
                </div>

                <div className="flex flex-wrap gap-3">
                  {prompts.map((prompt) => (
                    <button
                      key={prompt}
                      type="button"
                      onClick={() => setQuery(prompt)}
                      className="rounded-full border border-white/10 bg-black/20 px-4 py-2 text-left text-xs leading-5 text-cx-text-secondary transition hover:border-cx-gold/30 hover:bg-cx-gold/10 hover:text-cx-text-primary"
                    >
                      {prompt}
                    </button>
                  ))}
                </div>
              </div>

              {/* Messages */}
              <div className="flex-1 space-y-4 overflow-y-auto px-6 py-1">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
                  >
                    <div
                      className={[
                        'group relative max-w-[90%] rounded-[24px] px-5 py-4 text-sm leading-7 shadow-[0_18px_45px_rgba(0,0,0,0.18)] md:max-w-[82%]',
                        message.role === 'user'
                          ? 'bg-cx-gold text-cx-obsidian'
                          : message.tone === 'error'
                          ? 'border border-red-500/20 bg-red-500/10 text-red-50'
                          : 'border border-white/10 bg-white/[0.04] text-cx-text-primary',
                      ].join(' ')}
                    >
                      {message.role === 'assistant' ? (
                        <div className="mb-2 flex items-center justify-between gap-3">
                          <p className="text-[0.68rem] font-medium uppercase tracking-[0.22em] text-cx-gold/80">
                            ValueX
                            {message.agent ? (
                              <span className="ml-2 normal-case tracking-normal text-cx-text-muted/60">
                                · {agentLabel(message.agent)}
                              </span>
                            ) : null}
                          </p>
                          <button
                            type="button"
                            onClick={() => void copyMessage(message.id, message.content)}
                            className="opacity-0 group-hover:opacity-100 transition-opacity text-cx-text-muted hover:text-cx-text-primary"
                            aria-label="Copy message"
                          >
                            {copiedId === message.id ? (
                              <Check className="size-3.5 text-cx-gold" />
                            ) : (
                              <Copy className="size-3.5" />
                            )}
                          </button>
                        </div>
                      ) : null}
                      <p className="whitespace-pre-wrap">{message.content}</p>
                    </div>
                  </div>
                ))}

                {isStreaming ? (
                  <div className="flex justify-start">
                    <div className="rounded-[24px] border border-white/10 bg-white/[0.04] px-5 py-4 text-sm text-cx-text-secondary shadow-[0_18px_45px_rgba(0,0,0,0.18)]">
                      <p className="mb-2 text-[0.68rem] font-medium uppercase tracking-[0.22em] text-cx-gold/80">ValueX</p>
                      <div className="flex items-center gap-2">
                        <LoaderCircle className="size-4 animate-spin text-cx-gold" />
                        <span>{status}</span>
                      </div>
                    </div>
                  </div>
                ) : null}

                <div ref={conversationEndRef} />
              </div>

              {/* Input form */}
              <form className="border-t border-white/10 px-6 py-6" onSubmit={handleSubmit}>
                <label className="grid gap-3 text-sm text-cx-text-secondary">
                  Ask ValueX
                  <textarea
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    onKeyDown={handleKeyDown}
                    className="min-h-32 rounded-[24px] border border-white/10 bg-black/20 px-4 py-4 text-base leading-7 text-cx-text-primary outline-none transition focus:border-cx-gold/40 focus:ring-2 focus:ring-cx-gold/20"
                    placeholder="Ask what matters and ValueX will answer with the best workflow available in this build."
                  />
                </label>

                <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm leading-6 text-cx-text-muted">
                    Using fixture user <span className="text-cx-text-primary">{selectedProfile.name}</span>.{' '}
                    <span className="text-cx-text-muted/60">⌘↵ to send</span>
                  </p>
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <Button
                      type="button"
                      variant="ghost"
                      className="h-11 rounded-full px-5 text-cx-text-secondary hover:bg-white/5 hover:text-cx-text-primary"
                      onClick={stopStreaming}
                      disabled={!isStreaming}
                    >
                      Stop
                    </Button>
                    <Button
                      type="submit"
                      className="h-11 min-w-40 rounded-full px-6"
                      disabled={isStreaming || !query.trim()}
                    >
                      {isStreaming ? <LoaderCircle className="size-4 animate-spin" /> : <Sparkles className="size-4" />}
                      Ask ValueX
                    </Button>
                  </div>
                </div>
              </form>
            </CardContent>
          </Card>

          {/* Sidebar */}
          <div className="grid content-start gap-6">

            {/* Highlights card */}
            <Card className="border-white/10 bg-white/[0.03] py-0">
              <CardContent className="space-y-4 px-6 py-6">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs uppercase tracking-[0.2em] text-cx-gold/80">Latest answer</p>
                    <h2 className="mt-2 text-2xl font-medium text-white">Highlights</h2>
                  </div>
                  {latestResponse?.agent ? (
                    <span className="mt-2 rounded-sm border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[0.68rem] uppercase tracking-[0.1em] text-cx-text-muted">
                      {agentLabel(latestResponse.agent)}
                    </span>
                  ) : null}
                </div>

                {latestResponse ? (
                  <div className="space-y-3">

                    {/* Metrics strip */}
                    {(latestResponse.concentration_risk || latestResponse.performance) ? (
                      <div className="rounded-[18px] border border-white/[0.06] bg-black/20 px-4 py-3 space-y-2">
                        {latestResponse.concentration_risk && (
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-cx-text-muted uppercase tracking-[0.08em]">Concentration</span>
                            <div className="flex items-center gap-3">
                              <span className="text-cx-text-secondary">
                                Top: <span className="text-cx-text-primary font-medium">{latestResponse.concentration_risk.top_position_pct}%</span>
                              </span>
                              <span className="text-cx-text-secondary">
                                Top 3: <span className="text-cx-text-primary font-medium">{latestResponse.concentration_risk.top_3_positions_pct}%</span>
                              </span>
                              <span className={`rounded-sm px-1.5 py-0.5 text-[0.65rem] font-medium uppercase ${flagStyle(latestResponse.concentration_risk.flag)}`}>
                                {latestResponse.concentration_risk.flag}
                              </span>
                            </div>
                          </div>
                        )}
                        {latestResponse.performance && (
                          <div className="flex items-center justify-between text-xs">
                            <span className="text-cx-text-muted uppercase tracking-[0.08em]">Return</span>
                            <div className="flex items-center gap-3">
                              <span className="text-cx-text-secondary">
                                Total:{' '}
                                <span className={`font-medium ${(latestResponse.performance.total_return_pct ?? 0) >= 0 ? 'text-cx-positive' : 'text-cx-negative'}`}>
                                  {(latestResponse.performance.total_return_pct ?? 0) >= 0 ? '+' : ''}{latestResponse.performance.total_return_pct}%
                                </span>
                              </span>
                              {latestResponse.performance.annualized_return_pct != null && (
                                <span className="text-cx-text-secondary">
                                  Ann.:{' '}
                                  <span className={`font-medium ${(latestResponse.performance.annualized_return_pct ?? 0) >= 0 ? 'text-cx-positive' : 'text-cx-negative'}`}>
                                    {(latestResponse.performance.annualized_return_pct ?? 0) >= 0 ? '+' : ''}{latestResponse.performance.annualized_return_pct}%
                                  </span>
                                </span>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : null}

                    {/* Observations */}
                    {latestObservations.length ? (
                      latestObservations.slice(0, 3).map((item, index) => (
                        <div
                          key={`${item.text ?? 'obs'}-${index}`}
                          className="rounded-[22px] border border-white/10 bg-black/20 p-4"
                        >
                          <p className="text-[0.68rem] font-medium uppercase tracking-[0.2em] text-cx-gold/80">
                            {observationLabel(item.severity, index)}
                          </p>
                          <p className="mt-2 text-sm leading-7 text-cx-text-primary">{item.text}</p>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-[22px] border border-white/10 bg-black/20 p-4 text-sm leading-7 text-cx-text-primary">
                        {latestResponse.message ?? 'Your next answer will show up here with the clearest takeaways first.'}
                      </div>
                    )}

                    {/* Benchmark comparison */}
                    {latestResponse.benchmark_comparison ? (
                      <div className="rounded-[18px] border border-white/[0.06] bg-black/20 px-4 py-3">
                        <p className="text-[0.65rem] uppercase tracking-[0.1em] text-cx-text-muted mb-2">
                          vs {latestResponse.benchmark_comparison.benchmark}
                        </p>
                        <div className="grid grid-cols-3 gap-2 text-center text-xs">
                          <div>
                            <p className="text-cx-text-muted mb-0.5">Portfolio</p>
                            <p className={`font-medium ${(latestResponse.benchmark_comparison.portfolio_return_pct ?? 0) >= 0 ? 'text-cx-positive' : 'text-cx-negative'}`}>
                              {(latestResponse.benchmark_comparison.portfolio_return_pct ?? 0) >= 0 ? '+' : ''}{latestResponse.benchmark_comparison.portfolio_return_pct}%
                            </p>
                          </div>
                          <div>
                            <p className="text-cx-text-muted mb-0.5">Benchmark</p>
                            <p className={`font-medium ${(latestResponse.benchmark_comparison.benchmark_return_pct ?? 0) >= 0 ? 'text-cx-positive' : 'text-cx-negative'}`}>
                              {(latestResponse.benchmark_comparison.benchmark_return_pct ?? 0) >= 0 ? '+' : ''}{latestResponse.benchmark_comparison.benchmark_return_pct}%
                            </p>
                          </div>
                          <div>
                            <p className="text-cx-text-muted mb-0.5">Alpha</p>
                            <p className={`font-medium ${(latestResponse.benchmark_comparison.alpha_pct ?? 0) >= 0 ? 'text-cx-positive' : 'text-cx-negative'}`}>
                              {(latestResponse.benchmark_comparison.alpha_pct ?? 0) >= 0 ? '+' : ''}{latestResponse.benchmark_comparison.alpha_pct}%
                            </p>
                          </div>
                        </div>
                      </div>
                    ) : null}

                    {/* Benchmark unavailable note */}
                    {latestResponse.benchmark_note ? (
                      <p className="rounded-[22px] border border-white/10 bg-white/[0.03] p-4 text-sm leading-6 text-cx-text-muted">
                        {latestResponse.benchmark_note}
                      </p>
                    ) : null}

                    {/* Disclaimer */}
                    {latestResponse.disclaimer ? (
                      <p className="rounded-[22px] border border-cx-gold/20 bg-cx-gold/10 p-4 text-sm leading-6 text-cx-text-primary">
                        {latestResponse.disclaimer}
                      </p>
                    ) : null}

                    {/* Token count */}
                    {totalTokens > 0 ? (
                      <p className="text-right text-[0.65rem] text-cx-text-muted/50">
                        {totalTokens.toLocaleString()} tokens used
                      </p>
                    ) : null}

                  </div>
                ) : (
                  <div className="rounded-[22px] border border-dashed border-white/10 bg-black/10 p-5 text-sm leading-7 text-cx-text-muted">
                    Ask a question to turn this panel into a concise summary of what matters most in the current response.
                  </div>
                )}
              </CardContent>
            </Card>

            {/* User card */}
            <Card className="border-white/10 bg-white/[0.03] py-0">
              <CardContent className="space-y-4 px-6 py-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-cx-gold/80">About this user</p>
                  <h2 className="mt-2 text-xl font-medium text-white">{selectedProfile.name}</h2>
                </div>
                <p className="text-sm leading-7 text-cx-text-secondary">
                  {userSummaryLoading ? 'Preparing a fresh summary for this user...' : userSummary}
                </p>
                <p className="text-sm leading-7 text-cx-text-secondary">{selectedProfile.outlook}</p>
                <div className="rounded-[22px] border border-white/10 bg-black/20 p-4 text-sm leading-7 text-cx-text-primary">
                  Try follow-ups like "What matters most here?" or "Explain that without finance jargon."
                </div>
                {errorMessage ? (
                  <div className="rounded-[22px] border border-red-500/20 bg-red-500/10 p-4 text-sm leading-6 text-red-50">
                    {errorMessage}
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </section>
      </div>
    </main>
  )
}

// ─── Helper functions ─────────────────────────────────────────────────────────

function createWelcomeMessage(profile: PortfolioProfile): ChatMessage {
  return {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: `You're chatting with ValueX using ${profile.name}'s fixture data. Ask what matters, follow up naturally, and I'll answer with the best workflow available in this build.`,
  }
}

function mapUserToProfile(user: BackendUser): PortfolioProfile {
  const labelParts = [toTitleCase(user.risk_profile), user.country].filter(Boolean)
  const label = labelParts.length > 0 ? labelParts.join(' · ') : 'Available user'
  const summaryParts = [
    typeof user.positions_count === 'number' ? `${user.positions_count} positions` : null,
    user.preferred_benchmark ? `benchmark ${user.preferred_benchmark}` : null,
  ].filter(Boolean)
  return {
    userId: user.user_id,
    name: user.name,
    label,
    summary: summaryParts.length > 0 ? summaryParts.join(' · ') : 'Available fixture user.',
    outlook: 'Use this fixture user to ask follow-ups and inspect how the backend responds to different account shapes.',
    riskProfile: user.risk_profile,
    preferredBenchmark: user.preferred_benchmark,
    positionsCount: user.positions_count,
  }
}

function starterPromptsFor(profile: PortfolioProfile): string[] {
  const prompts: string[] = [
    'What is the biggest concentration risk in this portfolio?',
    'Summarize this portfolio\'s main risk in plain English.',
  ]

  prompts.push(
    profile.preferredBenchmark
      ? `How does this portfolio compare to ${profile.preferredBenchmark}?`
      : 'What stands out versus the benchmark?',
  )

  const risk = (profile.riskProfile ?? '').toLowerCase()
  if (profile.positionsCount === 0) {
    prompts.push('What should I consider when starting to invest?')
  } else if (risk.includes('aggressive')) {
    prompts.push('Which position is contributing the most to overall risk?')
  } else if (risk.includes('retiree') || risk.includes('conservative') || risk.includes('income')) {
    prompts.push('Is the income and bond allocation appropriate for this risk profile?')
  } else {
    prompts.push('Explain this portfolio\'s biggest concern without finance jargon.')
  }

  return prompts
}

function responseToCopy(response: AgentResponse): string {
  if (response.message?.trim()) return response.message
  const observations = response.observations?.map((o) => o.text).filter(Boolean)
  if (observations?.length) return observations.join('\n\n')
  if (response.status === 'not_implemented') {
    return 'That request falls outside the workflows available in this build. Try another investing question or rephrase what you need.'
  }
  return 'I reviewed the request and prepared a new set of takeaways.'
}

function errorToCopy(payload: ChatEventPayload): string {
  const message = payload.message
  if (typeof message === 'string' && message.trim()) return message
  return 'I could not complete that request. Please try a different question.'
}

function observationLabel(severity: string | undefined, index: number): string {
  if (severity === 'warning') return 'Watch item'
  if (severity === 'positive') return 'What is working'
  return index === 0 ? 'What matters most' : 'Additional context'
}

function agentLabel(agent: string): string {
  const map: Record<string, string> = {
    portfolio_health: 'Portfolio Analysis',
    general_query: 'General',
    market_research: 'Market Research',
    investment_strategy: 'Strategy',
    financial_planning: 'Planning',
    financial_calculator: 'Calculator',
    risk_assessment: 'Risk',
    product_recommendation: 'Recommendations',
    customer_support: 'Support',
  }
  return map[agent] ?? agent
}

function flagStyle(flag: string | undefined): string {
  if (flag === 'high') return 'bg-cx-negative/10 text-cx-negative'
  if (flag === 'warning') return 'bg-cx-gold/15 text-cx-gold'
  return 'bg-cx-positive/10 text-cx-positive'
}

function readableStage(stage: unknown): string | null {
  if (typeof stage !== 'string') return null
  switch (stage) {
    case 'safety_guard': return 'Checking your question'
    case 'classifier': return 'Choosing the right analysis'
    case 'agent_dispatch': return 'Preparing an answer'
    default:
      return stage.split('_').map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' ')
  }
}

function toTitleCase(value: string | undefined): string | null {
  if (!value) return null
  return value.split('_').map((p) => p.charAt(0).toUpperCase() + p.slice(1)).join(' ')
}

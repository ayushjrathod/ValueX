import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router'
import { ArrowLeft, LoaderCircle, RefreshCcw, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { buildApiUrl, streamChat, type ChatEventPayload, type ChatStreamEvent } from '@/lib/chat'

type PortfolioProfile = {
  userId: string
  name: string
  label: string
  summary: string
  outlook: string
}

type Observation = {
  severity?: string
  text?: string
}

type AgentResponse = {
  status?: string
  agent?: string
  intent?: string
  message?: string
  disclaimer?: string
  observations?: Observation[]
}

type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  content: string
  tone?: 'default' | 'error'
}

const fallbackProfiles: PortfolioProfile[] = [
  {
    userId: 'usr_001',
    name: 'Alex Chen',
    label: 'Aggressive US investor',
    summary: 'Tech-heavy sample account with a growth-oriented risk profile.',
    outlook: 'A useful starting point for concentration, benchmark, and momentum questions.',
  },
]

const starterPrompts = [
  'What is the biggest concentration risk in this portfolio?',
  'Summarize this portfolio’s main risk in plain English.',
  'What stands out versus the benchmark?',
  'Explain this portfolio’s biggest concern without finance jargon.',
]

let usersRequest: Promise<PortfolioProfile[]> | null = null
const userSummaryRequests = new Map<string, Promise<string>>()

function loadProfiles(): Promise<PortfolioProfile[]> {
  if (usersRequest) {
    return usersRequest
  }

  usersRequest = fetch(buildApiUrl('/users'))
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`Users request failed with status ${response.status}`)
      }

      const payload = (await response.json()) as { users?: BackendUser[] }
      const nextProfiles = (payload.users ?? []).map(mapUserToProfile)
      return nextProfiles.length > 0 ? nextProfiles : fallbackProfiles
    })
    .catch((error) => {
      usersRequest = null
      throw error
    })

  return usersRequest
}

function loadUserSummaryFor(userId: string, fallbackSummary: string): Promise<string> {
  const existingRequest = userSummaryRequests.get(userId)
  if (existingRequest) {
    return existingRequest
  }

  const request = fetch(buildApiUrl(`/user-summary?user_id=${encodeURIComponent(userId)}`))
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`User summary request failed with status ${response.status}`)
      }

      const payload = (await response.json()) as { summary?: string }
      return payload.summary ?? fallbackSummary
    })
    .catch((error) => {
      userSummaryRequests.delete(userId)
      throw error
    })

  userSummaryRequests.set(userId, request)
  return request
}

export default function Chat() {
  const [profiles, setProfiles] = useState<PortfolioProfile[]>(fallbackProfiles)
  const [selectedProfileId, setSelectedProfileId] = useState(fallbackProfiles[0].userId)
  const [query, setQuery] = useState('')
  const [sessionId, setSessionId] = useState<string>(() => crypto.randomUUID())
  const [status, setStatus] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [latestResponse, setLatestResponse] = useState<AgentResponse | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>(() => [createWelcomeMessage(fallbackProfiles[0])])
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [usersLoading, setUsersLoading] = useState(true)
  const [userSummary, setUserSummary] = useState(fallbackProfiles[0].summary)
  const [userSummaryLoading, setUserSummaryLoading] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const conversationEndRef = useRef<HTMLDivElement | null>(null)

  const selectedProfile = profiles.find((profile) => profile.userId === selectedProfileId) ?? profiles[0] ?? fallbackProfiles[0]
  const latestObservations = latestResponse?.observations?.filter((item) => Boolean(item.text)) ?? []

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort()
    }
  }, [])

  useEffect(() => {
    let isActive = true

    async function loadUsers() {
      try {
        const nextProfiles = await loadProfiles()
        if (!isActive || nextProfiles.length === 0) {
          return
        }

        setProfiles(nextProfiles)
        setSelectedProfileId((current) => {
          if (nextProfiles.some((profile) => profile.userId === current)) {
            return current
          }
          return nextProfiles[0].userId
        })
        setMessages([createWelcomeMessage(nextProfiles[0])])
      } catch {
        if (isActive) {
          setProfiles(fallbackProfiles)
        }
      } finally {
        if (isActive) {
          setUsersLoading(false)
        }
      }
    }

    void loadUsers()

    return () => {
      isActive = false
    }
  }, [])

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isStreaming])

  useEffect(() => {
    let isActive = true

    async function loadUserSummary() {
      setUserSummaryLoading(true)
      try {
        const summary = await loadUserSummaryFor(selectedProfile.userId, selectedProfile.summary)
        if (isActive) {
          setUserSummary(summary)
        }
      } catch {
        if (isActive) {
          setUserSummary(selectedProfile.summary)
        }
      } finally {
        if (isActive) {
          setUserSummaryLoading(false)
        }
      }
    }

    void loadUserSummary()

    return () => {
      isActive = false
    }
  }, [selectedProfile.userId])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    const trimmedQuery = query.trim()
    if (!trimmedQuery || isStreaming) {
      return
    }

    abortControllerRef.current?.abort()
    const controller = new AbortController()
    abortControllerRef.current = controller

    setIsStreaming(true)
    setStatus('Reviewing your request')
    setErrorMessage(null)
    setMessages((current) => [
      ...current,
      {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmedQuery,
      },
    ])
    setQuery('')

    try {
      await streamChat(
        {
          query: trimmedQuery,
          user_id: selectedProfile.userId,
          session_id: sessionId,
        },
        {
          signal: controller.signal,
          onEvent: handleEvent,
        },
      )
    } catch (streamError) {
      if (controller.signal.aborted) {
        setStatus('Conversation paused')
      } else {
        const messageText = streamError instanceof Error ? streamError.message : 'Unknown error'
        setErrorMessage(messageText)
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: messageText,
            tone: 'error',
          },
        ])
        setStatus('We hit a snag')
      }
    } finally {
      setIsStreaming(false)
      abortControllerRef.current = null
    }
  }

  function handleEvent(event: ChatStreamEvent) {
    switch (event.event) {
      case 'metadata':
        setStatus(readableStage(event.data.stage) ?? 'Working on it')
        break
      case 'progress':
        setStatus(readableStage(event.data.stage) ?? 'Working on it')
        break
      case 'message': {
        const response = event.data as AgentResponse
        setLatestResponse(response)
        setErrorMessage(null)
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: responseToCopy(response),
          },
        ])
        setStatus('Answer ready')
        break
      }
      case 'error':
      case 'safety_blocked': {
        const nextError = errorToCopy(event.data)
        setErrorMessage(nextError)
        setMessages((current) => [
          ...current,
          {
            id: crypto.randomUUID(),
            role: 'assistant',
            content: nextError,
            tone: 'error',
          },
        ])
        setStatus('Unable to answer that')
        break
      }
      case 'metrics':
        break
      case 'done':
        setStatus((event.data.status as string | undefined) === 'ok' ? 'Ready for a follow-up' : 'Try another question')
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

  return (
    <main className="min-h-screen bg-[#0a0c0f] text-cx-text-primary">
      <div className="mx-auto min-h-screen w-full max-w-7xl px-6 py-8 lg:px-10">
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
                  onChange={(event) => {
                    const nextProfile = profiles.find((profile) => profile.userId === event.target.value)
                    if (nextProfile) {
                      resetConversation(nextProfile)
                    }
                  }}
                  className="h-12 rounded-[18px] border border-white/10 bg-black/20 px-4 text-sm text-cx-text-primary outline-none transition focus:border-cx-gold/40 focus:ring-2 focus:ring-cx-gold/20"
                  disabled={usersLoading || profiles.length === 0}
                >
                  {profiles.map((profile) => (
                    <option key={profile.userId} value={profile.userId}>
                      {profile.name} · {profile.label}
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

        <section className="grid gap-6 py-8 lg:grid-cols-[1.18fr_0.82fr]">
          <Card className="border-white/10 bg-white/[0.03] py-0 shadow-[0_20px_80px_rgba(0,0,0,0.35)]">
            <CardContent className="flex h-full flex-col gap-6 px-0 py-0">
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
                  {starterPrompts.map((prompt) => (
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

              <div className="flex-1 space-y-4 overflow-y-auto px-6 py-1">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}
                  >
                    <div
                      className={[
                        'max-w-[90%] rounded-[24px] px-5 py-4 text-sm leading-7 shadow-[0_18px_45px_rgba(0,0,0,0.18)] md:max-w-[82%]',
                        message.role === 'user'
                          ? 'bg-cx-gold text-cx-obsidian'
                          : message.tone === 'error'
                          ? 'border border-red-500/20 bg-red-500/10 text-red-50'
                          : 'border border-white/10 bg-white/[0.04] text-cx-text-primary',
                      ].join(' ')}
                    >
                      {message.role === 'assistant' ? (
                        <p className="mb-2 text-[0.68rem] font-medium uppercase tracking-[0.22em] text-cx-gold/80">
                          ValueX
                        </p>
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

              <form className="border-t border-white/10 px-6 py-6" onSubmit={handleSubmit}>
                <label className="grid gap-3 text-sm text-cx-text-secondary">
                  Ask ValueX
                  <textarea
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    className="min-h-32 rounded-[24px] border border-white/10 bg-black/20 px-4 py-4 text-base leading-7 text-cx-text-primary outline-none transition focus:border-cx-gold/40 focus:ring-2 focus:ring-cx-gold/20"
                    placeholder="Ask what matters and ValueX will answer with the best workflow available in this build."
                  />
                </label>

                <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-sm leading-6 text-cx-text-muted">
                    Using fixture user <span className="text-cx-text-primary">{selectedProfile.name}</span>.
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

          <div className="grid content-start gap-6">
            <Card className="border-white/10 bg-white/[0.03] py-0">
              <CardContent className="space-y-5 px-6 py-6">
                <div>
                  <p className="text-xs uppercase tracking-[0.2em] text-cx-gold/80">Latest answer</p>
                  <h2 className="mt-2 text-2xl font-medium text-white">Highlights</h2>
                </div>

                {latestResponse ? (
                  <div className="space-y-4">
                    {latestObservations.length ? (
                      latestObservations.slice(0, 3).map((item, index) => (
                        <div key={`${item.text ?? 'observation'}-${index}`} className="rounded-[22px] border border-white/10 bg-black/20 p-4">
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

                    {latestResponse.disclaimer ? (
                      <p className="rounded-[22px] border border-cx-gold/20 bg-cx-gold/10 p-4 text-sm leading-6 text-cx-text-primary">
                        {latestResponse.disclaimer}
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
                  Try follow-ups like “What matters most here?” or “Explain that without finance jargon.”
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

type BackendUser = {
  user_id: string
  name: string
  country?: string
  risk_profile?: string
  positions_count?: number
  preferred_benchmark?: string
}

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
  }
}

function responseToCopy(response: AgentResponse) {
  if (response.message?.trim()) {
    return response.message
  }

  const observations = response.observations?.map((item) => item.text).filter(Boolean)
  if (observations?.length) {
    return observations.join('\n\n')
  }

  if (response.status === 'not_implemented') {
    return 'That request falls outside the workflows available in this build. Try another investing question or rephrase what you need.'
  }

  return 'I reviewed the request and prepared a new set of takeaways.'
}

function errorToCopy(payload: ChatEventPayload) {
  const message = payload.message
  if (typeof message === 'string' && message.trim()) {
    return message
  }
  return 'I could not complete that request. Please try a different question.'
}

function observationLabel(severity: string | undefined, index: number) {
  if (severity === 'warning') {
    return 'Watch item'
  }
  if (severity === 'positive') {
    return 'What is working'
  }
  return index === 0 ? 'What matters most' : 'Additional context'
}

function readableStage(stage: unknown) {
  if (typeof stage !== 'string') {
    return null
  }

  switch (stage) {
    case 'safety_guard':
      return 'Checking your question'
    case 'classifier':
      return 'Choosing the right analysis'
    case 'agent_dispatch':
      return 'Preparing an answer'
    default:
      return stage
        .split('_')
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(' ')
  }
}

function toTitleCase(value: string | undefined) {
  if (!value) {
    return null
  }

  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

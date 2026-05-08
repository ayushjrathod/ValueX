export type ChatRequest = {
  query: string
  user_id?: string
  session_id?: string
}

export type ChatEventName = 'metadata' | 'progress' | 'message' | 'metrics' | 'error' | 'done' | 'safety_blocked'

export type ChatEventPayload = Record<string, unknown>

export type ChatStreamEvent = {
  event: ChatEventName
  data: ChatEventPayload
}

import { apiUrl } from '@/lib/api'

type StreamHandlers = {
  signal?: AbortSignal
  onEvent: (event: ChatStreamEvent) => void
}

export async function streamChat(
  request: ChatRequest,
  { signal, onEvent }: StreamHandlers,
) {
  const response = await fetch(apiUrl('/chat'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    },
    body: JSON.stringify(request),
    signal,
  })

  if (!response.ok) {
    throw new Error(`Chat request failed with status ${response.status}`)
  }

  if (!response.body) {
    throw new Error('Streaming response body is unavailable.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })

    const frames = buffer.split(/\r?\n\r?\n/)
    buffer = frames.pop() ?? ''

    for (const frame of frames) {
      const parsedEvent = parseSseFrame(frame)
      if (parsedEvent) {
        onEvent(parsedEvent)
      }
    }

    if (done) {
      if (buffer.trim()) {
        const parsedEvent = parseSseFrame(buffer)
        if (parsedEvent) {
          onEvent(parsedEvent)
        }
      }
      break
    }
  }
}

function parseSseFrame(frame: string): ChatStreamEvent | null {
  const lines = frame
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)

  if (lines.length === 0) {
    return null
  }

  const eventLine = lines.find((line) => line.startsWith('event:'))
  const dataLines = lines.filter((line) => line.startsWith('data:'))

  if (!eventLine || dataLines.length === 0) {
    return null
  }

  const event = eventLine.slice(6).trim() as ChatEventName
  const rawData = dataLines
    .map((line) => line.slice(5).trim())
    .join('\n')

  try {
    return {
      event,
      data: JSON.parse(rawData) as ChatEventPayload,
    }
  } catch {
    return {
      event,
      data: { raw: rawData },
    }
  }
}

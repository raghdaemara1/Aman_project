import { useState, useRef, useEffect } from 'react'
import ChatMessage from '../components/ChatMessage'
import PipelineLog from '../components/PipelineLog'
import { sendChat, clearChatSession, getLogs } from '../services/api'
import type { ChatResponse } from '../services/api'

interface Message {
  role: 'human' | 'assistant'
  content: string
  agentUsed?: 'retrieval_agent' | 'extraction_agent'
  steps?: string[]
  sourceChunks?: string[]
  pageRefs?: number[]
}

interface Props {
  documentLoaded: boolean
}

export default function ChatPage({ documentLoaded }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [liveSteps, setLiveSteps] = useState<string[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading, liveSteps])

  // Poll /logs every 1.5s while agent is running
  useEffect(() => {
    if (!loading) return
    const interval = setInterval(async () => {
      try {
        const res = await getLogs()
        if (res.steps.length > 0) setLiveSteps(res.steps)
      } catch { /* ignore */ }
    }, 1500)
    return () => clearInterval(interval)
  }, [loading])

  async function handleSend() {
    const query = input.trim()
    if (!query || loading) return

    setInput('')
    setError(null)
    setLiveSteps([])
    setMessages(prev => [...prev, { role: 'human', content: query }])
    setLoading(true)

    try {
      const res: ChatResponse = await sendChat(query, sessionId)
      setSessionId(res.session_id)
      setMessages(prev => [
        ...prev,
        {
          role: 'assistant',
          content: res.answer,
          agentUsed: res.agent_used,
          steps: res.steps,
          sourceChunks: res.source_chunks,
          pageRefs: res.page_refs,
        },
      ])
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to get a response. Please try again.'
      setError(msg)
      setMessages(prev => prev.slice(0, -1))
    } finally {
      setLoading(false)
      setLiveSteps([])
    }
  }

  async function handleNewConversation() {
    if (sessionId) {
      try { await clearChatSession(sessionId) } catch { /* ignore */ }
    }
    setMessages([])
    setSessionId(null)
    setError(null)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">Conversational AI Pipeline</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Supervisor → Retrieval Agent or Extraction Agent · remembers conversation
          </p>
        </div>
        {messages.length > 0 && (
          <button
            onClick={handleNewConversation}
            className="text-xs text-gray-400 hover:text-gray-600 border border-gray-200 rounded-lg px-3 py-1.5 transition-colors"
          >
            New conversation
          </button>
        )}
      </div>

      {/* Agent legend */}
      <div className="flex gap-3 mb-4">
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <span className="w-2 h-2 rounded-full bg-blue-400 inline-block" />
          Retrieval Agent — open questions
        </div>
        <div className="flex items-center gap-1.5 text-xs text-gray-500">
          <span className="w-2 h-2 rounded-full bg-purple-400 inline-block" />
          Extraction Agent — field lookups
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-1">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center text-gray-400">
            <p className="text-sm font-medium text-gray-500 mb-1">Start a conversation</p>
            <p className="text-xs max-w-xs">
              Ask anything about the policy. The Supervisor Agent will route your question
              to the right specialist. Follow-up questions remember the context.
            </p>
            <div className="mt-4 space-y-1 text-xs text-left">
              <p className="text-gray-400">Try: <em>"What is the policy number?"</em></p>
              <p className="text-gray-400">Then: <em>"And when does it expire?"</em></p>
              <p className="text-gray-400">Or: <em>"What does it say about accidents?"</em></p>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <ChatMessage
            key={i}
            role={msg.role}
            content={msg.content}
            agentUsed={msg.agentUsed}
            steps={msg.steps}
            sourceChunks={msg.sourceChunks}
            pageRefs={msg.pageRefs}
          />
        ))}

        {loading && (
          <div className="space-y-2">
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-3 shadow-sm">
                <div className="flex gap-1 items-center">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              </div>
            </div>
            {liveSteps.length > 0 && (
              <PipelineLog steps={liveSteps} title="Agent Pipeline (Live)" />
            )}
          </div>
        )}

        {error && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="mt-4 flex gap-2 items-end">
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading || !documentLoaded}
          placeholder={documentLoaded ? 'Ask a question… (Enter to send, Shift+Enter for new line)' : 'Upload a document first'}
          rows={2}
          className="flex-1 resize-none rounded-xl border border-gray-200 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
        />
        <button
          onClick={handleSend}
          disabled={loading || !input.trim() || !documentLoaded}
          className="h-10 px-4 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  )
}

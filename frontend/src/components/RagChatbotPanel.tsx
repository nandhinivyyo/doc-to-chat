import React, { useEffect, useRef, useState } from 'react'
import { Bot, RotateCcw, Send, User } from 'lucide-react'
import { chatWithDocument } from '../services/api'
import type { RagSourceReference } from '../types/document'
import { MarkdownMessage } from './MarkdownMessage'

interface RagChatbotPanelProps {
  documentId: string
  documentName: string
}

type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: RagSourceReference[]
  retrievedChunks?: number
  model?: string
  isWelcome?: boolean
  isError?: boolean
}

const SUGGESTED_QUESTIONS = [
  'What is casinghead gas?',
  'What are the mitigation options?',
  'What are the implementation costs?',
]

const createWelcomeMessage = (): ChatMessage => ({
  id: `welcome-${Date.now()}`,
  role: 'assistant',
  content: 'Hello! Ask me anything about this document.',
  isWelcome: true,
})

const formatSourceLine = (source: RagSourceReference): string => {
  const detail =
    source.content_type === 'table'
      ? 'Table'
      : source.section_heading ?? 'Text'
  return `Page ${source.page} — ${detail} — ${source.chunking_method} (${source.chunk_id})`
}

const GROUNDING_REFUSAL_NORMALIZED =
  'the requested information is not available in the provided document context'
const NO_RELEVANT_CONTEXT_NORMALIZED =
  'no relevant information was found in the document'

const isOutOfDocumentRefusal = (answer: string): boolean => {
  const normalized = answer.trim().toLowerCase().replace(/[.!?\s]+$/g, '')
  return (
    normalized === GROUNDING_REFUSAL_NORMALIZED ||
    normalized === NO_RELEVANT_CONTEXT_NORMALIZED
  )
}

export const RagChatbotPanel: React.FC<RagChatbotPanelProps> = ({
  documentId,
  documentName,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>(() => [createWelcomeMessage()])
  const [input, setInput] = useState('')
  const [topK, setTopK] = useState<number>(5)
  const [isLoading, setIsLoading] = useState(false)

  const messagesEndRef = useRef<HTMLDivElement | null>(null)
  const activeDocumentRef = useRef(documentId)
  const resetVersionRef = useRef(0)

  useEffect(() => {
    activeDocumentRef.current = documentId
    resetVersionRef.current += 1
    setMessages([createWelcomeMessage()])
    setInput('')
    setIsLoading(false)
  }, [documentId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, isLoading])

  const sendQuestion = async (rawQuestion: string) => {
    const trimmed = rawQuestion.trim()
    if (!trimmed || isLoading) return

    const requestDocId = documentId
    const requestResetVersion = resetVersionRef.current

    const userMsg: ChatMessage = {
      id: `user-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      role: 'user',
      content: trimmed,
    }

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setIsLoading(true)

    try {
      const res = await chatWithDocument(requestDocId, {
        query: trimmed,
        top_k: topK,
      })

      if (
        activeDocumentRef.current !== requestDocId ||
        resetVersionRef.current !== requestResetVersion
      ) {
        return
      }

      const assistantMsg: ChatMessage = {
        id: `assistant-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        role: 'assistant',
        content: res.answer,
        sources: res.sources,
        retrievedChunks: res.retrieved_chunks,
        model: res.model,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      if (
        activeDocumentRef.current !== requestDocId ||
        resetVersionRef.current !== requestResetVersion
      ) {
        return
      }

      const rawDetail = err instanceof Error ? err.message.trim() : ''
      const isSafeDetail =
        rawDetail.length > 0 &&
        rawDetail.length < 220 &&
        !rawDetail.toLowerCase().includes('traceback') &&
        !rawDetail.toLowerCase().includes('aiza')
      const content = isSafeDetail
        ? `Sorry, I couldn't generate an answer. Please try again.\n\n(${rawDetail})`
        : "Sorry, I couldn't generate an answer. Please try again."

      const errorMsg: ChatMessage = {
        id: `error-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
        role: 'assistant',
        content,
        isError: true,
      }
      setMessages((prev) => [...prev, errorMsg])
    } finally {
      if (
        activeDocumentRef.current === requestDocId &&
        resetVersionRef.current === requestResetVersion
      ) {
        setIsLoading(false)
      }
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    void sendQuestion(input)
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void sendQuestion(input)
    }
  }

  const handleClearChat = () => {
    resetVersionRef.current += 1
    setMessages([createWelcomeMessage()])
    setInput('')
    setIsLoading(false)
  }

  const showSuggestions = messages.length === 1 && Boolean(messages[0]?.isWelcome) && !isLoading

  return (
    <section
      aria-label="RAG Chatbot"
      className="rounded-xl border border-indigo-200 bg-white p-5 shadow-sm"
    >
      {/* Header */}
      <div className="flex flex-col gap-1 border-b border-slate-100 pb-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-2.5">
          <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
            <Bot className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              RAG Chatbot (Phase 8 — Gemini API)
            </h2>
            <p className="text-xs text-slate-600">
              Document Assistant ·{' '}
              <span className="font-medium text-slate-800">{documentName}</span>
            </p>
          </div>
        </div>
        <span className="text-[11px] text-slate-500">
          Phase 7 FAISS retrieval + grounded Gemini answers
        </span>
      </div>

      {/* Scrollable conversation history */}
      <div
        role="log"
        aria-live="polite"
        aria-label="Chat conversation history"
        className="mt-4 h-[400px] max-h-[60vh] space-y-4 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50/70 p-4"
      >
        {messages.map((msg) =>
          msg.role === 'user' ? (
            <div key={msg.id} className="flex justify-end">
              <div className="flex max-w-[85%] items-start gap-2 sm:max-w-[75%]">
                <div className="rounded-2xl rounded-tr-sm bg-indigo-600 px-4 py-2.5 text-sm text-white shadow-sm">
                  <p className="mb-0.5 text-[11px] font-semibold uppercase tracking-wide text-indigo-200">
                    You
                  </p>
                  <pre className="whitespace-pre-wrap font-sans leading-relaxed">
                    {msg.content}
                  </pre>
                </div>
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-white">
                  <User className="h-3.5 w-3.5" />
                </div>
              </div>
            </div>
          ) : (
            <div key={msg.id} className="flex items-start gap-2.5">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
                <Bot className="h-4 w-4" />
              </div>

                <div
                  className={`max-w-[88%] rounded-2xl rounded-tl-sm border px-4 py-3 text-sm shadow-sm sm:max-w-[80%] ${
                    msg.isError
                      ? 'border-red-200 bg-red-50 text-red-800'
                      : 'border-slate-200 bg-white text-slate-800'
                  }`}
                >
                  <MarkdownMessage content={msg.content} />

                  {!isOutOfDocumentRefusal(msg.content) &&
                    msg.sources &&
                    msg.sources.length > 0 && (
                      <div className="mt-3 border-t border-slate-100 pt-2.5">
                        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                          Sources
                        </p>
                        <ul className="mt-1 space-y-1 text-xs text-slate-600">
                          {msg.sources.map((src) => (
                            <li
                              key={`${msg.id}-${src.chunking_method}-${src.chunk_id}-${src.rank}`}
                              className="flex flex-wrap items-center gap-1.5"
                            >
                              <span className="text-indigo-500">•</span>
                              <span>{formatSourceLine(src)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                  {msg.model && (
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                      {!isOutOfDocumentRefusal(msg.content) &&
                        typeof msg.retrievedChunks === 'number' && (
                          <>
                            <span>Chunks: {msg.retrievedChunks}</span>
                            <span>·</span>
                          </>
                        )}
                      <span>Model: {msg.model}</span>
                    </div>
                  )}
                </div>
            </div>
          ),
        )}

        {showSuggestions && (
          <div className="pl-10">
            <p className="mb-2 text-xs font-medium text-slate-500">Suggested questions:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  type="button"
                  onClick={() => void sendQuestion(q)}
                  className="rounded-full border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 transition hover:border-indigo-300 hover:bg-indigo-50"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {isLoading && (
          <div className="flex items-start gap-2.5">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-700">
              <Bot className="h-4 w-4" />
            </div>
            <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 shadow-sm">
              <span>Thinking</span>
              <span className="inline-flex items-center gap-1" aria-hidden="true">
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-500 [animation-delay:-0.3s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-500 [animation-delay:-0.15s]" />
                <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-indigo-500" />
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Bottom Input Area */}
      <form onSubmit={handleSubmit} className="mt-3 space-y-2.5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={2}
            placeholder="Ask a follow-up question..."
            aria-label="Chat message input"
            disabled={isLoading}
            className="w-full flex-1 resize-none rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none disabled:bg-slate-50"
          />

          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            <span>Send</span>
          </button>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-600">
          <div className="flex items-center gap-2">
            <label htmlFor="rag-top-k" className="font-medium text-slate-700">
              Top-K:
            </label>
            <select
              id="rag-top-k"
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              aria-label="RAG Top K"
              className="rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs text-slate-700 focus:border-indigo-500 focus:outline-none"
            >
              <option value={3}>3</option>
              <option value={5}>5</option>
              <option value={10}>10</option>
            </select>
            <span className="hidden text-[11px] text-slate-400 sm:inline">
              Press Enter to send · Shift+Enter for new line
            </span>
          </div>

          <button
            type="button"
            onClick={handleClearChat}
            className="inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 transition hover:bg-slate-100"
          >
            <RotateCcw className="h-3.5 w-3.5" />
            <span>Clear Chat</span>
          </button>
        </div>
      </form>
    </section>
  )
}

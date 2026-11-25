import React, { useEffect, useState } from 'react'
import { Loader2, Search } from 'lucide-react'
import { searchDocument } from '../services/api'
import type { SemanticSearchResponse } from '../types/document'

interface SemanticSearchPanelProps {
  documentId: string
  documentName: string
}

const METHOD_LABELS: Record<string, string> = {
  fixed_size: 'Fixed-Size',
  token_based: 'Token-Based',
  sentence_based: 'Sentence-Based',
  paragraph_based: 'Paragraph-Based',
  recursive: 'Recursive',
  sliding_window: 'Sliding Window',
  semantic: 'Semantic',
  structure_section: 'Structure / Section-Based',
  table: 'Tables',
  tables: 'Tables',
}

const SCOPE_OPTIONS = [
  { value: '', label: 'All Vector Stores (9)' },
  { value: 'tables', label: 'Tables Only' },
  { value: 'fixed_size', label: 'Fixed-Size' },
  { value: 'token_based', label: 'Token-Based' },
  { value: 'sentence_based', label: 'Sentence-Based' },
  { value: 'paragraph_based', label: 'Paragraph-Based' },
  { value: 'recursive', label: 'Recursive' },
  { value: 'sliding_window', label: 'Sliding Window' },
  { value: 'semantic', label: 'Semantic' },
  { value: 'structure_section', label: 'Structure / Section-Based' },
]

export const SemanticSearchPanel: React.FC<SemanticSearchPanelProps> = ({
  documentId,
  documentName,
}) => {
  const [query, setQuery] = useState('')
  const [topK, setTopK] = useState<number>(5)
  const [chunkingMethod, setChunkingMethod] = useState<string>('')
  const [isSearching, setIsSearching] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [response, setResponse] = useState<SemanticSearchResponse | null>(null)

  useEffect(() => {
    setResponse(null)
    setError(null)
  }, [documentId])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) {
      setError('Please enter a search query.')
      return
    }

    setIsSearching(true)
    setError(null)
    try {
      const payload = {
        query: trimmed,
        top_k: topK,
        ...(chunkingMethod ? { chunking_method: chunkingMethod } : {}),
      }
      const res = await searchDocument(documentId, payload)
      setResponse(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Semantic search failed.')
      setResponse(null)
    } finally {
      setIsSearching(false)
    }
  }

  return (
    <section
      aria-label="Semantic Search"
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Semantic Search (Phase 7)
          </h2>
          <p className="text-xs text-slate-600">
            Search FAISS embeddings for <span className="font-medium">{documentName}</span> using{' '}
            <code className="rounded bg-slate-100 px-1 py-0.5 text-[11px]">
              all-MiniLM-L6-v2
            </code>{' '}
            cosine similarity (chunk retrieval only, no LLM answer generation).
          </p>
        </div>
      </div>

      <form onSubmit={(e) => void handleSubmit(e)} className="mt-4 flex flex-col gap-3 lg:flex-row">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask about this document..."
            aria-label="Semantic search query"
            className="w-full rounded-lg border border-slate-300 bg-white py-2 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-blue-500 focus:outline-none"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={topK}
            onChange={(e) => setTopK(Number(e.target.value))}
            aria-label="Top K results"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none"
          >
            <option value={3}>Top 3</option>
            <option value={5}>Top 5</option>
            <option value={10}>Top 10</option>
          </select>

          <select
            value={chunkingMethod}
            onChange={(e) => setChunkingMethod(e.target.value)}
            aria-label="Vector store scope"
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 focus:border-blue-500 focus:outline-none"
          >
            {SCOPE_OPTIONS.map((opt) => (
              <option key={opt.value || 'all'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <button
            type="submit"
            disabled={isSearching}
            className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:opacity-60"
          >
            {isSearching ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Searching...
              </>
            ) : (
              <>
                <Search className="h-4 w-4" />
                Search
              </>
            )}
          </button>
        </div>
      </form>

      {error && (
        <div
          role="alert"
          className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700"
        >
          {error}
        </div>
      )}

      {response && (
        <div className="mt-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 pb-2 text-xs text-slate-600">
            <span>
              Showing top <span className="font-semibold text-slate-900">{response.results.length}</span>{' '}
              of {response.total_candidates} candidates across{' '}
              <span className="font-medium text-slate-800">{response.searched_stores.length}</span>{' '}
              FAISS store(s)
            </span>
            <span className="text-[11px] text-slate-500">Model: {response.model}</span>
          </div>

          {response.results.length === 0 ? (
            <p className="py-4 text-center text-sm text-slate-500">
              No matching chunks found in the selected vector store(s).
            </p>
          ) : (
            <div className="space-y-3">
              {response.results.map((item) => (
                <article
                  key={`${item.chunking_method}-${item.chunk_id}-${item.rank}`}
                  className="rounded-lg border border-slate-200 bg-slate-50/70 p-4"
                >
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <span className="rounded bg-blue-600 px-2 py-0.5 font-semibold text-white">
                      #{item.rank}
                    </span>
                    <span className="rounded bg-emerald-100 px-2 py-0.5 font-semibold text-emerald-800">
                      Similarity: {item.score.toFixed(4)}
                    </span>
                    <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-800">
                      Type: {item.content_type === 'table' ? 'Table' : 'Text'}
                    </span>
                    <span className="rounded bg-indigo-100 px-2 py-0.5 font-medium text-indigo-800">
                      Method: {METHOD_LABELS[item.chunking_method] ?? item.chunking_method}
                    </span>
                    <span className="rounded bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                      Page: {item.page}
                    </span>
                    {item.section_heading && (
                      <span className="rounded bg-white px-2 py-0.5 text-slate-700 ring-1 ring-slate-200">
                        Section: {item.section_heading}
                      </span>
                    )}
                    <span className="ml-auto font-mono text-[11px] text-slate-500">
                      {item.chunk_id}
                    </span>
                  </div>

                  <pre className="mt-2.5 whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-800">
                    {item.text}
                  </pre>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  )
}

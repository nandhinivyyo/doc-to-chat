import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { Loader2, RefreshCw, X } from 'lucide-react'
import {
  getChunkSummary,
  getImageChunks,
  getMethodChunks,
  getTableChunks,
  runDocumentChunking,
} from '../../services/api'
import type {
  ChunkItem,
  ChunkMethodName,
  ChunkSummaryResponse,
  ImageChunksResponse,
  MethodChunkStats,
  MethodChunksResponse,
  TableChunksResponse,
} from '../../types/document'
import { ImageChunksView } from './ImageChunksView'
import { TableChunksView } from './TableChunksView'
import { TextChunkCard } from './TextChunkCard'

interface ChunkVisualizationPanelProps {
  documentId: string
  documentName: string
}

type ContentTypeFilter = 'all' | 'text' | 'tables' | 'images'
type MethodSelection = 'all_methods' | ChunkMethodName

const METHOD_OPTIONS: { value: ChunkMethodName; label: string }[] = [
  { value: 'fixed_size', label: 'Fixed-Size' },
  { value: 'token_based', label: 'Token-Based' },
  { value: 'sentence_based', label: 'Sentence-Based' },
  { value: 'paragraph_based', label: 'Paragraph-Based' },
  { value: 'recursive', label: 'Recursive' },
  { value: 'sliding_window', label: 'Sliding Window' },
  { value: 'semantic', label: 'Semantic' },
  { value: 'structure_section', label: 'Structure / Section-Based' },
]

const PAGE_SIZE = 10

export const ChunkVisualizationPanel: React.FC<ChunkVisualizationPanelProps> = ({
  documentId,
  documentName,
}) => {
  const [contentType, setContentType] = useState<ContentTypeFilter>('text')
  const [selectedMethod, setSelectedMethod] = useState<MethodSelection>('fixed_size')
  const [currentPage, setCurrentPage] = useState<number>(1)

  const [summary, setSummary] = useState<ChunkSummaryResponse | null>(null)
  const [methodData, setMethodData] = useState<MethodChunksResponse | null>(null)
  const [tableData, setTableData] = useState<TableChunksResponse | null>(null)
  const [imageData, setImageData] = useState<ImageChunksResponse | null>(null)

  const [isLoadingBase, setIsLoadingBase] = useState(false)
  const [isLoadingMethod, setIsLoadingMethod] = useState(false)
  const [isRechunking, setIsRechunking] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [inspectedChunk, setInspectedChunk] = useState<ChunkItem | null>(null)

  const loadBaseData = useCallback(async (docId: string) => {
    setIsLoadingBase(true)
    setError(null)
    try {
      const [sumRes, tblRes, imgRes] = await Promise.all([
        getChunkSummary(docId),
        getTableChunks(docId),
        getImageChunks(docId),
      ])
      setSummary(sumRes)
      setTableData(tblRes)
      setImageData(imgRes)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load chunk data.')
    } finally {
      setIsLoadingBase(false)
    }
  }, [])

  const loadSelectedMethod = useCallback(async (docId: string, method: ChunkMethodName) => {
    setIsLoadingMethod(true)
    setError(null)
    try {
      const res = await getMethodChunks(docId, method)
      setMethodData(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load method chunks.')
    } finally {
      setIsLoadingMethod(false)
    }
  }, [])

  useEffect(() => {
    setCurrentPage(1)
    setInspectedChunk(null)
    void loadBaseData(documentId)
  }, [documentId, loadBaseData])

  useEffect(() => {
    setCurrentPage(1)
    if (selectedMethod !== 'all_methods') {
      void loadSelectedMethod(documentId, selectedMethod)
    }
  }, [documentId, selectedMethod, loadSelectedMethod])

  const handleRechunk = async () => {
    setIsRechunking(true)
    setError(null)
    try {
      await runDocumentChunking(documentId)
      await loadBaseData(documentId)
      if (selectedMethod !== 'all_methods') {
        await loadSelectedMethod(documentId, selectedMethod)
      }
      setCurrentPage(1)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to regenerate chunks.')
    } finally {
      setIsRechunking(false)
    }
  }

  const activeMethodStats: MethodChunkStats | null = useMemo(() => {
    if (selectedMethod === 'all_methods') return null
    return (
      methodData?.stats ??
      summary?.method_stats.find((s) => s.method === selectedMethod) ??
      null
    )
  }, [selectedMethod, methodData, summary])

  const activeMethodLabel = useMemo(() => {
    const found = METHOD_OPTIONS.find((m) => m.value === selectedMethod)
    return found ? found.label : selectedMethod
  }, [selectedMethod])

  const allChunks = methodData?.chunks ?? []
  const totalChunks = allChunks.length
  const totalPages = Math.max(1, Math.ceil(totalChunks / PAGE_SIZE))
  const safePage = Math.min(currentPage, totalPages)
  const startIdx = (safePage - 1) * PAGE_SIZE
  const paginatedChunks = allChunks.slice(startIdx, startIdx + PAGE_SIZE)

  const showText = contentType === 'all' || contentType === 'text'
  const showTables = contentType === 'all' || contentType === 'tables'
  const showImages = contentType === 'all' || contentType === 'images'

  return (
    <div className="space-y-5">
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">
              Chunk Visualization — {documentName}
            </h2>
            <p className="text-sm text-slate-500">
              Inspect text chunks across all 8 methodologies separately from structured table chunks and meaningful image chunks.
            </p>
          </div>

          <button
            type="button"
            disabled={isRechunking}
            onClick={() => void handleRechunk()}
            className="inline-flex items-center gap-1.5 self-start rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${isRechunking ? 'animate-spin' : ''}`} />
            {isRechunking ? 'Regenerating Chunks...' : 'Re-run Phase 4 Chunking'}
          </button>
        </div>

        <div className="mt-4 flex flex-col gap-3 border-t border-slate-100 pt-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Content Type:
            </span>
            {(
              [
                { id: 'all', label: 'All' },
                { id: 'text', label: 'Text' },
                {
                  id: 'tables',
                  label: `Tables (${summary?.table_chunks_count ?? tableData?.table_chunks_count ?? 0})`,
                },
                {
                  id: 'images',
                  label: `Images (${summary?.image_chunks_count ?? imageData?.image_chunks_count ?? 0})`,
                },
              ] as { id: ContentTypeFilter; label: string }[]
            ).map((tab) => (
              <button
                key={tab.id}
                type="button"
                onClick={() => setContentType(tab.id)}
                className={`rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  contentType === tab.id
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {showText && (
            <div className="flex items-center gap-2">
              <label
                htmlFor="chunk-method-select"
                className="text-xs font-semibold uppercase tracking-wide text-slate-500"
              >
                Chunking Method:
              </label>
              <select
                id="chunk-method-select"
                value={selectedMethod}
                onChange={(e) => {
                  setSelectedMethod(e.target.value as MethodSelection)
                  setCurrentPage(1)
                }}
                className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-800 focus:border-blue-500 focus:outline-none"
              >
                <option value="all_methods">All Methods (Overview)</option>
                {METHOD_OPTIONS.map((opt) => {
                  const count = summary?.method_stats.find((s) => s.method === opt.value)?.chunk_count
                  return (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                      {count !== undefined ? ` (${count})` : ''}
                    </option>
                  )
                })}
              </select>
            </div>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error}
        </div>
      )}

      {isLoadingBase ? (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-12 text-sm text-slate-600">
          <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
          <span>Loading chunk visualization data...</span>
        </div>
      ) : (
        <>
          {showText && (
            <section className="space-y-4">
              {selectedMethod === 'all_methods' ? (
                <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
                  <h3 className="text-base font-semibold text-slate-900">
                    All 8 Text Chunking Methods — Summary Comparison
                  </h3>
                  <p className="mt-1 text-xs text-slate-500">
                    Select any method below (or from the dropdown above) to inspect its chunks individually.
                  </p>

                  <div className="mt-4 overflow-x-auto rounded-lg border border-slate-200">
                    <table className="min-w-full divide-y divide-slate-200 text-sm">
                      <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
                        <tr>
                          <th className="px-4 py-2.5">Method</th>
                          <th className="px-4 py-2.5">Total Chunks</th>
                          <th className="px-4 py-2.5">Average Length</th>
                          <th className="px-4 py-2.5">Min Length</th>
                          <th className="px-4 py-2.5">Max Length</th>
                          <th className="px-4 py-2.5">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100 bg-white">
                        {(summary?.method_stats ?? []).map((st) => (
                          <tr key={st.method} className="hover:bg-slate-50">
                            <td className="px-4 py-2.5 font-medium text-slate-900">{st.label}</td>
                            <td className="px-4 py-2.5">{st.chunk_count}</td>
                            <td className="px-4 py-2.5">{st.avg_chunk_length} chars</td>
                            <td className="px-4 py-2.5">{st.min_chunk_length} chars</td>
                            <td className="px-4 py-2.5">{st.max_chunk_length} chars</td>
                            <td className="px-4 py-2.5">
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedMethod(st.method as ChunkMethodName)
                                  setCurrentPage(1)
                                }}
                                className="rounded bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100"
                              >
                                View Chunks
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <>
                  {activeMethodStats && (
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          Total Chunks
                        </p>
                        <p className="mt-1 text-2xl font-bold text-slate-900">
                          {activeMethodStats.chunk_count}
                        </p>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          Average Length
                        </p>
                        <p className="mt-1 text-2xl font-bold text-blue-700">
                          {activeMethodStats.avg_chunk_length}
                          <span className="ml-1 text-xs font-normal text-slate-500">chars</span>
                        </p>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          Minimum Length
                        </p>
                        <p className="mt-1 text-2xl font-bold text-slate-900">
                          {activeMethodStats.min_chunk_length}
                          <span className="ml-1 text-xs font-normal text-slate-500">chars</span>
                        </p>
                      </div>
                      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                          Maximum Length
                        </p>
                        <p className="mt-1 text-2xl font-bold text-slate-900">
                          {activeMethodStats.max_chunk_length}
                          <span className="ml-1 text-xs font-normal text-slate-500">chars</span>
                        </p>
                      </div>
                    </div>
                  )}

                  {isLoadingMethod ? (
                    <div className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-10 text-sm text-slate-600">
                      <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
                      <span>Loading {activeMethodLabel} chunks...</span>
                    </div>
                  ) : totalChunks === 0 ? (
                    <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
                      No text chunks generated for {activeMethodLabel}.
                    </div>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
                        <span className="text-slate-600">
                          Showing <strong className="text-slate-900">{startIdx + 1}</strong>–
                          <strong className="text-slate-900">
                            {Math.min(startIdx + PAGE_SIZE, totalChunks)}
                          </strong>{' '}
                          of <strong className="text-slate-900">{totalChunks}</strong>{' '}
                          {activeMethodLabel} chunks
                        </span>

                        <div className="flex flex-wrap items-center gap-1.5">
                          <button
                            type="button"
                            disabled={safePage <= 1}
                            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                            className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                          >
                            Previous
                          </button>
                          {Array.from({ length: totalPages }, (_, idx) => idx + 1).map((pageNum) => (
                            <button
                              key={pageNum}
                              type="button"
                              onClick={() => setCurrentPage(pageNum)}
                              className={`rounded-lg px-2.5 py-1 text-xs font-medium ${
                                pageNum === safePage
                                  ? 'bg-slate-900 text-white'
                                  : 'border border-slate-200 text-slate-700 hover:bg-slate-50'
                              }`}
                            >
                              {pageNum}
                            </button>
                          ))}
                          <button
                            type="button"
                            disabled={safePage >= totalPages}
                            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                            className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                          >
                            Next
                          </button>
                        </div>
                      </div>

                      <div className="space-y-3">
                        {paginatedChunks.map((chunk, idx) => {
                          const globalIdx = startIdx + idx
                          const prevChunk = globalIdx > 0 ? allChunks[globalIdx - 1] : undefined
                          return (
                            <TextChunkCard
                              key={chunk.chunk_id}
                              chunk={chunk}
                              methodLabel={activeMethodLabel}
                              previousChunk={prevChunk}
                              onInspect={setInspectedChunk}
                            />
                          )
                        })}
                      </div>
                    </>
                  )}
                </>
              )}
            </section>
          )}

          {showTables && (
            <section className="space-y-3">
              <h3 className="text-base font-semibold text-slate-900">
                Table Chunks ({tableData?.table_chunks_count ?? 0})
              </h3>
              <TableChunksView tables={tableData?.tables ?? []} />
            </section>
          )}

          {showImages && (
            <section className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-base font-semibold text-slate-900">
                  Meaningful Image Chunks ({imageData?.image_chunks_count ?? 0})
                </h3>
                <span className="text-xs text-slate-500">
                  Decorative logos flagged in Phase 3 are excluded
                </span>
              </div>
              <ImageChunksView images={imageData?.images ?? []} />
            </section>
          )}
        </>
      )}

      {inspectedChunk && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4"
          onClick={() => setInspectedChunk(null)}
        >
          <div
            className="max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-4 flex items-center justify-between border-b border-slate-200 pb-3">
              <div>
                <h4 className="font-mono text-base font-semibold text-slate-900">
                  {inspectedChunk.chunk_id}
                </h4>
                <p className="text-xs text-slate-500">
                  Page {inspectedChunk.page} · Method: {inspectedChunk.chunking_method} ·{' '}
                  {inspectedChunk.content.length} characters
                </p>
              </div>
              <button
                type="button"
                onClick={() => setInspectedChunk(null)}
                aria-label="Close chunk inspector"
                className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Chunk Content
                </p>
                <p className="whitespace-pre-wrap rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm leading-relaxed text-slate-800">
                  {inspectedChunk.content}
                </p>
              </div>

              <div>
                <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Metadata
                </p>
                <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                  {JSON.stringify(inspectedChunk.metadata, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

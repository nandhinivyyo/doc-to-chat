import React from 'react'
import { ArrowDown, Maximize2 } from 'lucide-react'
import type { ChunkItem } from '../../types/document'

interface TextChunkCardProps {
  chunk: ChunkItem
  methodLabel: string
  previousChunk?: ChunkItem
  onInspect: (chunk: ChunkItem) => void
}

function getOverlapText(prev: ChunkItem | undefined, current: ChunkItem): string | null {
  if (!prev || prev.page !== current.page) return null
  const overlapChars = Number(current.metadata.overlap_chars ?? 0)
  if (!overlapChars || overlapChars <= 0) return null

  const candidate = current.content.slice(0, overlapChars)
  if (candidate && prev.content.endsWith(candidate)) {
    return candidate
  }
  return null
}

export const TextChunkCard: React.FC<TextChunkCardProps> = ({
  chunk,
  methodLabel,
  previousChunk,
  onInspect,
}) => {
  const sectionHeading =
    typeof chunk.metadata.section_heading === 'string' && chunk.metadata.section_heading
      ? chunk.metadata.section_heading
      : null

  const pagesList = Array.isArray(chunk.metadata.pages)
    ? (chunk.metadata.pages as number[])
    : null

  const pageDisplay =
    pagesList && pagesList.length > 1
      ? `Pages ${pagesList[0]}–${pagesList[pagesList.length - 1]}`
      : `Page ${chunk.page}`

  const isSlidingWindow = chunk.chunking_method === 'sliding_window'
  const isSectionBased = chunk.chunking_method === 'structure_section'
  const isSemantic = chunk.chunking_method === 'semantic'

  const overlapChars = Number(chunk.metadata.overlap_chars ?? 0)
  const overlapSnippet = isSlidingWindow ? getOverlapText(previousChunk, chunk) : null

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      {isSectionBased && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-indigo-100 bg-indigo-50/70 px-3 py-2 text-xs text-indigo-900">
          <span className="font-semibold">
            Section: {sectionHeading ?? 'General Document Content'}
          </span>
          <span className="font-medium text-indigo-700">{pageDisplay}</span>
        </div>
      )}

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded bg-blue-100 px-2 py-0.5 font-mono font-semibold text-blue-800">
            {chunk.chunk_id}
          </span>
          <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-700">
            {pageDisplay}
          </span>
          <span className="rounded bg-slate-100 px-2 py-0.5 font-medium text-slate-700">
            {methodLabel}
          </span>
          {sectionHeading && !isSectionBased && (
            <span className="rounded bg-indigo-50 px-2 py-0.5 font-medium text-indigo-700">
              Section: {sectionHeading}
            </span>
          )}
          {isSlidingWindow && overlapChars > 0 && (
            <span className="rounded bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
              Overlap: {overlapChars} characters
            </span>
          )}
          {isSemantic && (
            <span className="rounded bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800">
              Semantic similarity grouping
            </span>
          )}
        </div>

        <div className="flex items-center gap-3">
          <span className="text-slate-500">{chunk.content.length} characters</span>
          <button
            type="button"
            onClick={() => onInspect(chunk)}
            className="inline-flex items-center gap-1 rounded border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
          >
            <Maximize2 className="h-3 w-3" />
            Inspect
          </button>
        </div>
      </div>

      {overlapSnippet && (
        <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50/70 p-3 text-xs text-amber-950">
          <div className="mb-1 flex items-center gap-1.5 font-semibold text-amber-800">
            <span>Previous Chunk ({previousChunk?.chunk_id})</span>
            <ArrowDown className="h-3.5 w-3.5" />
            <span>Overlapping content ({overlapSnippet.length} chars)</span>
            <ArrowDown className="h-3.5 w-3.5" />
            <span>Current Chunk</span>
          </div>
          <p className="line-clamp-2 whitespace-pre-wrap font-mono text-[11px] text-amber-900">
            {overlapSnippet}
          </p>
        </div>
      )}

      <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
        {chunk.content}
      </p>
    </div>
  )
}

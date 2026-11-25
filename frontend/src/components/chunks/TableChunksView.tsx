import React, { useState } from 'react'
import { Code2, Table2 } from 'lucide-react'
import type { ChunkItem } from '../../types/document'

interface TableChunksViewProps {
  tables: ChunkItem[]
}

export const TableChunksView: React.FC<TableChunksViewProps> = ({ tables }) => {
  const [rawTextMode, setRawTextMode] = useState<Record<string, boolean>>({})

  if (tables.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No table chunks available for this document.
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {tables.map((chunk) => {
        const tableId = String(chunk.metadata.table_id ?? chunk.chunk_id)
        const extractor = String(chunk.metadata.extraction_method ?? 'unknown')
        const headers = Array.isArray(chunk.metadata.headers)
          ? (chunk.metadata.headers as string[])
          : []
        const rows = Array.isArray(chunk.metadata.rows)
          ? (chunk.metadata.rows as string[][])
          : []
        const showRaw = Boolean(rawTextMode[chunk.chunk_id])

        return (
          <div
            key={chunk.chunk_id}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="inline-flex items-center gap-1 rounded bg-emerald-100 px-2.5 py-1 font-semibold text-emerald-800">
                  <Table2 className="h-3.5 w-3.5" />
                  {tableId}
                </span>
                <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-700">
                  Page {chunk.page}
                </span>
                <span className="rounded bg-cyan-50 px-2 py-0.5 font-medium text-cyan-800">
                  Extractor: {extractor}
                </span>
                <span className="text-slate-500">
                  {rows.length} rows × {headers.length} columns
                </span>
              </div>

              <button
                type="button"
                onClick={() =>
                  setRawTextMode((prev) => ({
                    ...prev,
                    [chunk.chunk_id]: !prev[chunk.chunk_id],
                  }))
                }
                className="inline-flex items-center gap-1 rounded border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
              >
                <Code2 className="h-3.5 w-3.5" />
                {showRaw ? 'Show HTML Table' : 'Show Chunk Text'}
              </button>
            </div>

            {showRaw ? (
              <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                {chunk.content}
              </pre>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full divide-y divide-slate-200 text-xs">
                  <thead className="bg-slate-50">
                    <tr>
                      {headers.map((header, idx) => (
                        <th
                          key={idx}
                          className="px-3 py-2 text-left font-semibold text-slate-700"
                        >
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 bg-white">
                    {rows.map((row, rIdx) => (
                      <tr key={rIdx} className="hover:bg-slate-50">
                        {row.map((cell, cIdx) => (
                          <td key={cIdx} className="px-3 py-2 text-slate-700">
                            {cell}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

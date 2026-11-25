import React, { useMemo, useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { FileText, Table2, Image as ImageIcon, LayoutList, Code2 } from 'lucide-react'
import { resolveImageUrl } from '../services/api'
import type { DocumentExtractionResponse } from '../types/document'

interface ExtractionPreviewProps {
  extraction: DocumentExtractionResponse
}

type PreviewTab = 'overview' | 'text' | 'tables' | 'images'

export const ExtractionPreview: React.FC<ExtractionPreviewProps> = ({ extraction }) => {
  const [activeTab, setActiveTab] = useState<PreviewTab>('overview')
  const [pageFilter, setPageFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [showMarkdownMap, setShowMarkdownMap] = useState<Record<string, boolean>>({})

  const pageNumbers = useMemo(
    () => extraction.pages.map((p) => p.page),
    [extraction.pages],
  )

  const filteredText = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return extraction.text.filter((item) => {
      if (pageFilter !== 'all' && item.page !== Number(pageFilter)) return false
      if (q && !item.content.toLowerCase().includes(q)) return false
      return true
    })
  }, [extraction.text, pageFilter, searchQuery])

  const filteredTables = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    return extraction.tables.filter((tbl) => {
      if (pageFilter !== 'all' && tbl.page !== Number(pageFilter)) return false
      if (q && !tbl.markdown.toLowerCase().includes(q)) return false
      return true
    })
  }, [extraction.tables, pageFilter, searchQuery])

  const filteredImages = useMemo(() => {
    return extraction.images.filter((img) => {
      if (pageFilter !== 'all' && img.page !== Number(pageFilter)) return false
      return true
    })
  }, [extraction.images, pageFilter])

  const chartData = useMemo(
    () =>
      extraction.pages.map((p) => ({
        page: `P${p.page}`,
        Text: p.text_items_count,
        Tables: p.tables_count,
        Images: p.images_count,
      })),
    [extraction.pages],
  )

  const toggleMarkdown = (contentId: string) => {
    setShowMarkdownMap((prev) => ({ ...prev, [contentId]: !prev[contentId] }))
  }

  const tabs: { id: PreviewTab; label: string; count?: number; icon: React.ReactNode }[] = [
    { id: 'overview', label: 'Page Overview', icon: <LayoutList className="h-4 w-4" /> },
    { id: 'text', label: 'Text', count: extraction.text.length, icon: <FileText className="h-4 w-4" /> },
    { id: 'tables', label: 'Tables', count: extraction.tables.length, icon: <Table2 className="h-4 w-4" /> },
    { id: 'images', label: 'Images', count: extraction.images.length, icon: <ImageIcon className="h-4 w-4" /> },
  ]

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => {
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                  active
                    ? 'bg-slate-900 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                {tab.icon}
                <span>{tab.label}</span>
                {tab.count !== undefined && (
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      active ? 'bg-slate-700 text-white' : 'bg-white text-slate-600'
                    }`}
                  >
                    {tab.count}
                  </span>
                )}
              </button>
            )
          })}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <select
            value={pageFilter}
            onChange={(e) => setPageFilter(e.target.value)}
            aria-label="Filter by page"
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700 focus:border-blue-500 focus:outline-none"
          >
            <option value="all">All Pages ({extraction.pages.length})</option>
            {pageNumbers.map((pg) => (
              <option key={pg} value={pg}>
                Page {pg}
              </option>
            ))}
          </select>

          {(activeTab === 'text' || activeTab === 'tables') && (
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter extracted content..."
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 focus:border-blue-500 focus:outline-none"
            />
          )}
        </div>
      </div>

      <div className="p-5">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div>
              <h4 className="mb-3 text-sm font-semibold text-slate-800">
                Content Distribution by Page
              </h4>
              <div className="h-64 w-full rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="page" tick={{ fontSize: 12 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="Text" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Tables" fill="#10b981" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="Images" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-semibold uppercase text-slate-500">
                  <tr>
                    <th className="px-4 py-2.5">Page</th>
                    <th className="px-4 py-2.5">Size (pt)</th>
                    <th className="px-4 py-2.5">Text Blocks</th>
                    <th className="px-4 py-2.5">Tables</th>
                    <th className="px-4 py-2.5">Images</th>
                    <th className="px-4 py-2.5">Characters</th>
                    <th className="px-4 py-2.5">OCR</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {extraction.pages.map((pg) => (
                    <tr key={pg.page} className="hover:bg-slate-50">
                      <td className="px-4 py-2.5 font-medium text-slate-900">Page {pg.page}</td>
                      <td className="px-4 py-2.5 text-slate-500">
                        {pg.width} × {pg.height}
                      </td>
                      <td className="px-4 py-2.5">{pg.text_items_count}</td>
                      <td className="px-4 py-2.5">{pg.tables_count}</td>
                      <td className="px-4 py-2.5">{pg.images_count}</td>
                      <td className="px-4 py-2.5 text-slate-600">{pg.char_count}</td>
                      <td className="px-4 py-2.5">
                        {pg.ocr_used ? (
                          <span className="rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-800">
                            OCR Used
                          </span>
                        ) : (
                          <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                            Native
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'text' && (
          <div className="space-y-3">
            {filteredText.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-500">
                No extracted text items match the current filter.
              </p>
            ) : (
              filteredText.map((item) => (
                <div
                  key={item.content_id}
                  className="rounded-lg border border-slate-200 bg-slate-50/50 p-4"
                >
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded bg-blue-100 px-2 py-0.5 font-medium text-blue-800">
                        {item.content_id}
                      </span>
                      <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-700">
                        Page {item.page}
                      </span>
                      {item.section_heading && (
                        <span className="rounded bg-indigo-50 px-2 py-0.5 font-medium text-indigo-700">
                          Section: {item.section_heading}
                        </span>
                      )}
                      {item.ocr_used && (
                        <span className="rounded bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                          OCR
                        </span>
                      )}
                    </div>
                    <span>{item.char_count} chars</span>
                  </div>
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
                    {item.content}
                  </p>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'tables' && (
          <div className="space-y-5">
            {filteredTables.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-500">
                No extracted tables match the current filter.
              </p>
            ) : (
              filteredTables.map((tbl) => {
                const showMd = Boolean(showMarkdownMap[tbl.content_id])
                return (
                  <div
                    key={tbl.content_id}
                    className="rounded-lg border border-slate-200 bg-white p-4"
                  >
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <div className="flex flex-wrap items-center gap-2 text-xs">
                        <span className="rounded bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800">
                          {tbl.content_id}
                        </span>
                        <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-700">
                          Page {tbl.page}
                        </span>
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-600">
                          {tbl.row_count} × {tbl.col_count}
                        </span>
                        <span className="rounded bg-cyan-50 px-2 py-0.5 font-medium text-cyan-700">
                          Extractor: {tbl.extractor}
                        </span>
                      </div>

                      <button
                        type="button"
                        onClick={() => toggleMarkdown(tbl.content_id)}
                        className="inline-flex items-center gap-1 rounded border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50"
                      >
                        <Code2 className="h-3.5 w-3.5" />
                        {showMd ? 'Show Table View' : 'Show Markdown'}
                      </button>
                    </div>

                    {showMd ? (
                      <pre className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                        {tbl.markdown}
                      </pre>
                    ) : (
                      <div className="overflow-x-auto rounded-lg border border-slate-200">
                        <table className="min-w-full divide-y divide-slate-200 text-xs">
                          <thead className="bg-slate-50">
                            <tr>
                              {(tbl.data[0] ?? []).map((cell, cIdx) => (
                                <th
                                  key={cIdx}
                                  className="px-3 py-2 text-left font-semibold text-slate-700"
                                >
                                  {cell || `Col ${cIdx + 1}`}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100 bg-white">
                            {tbl.data.slice(1).map((row, rIdx) => (
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
              })
            )}
          </div>
        )}

        {activeTab === 'images' && (
          <div>
            {filteredImages.length === 0 ? (
              <p className="py-8 text-center text-sm text-slate-500">
                No extracted images match the current filter.
              </p>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {filteredImages.map((img) => (
                  <div
                    key={img.image_id}
                    className="overflow-hidden rounded-lg border border-slate-200 bg-slate-50"
                  >
                    <div className="flex h-48 items-center justify-center bg-white p-2">
                      <img
                        src={resolveImageUrl(img.image_url)}
                        alt={`${img.image_id} from page ${img.page}`}
                        className="max-h-full max-w-full object-contain"
                      />
                    </div>
                    <div className="border-t border-slate-200 p-3 text-xs text-slate-600">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-violet-700">{img.image_id}</span>
                        <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-700">
                          Page {img.page}
                        </span>
                      </div>
                      <p className="mt-1 text-slate-500">
                        {img.width} × {img.height} px · {img.format.toUpperCase()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}


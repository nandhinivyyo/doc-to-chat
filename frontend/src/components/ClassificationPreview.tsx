import React, { useMemo, useState } from 'react'
import { FileText, Table2, Image as ImageIcon, Code2, Sparkles, Filter } from 'lucide-react'
import { resolveImageUrl } from '../services/api'
import type { ClassifiedDocumentResponse } from '../types/document'

interface ClassificationPreviewProps {
  classified: ClassifiedDocumentResponse
}

type ClassifiedTab = 'text' | 'tables' | 'images' | 'duplicates'

export const ClassificationPreview: React.FC<ClassificationPreviewProps> = ({ classified }) => {
  const [activeTab, setActiveTab] = useState<ClassifiedTab>('text')
  const [showBoilerplate, setShowBoilerplate] = useState(false)
  const [showDecorativeImages, setShowDecorativeImages] = useState(false)
  const [pageFilter, setPageFilter] = useState<string>('all')
  const [showMarkdownMap, setShowMarkdownMap] = useState<Record<string, boolean>>({})

  const { stats } = classified

  const pageNumbers = useMemo(
    () => Array.from({ length: classified.total_pages }, (_, idx) => idx + 1),
    [classified.total_pages],
  )

  const filteredText = useMemo(
    () =>
      classified.text.filter((item) => {
        if (!showBoilerplate && item.is_boilerplate) return false
        if (pageFilter !== 'all' && item.page !== Number(pageFilter)) return false
        return true
      }),
    [classified.text, showBoilerplate, pageFilter],
  )

  const filteredTables = useMemo(
    () =>
      classified.tables.filter((tbl) => {
        if (pageFilter !== 'all' && tbl.page !== Number(pageFilter)) return false
        return true
      }),
    [classified.tables, pageFilter],
  )

  const filteredImages = useMemo(
    () =>
      classified.images.filter((img) => {
        if (!showDecorativeImages && img.is_decorative) return false
        if (pageFilter !== 'all' && img.page !== Number(pageFilter)) return false
        return true
      }),
    [classified.images, showDecorativeImages, pageFilter],
  )

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Clean Text Items
          </p>
          <p className="mt-1.5 text-2xl font-bold text-slate-900">{stats.clean_text_items}</p>
          <p className="mt-0.5 text-xs text-slate-500">
            {stats.boilerplate_text_items} boilerplate flagged
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Table Duplicates Removed
          </p>
          <p className="mt-1.5 text-2xl font-bold text-blue-700">
            {stats.removed_table_duplicates}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            From {stats.raw_text_items} raw text blocks
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Classified Tables
          </p>
          <p className="mt-1.5 text-2xl font-bold text-emerald-700">{stats.classified_tables}</p>
          <p className="mt-0.5 text-xs text-slate-500">
            {stats.refined_tables_count} refined via pdfplumber
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            Content Images
          </p>
          <p className="mt-1.5 text-2xl font-bold text-violet-700">{stats.content_images}</p>
          <p className="mt-0.5 text-xs text-slate-500">
            {stats.decorative_images} decorative logos flagged
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setActiveTab('text')}
              className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                activeTab === 'text'
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <FileText className="h-4 w-4" />
              <span>Clean Text</span>
              <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs">
                {filteredText.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('tables')}
              className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                activeTab === 'tables'
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <Table2 className="h-4 w-4" />
              <span>Refined Tables</span>
              <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs">
                {filteredTables.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('images')}
              className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                activeTab === 'images'
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <ImageIcon className="h-4 w-4" />
              <span>Classified Images</span>
              <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs">
                {filteredImages.length}
              </span>
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('duplicates')}
              className={`inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition ${
                activeTab === 'duplicates'
                  ? 'bg-slate-900 text-white'
                  : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
              }`}
            >
              <Filter className="h-4 w-4" />
              <span>Removed Duplicates</span>
              <span className="rounded-full bg-white/20 px-2 py-0.5 text-xs">
                {classified.excluded_duplicates.length}
              </span>
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {activeTab === 'text' && (
              <label className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600">
                <input
                  type="checkbox"
                  checked={showBoilerplate}
                  onChange={(e) => setShowBoilerplate(e.target.checked)}
                  className="rounded border-slate-300"
                />
                Show boilerplate ({stats.boilerplate_text_items})
              </label>
            )}

            {activeTab === 'images' && (
              <label className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-600">
                <input
                  type="checkbox"
                  checked={showDecorativeImages}
                  onChange={(e) => setShowDecorativeImages(e.target.checked)}
                  className="rounded border-slate-300"
                />
                Show decorative logos ({stats.decorative_images})
              </label>
            )}

            <select
              value={pageFilter}
              onChange={(e) => setPageFilter(e.target.value)}
              aria-label="Filter classified content by page"
              className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-700"
            >
              <option value="all">All Pages ({classified.total_pages})</option>
              {pageNumbers.map((pg) => (
                <option key={pg} value={pg}>
                  Page {pg}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="p-5">
          {activeTab === 'text' && (
            <div className="space-y-3">
              {filteredText.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-500">
                  No classified text items match the current filter.
                </p>
              ) : (
                filteredText.map((item) => (
                  <div
                    key={item.content_id}
                    className={`rounded-lg border p-4 ${
                      item.is_boilerplate
                        ? 'border-amber-200 bg-amber-50/40'
                        : 'border-slate-200 bg-slate-50/50'
                    }`}
                  >
                    <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded bg-blue-100 px-2 py-0.5 font-medium text-blue-800">
                          {item.content_id}
                        </span>
                        <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-700">
                          Page {item.page}
                        </span>
                        <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-600">
                          {item.extraction_method}
                        </span>
                        {item.section_heading && (
                          <span className="rounded bg-indigo-50 px-2 py-0.5 font-medium text-indigo-700">
                            {item.section_heading}
                          </span>
                        )}
                        {item.is_boilerplate && (
                          <span className="rounded bg-amber-100 px-2 py-0.5 font-medium text-amber-800">
                            Boilerplate
                          </span>
                        )}
                      </div>
                      <span className="text-slate-500">
                        {String(item.metadata.char_count ?? item.text.length)} chars
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
                      {item.text}
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
                  No tables match the current filter.
                </p>
              ) : (
                filteredTables.map((tbl) => {
                  const showMd = Boolean(showMarkdownMap[tbl.table_id])
                  return (
                    <div
                      key={tbl.table_id}
                      className="rounded-lg border border-slate-200 bg-white p-4"
                    >
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="rounded bg-emerald-100 px-2 py-0.5 font-medium text-emerald-800">
                            {tbl.table_id}
                          </span>
                          <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-700">
                            Page {tbl.page}
                          </span>
                          <span className="inline-flex items-center gap-1 rounded bg-cyan-50 px-2 py-0.5 font-medium text-cyan-700">
                            <Sparkles className="h-3 w-3" />
                            {tbl.extraction_method}
                          </span>
                          {typeof tbl.metadata.comparison === 'string' && (
                            <span className="text-slate-500">{tbl.metadata.comparison}</span>
                          )}
                        </div>

                        <button
                          type="button"
                          onClick={() =>
                            setShowMarkdownMap((prev) => ({
                              ...prev,
                              [tbl.table_id]: !prev[tbl.table_id],
                            }))
                          }
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
                                {tbl.headers.map((hdr, idx) => (
                                  <th
                                    key={idx}
                                    className="px-3 py-2 text-left font-semibold text-slate-700"
                                  >
                                    {hdr}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 bg-white">
                              {tbl.rows.map((row, rIdx) => (
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
                  No classified images match the current filter.
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
                        <div className="flex items-center justify-between gap-2">
                          <span className="font-semibold text-violet-700">{img.image_id}</span>
                          <span
                            className={`rounded-full px-2 py-0.5 font-medium ${
                              img.is_decorative
                                ? 'bg-amber-100 text-amber-800'
                                : 'bg-emerald-100 text-emerald-800'
                            }`}
                          >
                            {img.is_decorative ? 'Decorative Logo' : 'Content Figure'}
                          </span>
                        </div>
                        <p className="mt-1 text-slate-500">
                          Page {img.page} · {img.width} × {img.height} px ·{' '}
                          {img.image_format.toUpperCase()}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {activeTab === 'duplicates' && (
            <div className="space-y-2.5">
              {classified.excluded_duplicates.length === 0 ? (
                <p className="py-8 text-center text-sm text-slate-500">
                  No table-duplicate text blocks were detected.
                </p>
              ) : (
                classified.excluded_duplicates.map((dup) => (
                  <div
                    key={dup.raw_content_id}
                    className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs"
                  >
                    <div className="flex flex-wrap items-center gap-2 font-medium text-slate-700">
                      <span className="rounded bg-rose-100 px-2 py-0.5 text-rose-800">
                        Excluded {dup.raw_content_id}
                      </span>
                      <span>Page {dup.page}</span>
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-emerald-800">
                        Matched {dup.matched_table_id}
                      </span>
                      <span className="text-slate-500">
                        Overlap: {(dup.overlap_ratio * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="mt-1.5 text-slate-600">{dup.text_preview}</p>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}


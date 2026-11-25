import React from 'react'
import { FileText, Layers, Table2, Image as ImageIcon, ScanText, CheckCircle2, AlertTriangle } from 'lucide-react'
import type { DocumentSummary } from '../types/document'

interface DocumentSummaryCardsProps {
  summary: DocumentSummary
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

export const DocumentSummaryCards: React.FC<DocumentSummaryCardsProps> = ({ summary }) => {
  const isWarning = summary.status === 'completed_with_warnings'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-4 shadow-sm">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-base font-semibold text-slate-900">{summary.document}</h3>
            <p className="text-xs text-slate-500">
              ID: <code className="rounded bg-slate-100 px-1.5 py-0.5">{summary.document_id}</code> · Size:{' '}
              {formatBytes(summary.file_size_bytes)}
            </p>
          </div>
        </div>

        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
            isWarning
              ? 'bg-amber-50 text-amber-800 border border-amber-200'
              : 'bg-emerald-50 text-emerald-800 border border-emerald-200'
          }`}
        >
          {isWarning ? (
            <AlertTriangle className="h-3.5 w-3.5" />
          ) : (
            <CheckCircle2 className="h-3.5 w-3.5" />
          )}
          {isWarning ? 'Completed with Warnings' : 'Extraction Completed'}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wide">Pages</span>
            <Layers className="h-4 w-4 text-slate-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{summary.total_pages}</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wide">Text Items</span>
            <FileText className="h-4 w-4 text-blue-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{summary.text_items}</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wide">Tables</span>
            <Table2 className="h-4 w-4 text-emerald-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{summary.tables}</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wide">Images</span>
            <ImageIcon className="h-4 w-4 text-violet-500" />
          </div>
          <p className="mt-2 text-2xl font-bold text-slate-900">{summary.images}</p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm col-span-2 md:col-span-1">
          <div className="flex items-center justify-between text-slate-500">
            <span className="text-xs font-medium uppercase tracking-wide">OCR Fallback</span>
            <ScanText className="h-4 w-4 text-amber-500" />
          </div>
          <p className="mt-2 text-lg font-bold text-slate-900">
            {summary.ocr_used ? `Yes (${summary.ocr_pages.length} pg)` : 'Not Needed'}
          </p>
          {summary.ocr_used && (
            <p className="mt-0.5 text-xs text-slate-500">
              Pages: {summary.ocr_pages.join(', ')}
            </p>
          )}
        </div>
      </div>

      {summary.errors.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs text-amber-900">
          <p className="font-semibold">Pipeline Diagnostics ({summary.errors.length})</p>
          <ul className="mt-1.5 list-disc space-y-1 pl-4">
            {summary.errors.map((err, idx) => (
              <li key={idx}>{err}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}


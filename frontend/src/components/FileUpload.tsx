import React, { useRef, useState } from 'react'
import { FileUp, Loader2, AlertCircle, CheckCircle2 } from 'lucide-react'

interface FileUploadProps {
  onUpload: (file: File) => Promise<void>
  isUploading: boolean
  uploadStatus: string | null
  error: string | null
}

export const FileUpload: React.FC<FileUploadProps> = ({
  onUpload,
  isUploading,
  uploadStatus,
  error,
}) => {
  const inputRef = useRef<HTMLInputElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null)

  const handleFile = async (file: File | undefined) => {
    if (!file) return
    setSelectedFileName(file.name)
    await onUpload(file)
  }

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-900">Upload Technical PDF</h2>
          <p className="text-sm text-slate-500">
            Ingest a CCAC / OGMP Technical Guidance PDF to extract text, structured tables, images, and OCR content.
          </p>
        </div>
        {selectedFileName && (
          <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
            Selected: {selectedFileName}
          </span>
        )}
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setIsDragging(true)
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setIsDragging(false)
          const droppedFile = e.dataTransfer.files?.[0]
          void handleFile(droppedFile)
        }}
        onClick={() => !isUploading && inputRef.current?.click()}
        className={`mt-4 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-8 transition ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-slate-300 bg-slate-50 hover:border-slate-400 hover:bg-slate-100/70'
        } ${isUploading ? 'pointer-events-none opacity-70' : ''}`}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={(e) => {
            const picked = e.target.files?.[0]
            void handleFile(picked)
            e.target.value = ''
          }}
        />
        {isUploading ? (
          <>
            <Loader2 className="h-9 w-9 animate-spin text-blue-600" />
            <p className="mt-3 text-sm font-medium text-slate-700">
              Running PDF extraction pipeline (text, tables, images, OCR fallback)...
            </p>
          </>
        ) : (
          <>
            <FileUp className="h-9 w-9 text-slate-400" />
            <p className="mt-3 text-sm font-medium text-slate-700">
              Drag and drop a PDF here, or <span className="text-blue-600 underline">browse</span>
            </p>
            <p className="mt-1 text-xs text-slate-500">Supports single PDF upload (max 50 MB)</p>
          </>
        )}
      </div>

      {uploadStatus && !error && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm text-emerald-800">
          <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
          <span>{uploadStatus}</span>
        </div>
      )}

      {error && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-rose-200 bg-rose-50 px-4 py-2.5 text-sm text-rose-800">
          <AlertCircle className="h-4 w-4 shrink-0 text-rose-600" />
          <span>{error}</span>
        </div>
      )}
    </div>
  )
}


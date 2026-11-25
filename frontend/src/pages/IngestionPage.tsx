import React, { useCallback, useEffect, useState } from 'react'
import { FolderOpen, Loader2, RefreshCw } from 'lucide-react'
import { ClassificationPreview } from '../components/ClassificationPreview'
import { ChunkVisualizationPanel } from '../components/chunks/ChunkVisualizationPanel'
import { DocumentSummaryCards } from '../components/DocumentSummaryCards'
import { ExtractionPreview } from '../components/ExtractionPreview'
import { FileUpload } from '../components/FileUpload'
import { PhaseRoadmapBanner } from '../components/PhaseRoadmapBanner'
import { RagChatbotPanel } from '../components/RagChatbotPanel'
import { SemanticSearchPanel } from '../components/SemanticSearchPanel'
import {
  getDocumentClassification,
  getDocumentExtraction,
  listDocuments,
  runDocumentClassification,
  uploadDocument,
} from '../services/api'
import type {
  ClassifiedDocumentResponse,
  DocumentExtractionResponse,
  DocumentSummary,
} from '../types/document'

type ViewMode = 'chunks' | 'classified' | 'raw'

export const IngestionPage: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentSummary[]>([])
  const [activeExtraction, setActiveExtraction] =
    useState<DocumentExtractionResponse | null>(null)
  const [activeClassification, setActiveClassification] =
    useState<ClassifiedDocumentResponse | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>('chunks')
  const [isUploading, setIsUploading] = useState(false)
  const [isLoadingExtraction, setIsLoadingExtraction] = useState(false)
  const [isClassifying, setIsClassifying] = useState(false)
  const [uploadStatus, setUploadStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const loadDocumentDetails = useCallback(async (documentId: string) => {
    setIsLoadingExtraction(true)
    setError(null)
    try {
      const [extractionData, classifiedData] = await Promise.all([
        getDocumentExtraction(documentId),
        getDocumentClassification(documentId),
      ])
      setActiveExtraction(extractionData)
      setActiveClassification(classifiedData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load document details.')
    } finally {
      setIsLoadingExtraction(false)
    }
  }, [])

  useEffect(() => {
    const init = async () => {
      try {
        const docs = await listDocuments()
        setDocuments(docs)
        if (docs.length > 0) {
          await loadDocumentDetails(docs[0].document_id)
        }
      } catch {
        // Backend may still be starting up; user can upload when ready
      }
    }
    void init()
  }, [loadDocumentDetails])

  const handleUpload = async (file: File) => {
    setIsUploading(true)
    setError(null)
    setUploadStatus(null)
    try {
      const summary = await uploadDocument(file)
      setUploadStatus(
        `Extracted & classified '${summary.document}' (${summary.total_pages} pages, ${summary.text_items} raw text items, ${summary.tables} tables, ${summary.images} images).`,
      )
      setDocuments((prev) => [
        summary,
        ...prev.filter((d) => d.document_id !== summary.document_id),
      ])
      await loadDocumentDetails(summary.document_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed.')
    } finally {
      setIsUploading(false)
    }
  }

  const handleReclassify = async () => {
    if (!activeExtraction) return
    setIsClassifying(true)
    setError(null)
    try {
      const updated = await runDocumentClassification(activeExtraction.summary.document_id)
      setActiveClassification(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Classification failed.')
    } finally {
      setIsClassifying(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-blue-600">
            HCL Final-Year Project · Phase 1–8
          </p>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            Intelligent Document-to-Chatbot Pipeline
          </h1>
          <p className="mt-1 text-sm text-slate-600">
            Multimodal PDF extraction, classification, 8-method chunking, visualization, FAISS embeddings, semantic search &amp; Gemini RAG chatbot
          </p>
        </div>

        {documents.length > 0 && (
          <div className="flex items-center gap-2">
            <FolderOpen className="h-4 w-4 text-slate-500" />
            <select
              value={activeExtraction?.summary.document_id ?? ''}
              onChange={(e) => {
                if (e.target.value) void loadDocumentDetails(e.target.value)
              }}
              aria-label="Select processed document"
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:border-blue-500 focus:outline-none"
            >
              {documents.map((doc) => (
                <option key={doc.document_id} value={doc.document_id}>
                  {doc.document} ({doc.total_pages}p)
                </option>
              ))}
            </select>
          </div>
        )}
      </header>

      <PhaseRoadmapBanner />

      <FileUpload
        onUpload={handleUpload}
        isUploading={isUploading}
        uploadStatus={uploadStatus}
        error={error}
      />

      {isLoadingExtraction && (
        <div className="flex items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white py-12 text-sm text-slate-600">
          <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
          <span>Loading extracted & classified document data...</span>
        </div>
      )}

      {!isLoadingExtraction && activeExtraction && (
        <div className="space-y-6">
          <DocumentSummaryCards summary={activeExtraction.summary} />

          <SemanticSearchPanel
            documentId={activeExtraction.summary.document_id}
            documentName={activeExtraction.summary.document}
          />

          <RagChatbotPanel
            documentId={activeExtraction.summary.document_id}
            documentName={activeExtraction.summary.document}
          />

          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setViewMode('chunks')}
                className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
                  viewMode === 'chunks'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                Chunk Visualization (Phase 5)
              </button>
              <button
                type="button"
                onClick={() => setViewMode('classified')}
                className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
                  viewMode === 'classified'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                Classified & Cleaned (Phase 3)
              </button>
              <button
                type="button"
                onClick={() => setViewMode('raw')}
                className={`rounded-lg px-3.5 py-1.5 text-sm font-medium transition ${
                  viewMode === 'raw'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                Raw Extraction (Phase 2)
              </button>
            </div>

            {viewMode === 'classified' && (
              <button
                type="button"
                disabled={isClassifying}
                onClick={() => void handleReclassify()}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${isClassifying ? 'animate-spin' : ''}`} />
                {isClassifying ? 'Classifying...' : 'Re-run Classification'}
              </button>
            )}
          </div>

          {viewMode === 'chunks' ? (
            <ChunkVisualizationPanel
              documentId={activeExtraction.summary.document_id}
              documentName={activeExtraction.summary.document}
            />
          ) : viewMode === 'classified' && activeClassification ? (
            <ClassificationPreview classified={activeClassification} />
          ) : (
            <ExtractionPreview extraction={activeExtraction} />
          )}
        </div>
      )}
    </div>
  )
}

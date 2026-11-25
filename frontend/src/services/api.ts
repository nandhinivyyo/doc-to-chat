import type {
  ChunkSummaryResponse,
  ClassifiedDocumentResponse,
  DocumentExtractionResponse,
  DocumentListResponse,
  DocumentSummary,
  ImageChunksResponse,
  MethodChunksResponse,
  RagChatRequest,
  RagChatResponse,
  SemanticSearchRequest,
  SemanticSearchResponse,
  TableChunksResponse,
} from '../types/document'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`
    try {
      const payload = await response.json()
      if (payload?.detail) {
        message = typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail)
      }
    } catch {
      // keep fallback message
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export async function listDocuments(): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE}/api/documents`)
  const data = await handleResponse<DocumentListResponse>(res)
  return data.documents
}

export async function uploadDocument(file: File): Promise<DocumentSummary> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE}/api/documents/upload`, {
    method: 'POST',
    body: formData,
  })
  return handleResponse<DocumentSummary>(res)
}

export async function getDocumentSummary(documentId: string): Promise<DocumentSummary> {
  const res = await fetch(`${API_BASE}/api/documents/${encodeURIComponent(documentId)}`)
  return handleResponse<DocumentSummary>(res)
}

export async function getDocumentExtraction(
  documentId: string,
): Promise<DocumentExtractionResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/extraction`,
  )
  return handleResponse<DocumentExtractionResponse>(res)
}

export async function getDocumentClassification(
  documentId: string,
): Promise<ClassifiedDocumentResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/classification`,
  )
  return handleResponse<ClassifiedDocumentResponse>(res)
}

export async function runDocumentClassification(
  documentId: string,
): Promise<ClassifiedDocumentResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/classify`,
    { method: 'POST' },
  )
  return handleResponse<ClassifiedDocumentResponse>(res)
}

export async function runDocumentChunking(
  documentId: string,
): Promise<ChunkSummaryResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/chunk`,
    { method: 'POST' },
  )
  return handleResponse<ChunkSummaryResponse>(res)
}

export async function getChunkSummary(
  documentId: string,
): Promise<ChunkSummaryResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/chunks/summary`,
  )
  return handleResponse<ChunkSummaryResponse>(res)
}

export async function getMethodChunks(
  documentId: string,
  method: string,
): Promise<MethodChunksResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/chunks/${encodeURIComponent(method)}`,
  )
  return handleResponse<MethodChunksResponse>(res)
}

export async function getTableChunks(
  documentId: string,
): Promise<TableChunksResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/chunks/tables`,
  )
  return handleResponse<TableChunksResponse>(res)
}

export async function getImageChunks(
  documentId: string,
): Promise<ImageChunksResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/chunks/images`,
  )
  return handleResponse<ImageChunksResponse>(res)
}

export async function searchDocument(
  documentId: string,
  request: SemanticSearchRequest,
): Promise<SemanticSearchResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/search`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    },
  )
  return handleResponse<SemanticSearchResponse>(res)
}

export async function chatWithDocument(
  documentId: string,
  request: RagChatRequest,
): Promise<RagChatResponse> {
  const res = await fetch(
    `${API_BASE}/api/documents/${encodeURIComponent(documentId)}/chat`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    },
  )
  return handleResponse<RagChatResponse>(res)
}

export function resolveImageUrl(imageUrl: string): string {
  if (imageUrl.startsWith('http://') || imageUrl.startsWith('https://')) {
    return imageUrl
  }
  return `${API_BASE}${imageUrl}`
}


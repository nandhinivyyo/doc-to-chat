export interface TextItem {
  content_id: string
  content_type: 'text'
  document: string
  page: number
  content: string
  bbox: number[] | null
  section_heading: string | null
  ocr_used: boolean
  char_count: number
}

export interface TableItem {
  content_id: string
  content_type: 'table'
  document: string
  page: number
  row_count: number
  col_count: number
  headers: string[]
  data: string[][]
  markdown: string
  extractor: 'pymupdf' | 'pdfplumber'
  bbox: number[] | null
}

export interface ImageItem {
  content_id: string
  content_type: 'image'
  document: string
  page: number
  image_id: string
  image_path: string
  image_url: string
  file_name: string
  width: number
  height: number
  format: string
  bbox: number[] | null
  ocr_text: string | null
}

export interface PageMetadata {
  page: number
  width: number
  height: number
  text_items_count: number
  tables_count: number
  images_count: number
  ocr_used: boolean
  ocr_reason: string | null
  char_count: number
  errors: string[]
}

export interface DocumentSummary {
  document_id: string
  document: string
  file_size_bytes: number
  total_pages: number
  text_items: number
  tables: number
  images: number
  ocr_pages: number[]
  ocr_used: boolean
  status: 'completed' | 'completed_with_warnings' | 'failed'
  created_at: string
  errors: string[]
}

export interface DocumentExtractionResponse {
  summary: DocumentSummary
  pages: PageMetadata[]
  text: TextItem[]
  tables: TableItem[]
  images: ImageItem[]
}

export interface DocumentListResponse {
  documents: DocumentSummary[]
}

export interface ClassifiedTextItem {
  content_id: string
  document_id: string
  document_name: string
  page: number
  content_type: 'text'
  text: string
  bbox: number[] | null
  section_heading: string | null
  extraction_method: 'pymupdf' | 'ocr'
  is_boilerplate: boolean
  metadata: Record<string, unknown>
}

export interface ClassifiedTableItem {
  table_id: string
  content_id: string
  document_id: string
  document_name: string
  page: number
  content_type: 'table'
  headers: string[]
  rows: string[][]
  structured_data: Record<string, string>[]
  markdown: string
  bbox: number[] | null
  extraction_method: 'pymupdf' | 'pdfplumber'
  metadata: Record<string, unknown>
}

export interface ClassifiedImageItem {
  image_id: string
  content_id: string
  document_id: string
  document_name: string
  page: number
  content_type: 'image'
  image_path: string
  image_url: string
  image_format: string
  width: number
  height: number
  bbox: number[] | null
  ocr_text: string | null
  is_decorative: boolean
  metadata: Record<string, unknown>
}

export interface ExcludedDuplicateItem {
  raw_content_id: string
  page: number
  matched_table_id: string
  overlap_ratio: number
  reason: string
  text_preview: string
}

export interface ClassificationStats {
  raw_text_items: number
  classified_text_items: number
  clean_text_items: number
  boilerplate_text_items: number
  removed_table_duplicates: number
  raw_tables: number
  classified_tables: number
  refined_tables_count: number
  raw_images: number
  classified_images: number
  content_images: number
  decorative_images: number
}

export interface ClassifiedDocumentResponse {
  document_id: string
  document_name: string
  total_pages: number
  created_at: string
  stats: ClassificationStats
  text: ClassifiedTextItem[]
  tables: ClassifiedTableItem[]
  images: ClassifiedImageItem[]
  excluded_duplicates: ExcludedDuplicateItem[]
}

export type ChunkMethodName =
  | 'fixed_size'
  | 'token_based'
  | 'sentence_based'
  | 'paragraph_based'
  | 'recursive'
  | 'sliding_window'
  | 'semantic'
  | 'structure_section'

export interface ChunkItem {
  chunk_id: string
  document_id: string
  page: number
  content_type: 'text' | 'table' | 'image'
  chunking_method: string
  content: string
  metadata: Record<string, unknown>
}

export interface MethodChunkStats {
  method: string
  label: string
  chunk_count: number
  avg_chunk_length: number
  min_chunk_length: number
  max_chunk_length: number
  total_characters: number
  total_words: number
}

export interface ChunkSummaryResponse {
  document_id: string
  document_name: string
  total_pages: number
  created_at: string
  parameters: Record<string, number>
  method_stats: MethodChunkStats[]
  table_chunks_count: number
  image_chunks_count: number
  warnings: string[]
}

export interface MethodChunksResponse {
  document_id: string
  document_name: string
  method: string
  stats: MethodChunkStats
  chunks: ChunkItem[]
}

export interface TableChunksResponse {
  document_id: string
  document_name: string
  table_chunks_count: number
  tables: ChunkItem[]
}

export interface ImageChunksResponse {
  document_id: string
  document_name: string
  image_chunks_count: number
  images: ChunkItem[]
}

export interface SemanticSearchRequest {
  query: string
  top_k: number
  chunking_method?: string
}

export interface SemanticSearchResult {
  rank: number
  score: number
  chunk_id: string
  document_id: string
  content_type: 'text' | 'table'
  chunking_method: string
  page: number
  section_heading: string | null
  text: string
}

export interface SemanticSearchResponse {
  query: string
  top_k: number
  document_id: string
  chunking_method: string | null
  model: string
  searched_stores: string[]
  total_candidates: number
  results: SemanticSearchResult[]
}

export interface RagChatRequest {
  query: string
  top_k: number
}

export interface RagSourceReference {
  rank: number
  score: number
  page: number
  chunk_id: string
  content_type: 'text' | 'table'
  chunking_method: string
  section_heading: string | null
}

export interface RagChatResponse {
  query: string
  answer: string
  sources: RagSourceReference[]
  retrieved_chunks: number
  model: string
}


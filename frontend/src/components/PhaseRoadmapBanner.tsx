import React from 'react'

const PIPELINE_STAGES = [
  { label: '1-2. PDF Ingestion & Extraction', active: true },
  { label: '3. Content Classification', active: true },
  { label: '4. 8-Method Chunking', active: true },
  { label: '5. Chunk Visualization', active: true },
  { label: '6. Embeddings & FAISS', active: true },
  { label: '7. Semantic Search', active: true },
  { label: '8. RAG Chatbot (Gemini)', active: true },
]

export const PhaseRoadmapBanner: React.FC = () => {
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <span className="mr-1 text-xs font-semibold uppercase tracking-wider text-slate-500">
        Pipeline Roadmap:
      </span>
      {PIPELINE_STAGES.map((stage) => (
        <span
          key={stage.label}
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            stage.active
              ? 'bg-blue-600 text-white'
              : 'bg-slate-100 text-slate-500'
          }`}
        >
          {stage.label}
        </span>
      ))}
    </div>
  )
}

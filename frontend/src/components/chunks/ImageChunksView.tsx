import React from 'react'
import { Image as ImageIcon } from 'lucide-react'
import { resolveImageUrl } from '../../services/api'
import type { ChunkItem } from '../../types/document'

interface ImageChunksViewProps {
  images: ChunkItem[]
}

export const ImageChunksView: React.FC<ImageChunksViewProps> = ({ images }) => {
  if (images.length === 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
        No meaningful content image chunks available for this document.
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {images.map((chunk) => {
        const imageId = String(chunk.metadata.image_id ?? chunk.chunk_id)
        const imageUrl = String(chunk.metadata.image_url ?? '')
        const imagePath = String(chunk.metadata.image_path ?? '')
        const sectionHeading =
          typeof chunk.metadata.section_heading === 'string' && chunk.metadata.section_heading
            ? chunk.metadata.section_heading
            : null
        const captionContext =
          typeof chunk.metadata.caption_context === 'string' && chunk.metadata.caption_context
            ? chunk.metadata.caption_context
            : null
        const width = Number(chunk.metadata.width ?? 0)
        const height = Number(chunk.metadata.height ?? 0)
        const format = String(chunk.metadata.image_format ?? '').toUpperCase()

        return (
          <div
            key={chunk.chunk_id}
            className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
          >
            <div className="flex h-52 items-center justify-center bg-slate-50 p-3">
              {imageUrl ? (
                <img
                  src={resolveImageUrl(imageUrl)}
                  alt={`${imageId} on page ${chunk.page}`}
                  className="max-h-full max-w-full rounded object-contain"
                />
              ) : (
                <ImageIcon className="h-10 w-10 text-slate-300" />
              )}
            </div>

            <div className="space-y-1.5 border-t border-slate-200 p-4 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono font-semibold text-violet-700">{imageId}</span>
                <span className="rounded bg-slate-200 px-2 py-0.5 font-medium text-slate-700">
                  Page {chunk.page}
                </span>
              </div>

              {sectionHeading && (
                <p className="font-medium text-slate-800">Section: {sectionHeading}</p>
              )}

              {captionContext && captionContext !== sectionHeading && (
                <p className="text-slate-600">Context: {captionContext}</p>
              )}

              <p className="text-slate-500">
                {width} × {height} px {format ? `· ${format}` : ''}
              </p>

              <p className="truncate font-mono text-[11px] text-slate-400" title={imagePath}>
                {imagePath}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

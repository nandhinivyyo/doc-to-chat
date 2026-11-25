import React from 'react'

interface MarkdownMessageProps {
  content: string
}

const INLINE_TOKEN_REGEX = /(\*\*[^\n]+?\*\*|`[^`\n]+?`|\*[^*\n]+?\*)/g
const BULLET_LINE_REGEX = /^\s*[-*•]\s+(.+)$/
const NUMBERED_LINE_REGEX = /^\s*\d+[.)]\s+(.+)$/
const HEADING_LINE_REGEX = /^\s*#{1,3}\s+(.+)$/

function renderInlineMarkdown(text: string, keyPrefix: string): React.ReactNode[] {
  const parts = text.split(INLINE_TOKEN_REGEX)
  return parts
    .filter((part) => part.length > 0)
    .map((part, idx) => {
      const key = `${keyPrefix}-${idx}`
      if (part.startsWith('**') && part.endsWith('**') && part.length > 4) {
        return (
          <strong key={key} className="font-semibold text-slate-900">
            {part.slice(2, -2)}
          </strong>
        )
      }
      if (part.startsWith('*') && part.endsWith('*') && part.length > 2) {
        return (
          <em key={key} className="italic text-slate-700">
            {part.slice(1, -1)}
          </em>
        )
      }
      if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
        return (
          <code
            key={key}
            className="rounded bg-slate-100 px-1 py-0.5 font-mono text-[0.85em] text-slate-800"
          >
            {part.slice(1, -1)}
          </code>
        )
      }
      return <React.Fragment key={key}>{part}</React.Fragment>
    })
}

export const MarkdownMessage: React.FC<MarkdownMessageProps> = ({ content }) => {
  const lines = content.replace(/\r\n/g, '\n').split('\n')
  const blocks: React.ReactNode[] = []

  let i = 0
  let blockIdx = 0

  while (i < lines.length) {
    const line = lines[i]

    if (!line.trim()) {
      i += 1
      continue
    }

    const headingMatch = line.match(HEADING_LINE_REGEX)
    if (headingMatch) {
      const key = `h-${blockIdx++}`
      blocks.push(
        <p key={key} className="font-semibold text-slate-900">
          {renderInlineMarkdown(headingMatch[1].trim(), key)}
        </p>,
      )
      i += 1
      continue
    }

    if (BULLET_LINE_REGEX.test(line)) {
      const items: string[] = []
      while (i < lines.length) {
        const match = lines[i].match(BULLET_LINE_REGEX)
        if (!match) break
        items.push(match[1].trim())
        i += 1
      }
      const listKey = `ul-${blockIdx++}`
      blocks.push(
        <ul key={listKey} className="list-disc space-y-1 pl-5">
          {items.map((itemText, itemIdx) => (
            <li key={`${listKey}-${itemIdx}`} className="leading-relaxed">
              {renderInlineMarkdown(itemText, `${listKey}-${itemIdx}`)}
            </li>
          ))}
        </ul>,
      )
      continue
    }

    if (NUMBERED_LINE_REGEX.test(line)) {
      const items: string[] = []
      while (i < lines.length) {
        const match = lines[i].match(NUMBERED_LINE_REGEX)
        if (!match) break
        items.push(match[1].trim())
        i += 1
      }
      const listKey = `ol-${blockIdx++}`
      blocks.push(
        <ol key={listKey} className="list-decimal space-y-1 pl-5">
          {items.map((itemText, itemIdx) => (
            <li key={`${listKey}-${itemIdx}`} className="leading-relaxed">
              {renderInlineMarkdown(itemText, `${listKey}-${itemIdx}`)}
            </li>
          ))}
        </ol>,
      )
      continue
    }

    const paragraphLines: string[] = []
    while (
      i < lines.length &&
      lines[i].trim() !== '' &&
      !HEADING_LINE_REGEX.test(lines[i]) &&
      !BULLET_LINE_REGEX.test(lines[i]) &&
      !NUMBERED_LINE_REGEX.test(lines[i])
    ) {
      paragraphLines.push(lines[i])
      i += 1
    }

    const pKey = `p-${blockIdx++}`
    blocks.push(
      <p key={pKey} className="leading-relaxed">
        {paragraphLines.map((pLine, lineIdx) => (
          <React.Fragment key={`${pKey}-l-${lineIdx}`}>
            {lineIdx > 0 && <br />}
            {renderInlineMarkdown(pLine, `${pKey}-l-${lineIdx}`)}
          </React.Fragment>
        ))}
      </p>,
    )
  }

  return <div className="space-y-2 text-sm leading-relaxed">{blocks}</div>
}

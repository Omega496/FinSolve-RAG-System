/**
 * AssistantMessage — renders LLM response with streaming support.
 * 
 * Shows blinking cursor while streaming.
 * Renders SourceCitations when done.
 */

import ReactMarkdown from 'react-markdown'
import SourceCitations from './SourceCitations.jsx'

export default function AssistantMessage({ content, sources, isStreaming, isBlocked }) {
  // Don't render blocked messages here — GuardrailBlockedMessage handles those
  if (isBlocked) return null

  return (
    <div className="max-w-3xl mr-auto">
      {/* Message bubble */}
      <div className="bg-slate-700 rounded-lg p-4 mr-12 text-slate-100">
        <ReactMarkdown className="prose prose-invert prose-sm max-w-none">
          {content}
        </ReactMarkdown>

        {/* Blinking cursor while streaming */}
        {isStreaming && (
          <span className="inline-block w-2 h-4 ml-1 bg-slate-300 animate-pulse" />
        )}
      </div>

      {/* Source citations — only show when streaming complete */}
      {!isStreaming && sources?.length > 0 && (
        <SourceCitations sources={sources} />
      )}
    </div>
  )
}

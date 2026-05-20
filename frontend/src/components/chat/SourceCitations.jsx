/**
 * SourceCitations — collapsible list of source chunks.
 * 
 * Shows doc name and section (header_breadcrumb) for each retrieved chunk.
 */

import { useState } from 'react'

export default function SourceCitations({ sources }) {
  const [expanded, setExpanded] = useState(false)

  if (!sources || sources.length === 0) return null

  return (
    <div className="mt-2 ml-12">
      {/* Toggle button */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-xs text-slate-400 hover:text-slate-300 transition-colors"
      >
        <svg
          className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
        </svg>
        {sources.length} source{sources.length !== 1 ? 's' : ''} cited
      </button>

      {/* Source list */}
      {expanded && (
        <div className="mt-2 space-y-1">
          {sources.map((source, i) => (
            <div
              key={i}
              className="flex items-start gap-2 text-xs text-slate-400 bg-slate-800 rounded px-3 py-2"
            >
              <svg
                className="w-3 h-3 mt-0.5 text-slate-500 flex-shrink-0"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M19.5 14.25v-2.625a3.375 3.375 0 0 0-3.375-3.375h-1.5A1.125 1.125 0 0 1 13.5 7.125v-1.5a3.375 3.375 0 0 0-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 0 0-9-9Z"
                />
              </svg>
              <div className="min-w-0">
                <span className="font-medium text-slate-300">
                  {source.source_file || 'Unknown'}
                </span>
                {source.header && (
                  <span className="text-slate-500 ml-1">
                    — {source.header}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

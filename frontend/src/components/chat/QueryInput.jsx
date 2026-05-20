/**
 * QueryInput — multi-line textarea with submit button.
 * 
 * Enter to send, Shift+Enter for newline.
 * Disabled during streaming.
 */

import { useRef, useCallback } from 'react'

export default function QueryInput({ value, onChange, onSubmit, isStreaming }) {
  const textareaRef = useRef(null)

  const handleKeyDown = useCallback((e) => {
    // Enter to send, Shift+Enter for newline
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (!isStreaming && value.trim()) {
        onSubmit()
      }
    }
  }, [isStreaming, value, onSubmit])

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        if (!isStreaming && value.trim()) {
          onSubmit()
        }
      }}
      className="p-4 border-t border-slate-700"
    >
      <div className="max-w-3xl mx-auto flex gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about company documents... (Enter to send, Shift+Enter for newline)"
          rows={1}
          className="flex-1 px-4 py-3 bg-slate-800 border border-slate-600 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          disabled={isStreaming}
        />
        <button
          type="submit"
          disabled={isStreaming || !value.trim()}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 disabled:cursor-not-allowed text-white font-medium rounded-lg transition-colors self-end"
        >
          {isStreaming ? (
            <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 12 3.269 3.125A59.769 59.769 0 0 1 21.485 12 59.768 59.768 0 0 1 3.27 20.875L5.999 12Zm0 0h7.5" />
            </svg>
          )}
        </button>
      </div>
    </form>
  )
}

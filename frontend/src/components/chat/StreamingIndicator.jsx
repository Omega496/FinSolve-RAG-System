/**
 * StreamingIndicator — animated dots shown while streaming.
 */

export default function StreamingIndicator() {
  return (
    <div className="max-w-3xl mr-auto">
      <div className="bg-slate-700 rounded-lg p-4 mr-12">
        <div className="flex items-center gap-1.5">
          <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
          <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
          <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
        </div>
      </div>
    </div>
  )
}

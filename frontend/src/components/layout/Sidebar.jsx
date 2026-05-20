/**
 * Sidebar — navigation panel with role badge, sessions, logout.
 * 
 * slate-800 background per AGNNTS.md.
 */

import RoleBadge from './RoleBadge.jsx'

export default function Sidebar({
  user,
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
  onLogout,
}) {
  return (
    <div className="w-64 bg-slate-800 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-bold text-slate-100 mb-3">FinSolve</h2>
        <RoleBadge role={user?.role} />
        <p className="text-xs text-slate-400 mt-2">{user?.name}</p>
      </div>

      {/* New Chat button */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 hover:bg-blue-700 rounded text-sm text-white font-medium transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Chat
        </button>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1">
        <p className="text-xs text-slate-500 uppercase mb-2">Conversations</p>
        {sessions.length === 0 ? (
          <p className="text-xs text-slate-500 italic">No conversations yet</p>
        ) : (
          sessions.map((session) => (
            <button
              key={session.id}
              onClick={() => onSelectSession(session.id)}
              className={`w-full text-left px-3 py-2 rounded text-sm transition-colors ${
                session.id === activeSessionId
                  ? 'bg-slate-700 text-slate-100'
                  : 'text-slate-400 hover:bg-slate-700/50 hover:text-slate-300'
              }`}
            >
              <div className="truncate">{session.title}</div>
              <div className="text-xs text-slate-500 mt-0.5">
                {session.messages.length} messages
              </div>
            </button>
          ))
        )}
      </div>

      {/* Logout */}
      <div className="p-3 border-t border-slate-700">
        <button
          onClick={onLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-red-900/50 hover:bg-red-900 rounded text-sm text-red-300 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" />
          </svg>
          Logout
        </button>
      </div>
    </div>
  )
}

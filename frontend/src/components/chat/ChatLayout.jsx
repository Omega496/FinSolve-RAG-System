/**
 * ChatLayout — main page wrapper with Sidebar + MainChat.
 * 
 * Sidebar (slate-800) on left, MainChat (slate-900) on right.
 * Manages sessions and conversation state.
 */

import { useState, useRef, useEffect, useCallback } from 'react'
import { useAuth } from '../../context/AuthContext.jsx'
import { useStream } from '../../hooks/useStream.js'
import Sidebar from '../layout/Sidebar.jsx'
import MessageList from './MessageList.jsx'
import QueryInput from './QueryInput.jsx'

export default function ChatLayout() {
  const { user, logout } = useAuth()
  const {
    tokens,
    sources,
    isStreaming,
    isBlocked,
    blockReason,
    error,
    sendQuery,
  } = useStream()

  const [input, setInput] = useState('')
  const [sessions, setSessions] = useState([])
  const [activeSessionId, setActiveSessionId] = useState(null)
  const messagesEndRef = useRef(null)

  // Get current session's messages
  const currentSession = sessions.find(s => s.id === activeSessionId)
  const messages = currentSession?.messages || []

  // Build current response from tokens
  const currentResponse = tokens.join('')

  // Auto-scroll on new messages or tokens
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentResponse])

  // When streaming ends, save the response to session
  useEffect(() => {
    if (!isStreaming && activeSessionId && (currentResponse || isBlocked)) {
      setSessions(prev => prev.map(session => {
        if (session.id !== activeSessionId) return session

        // Check if this response is already saved
        const lastMsg = session.messages[session.messages.length - 1]
        if (lastMsg?.role === 'assistant' && lastMsg?.content === currentResponse) {
          return session
        }

        return {
          ...session,
          messages: [
            ...session.messages,
            {
              role: 'assistant',
              content: isBlocked ? `[Blocked: ${blockReason}]` : currentResponse,
              sources: isBlocked ? [] : sources,
              blocked: isBlocked,
              blockReason: blockReason,
            }
          ]
        }
      }))
    }
  }, [isStreaming, isBlocked, blockReason, currentResponse, sources, activeSessionId])

  const handleNewChat = useCallback(() => {
    const newSession = {
      id: crypto.randomUUID(),
      title: 'New Chat',
      messages: [],
      createdAt: new Date().toISOString(),
    }
    setSessions(prev => [newSession, ...prev])
    setActiveSessionId(newSession.id)
  }, [])

  const handleSelectSession = useCallback((sessionId) => {
    setActiveSessionId(sessionId)
  }, [])

  const handleSubmit = useCallback(async () => {
    if (!input.trim() || isStreaming) return

    const query = input.trim()
    setInput('')

    // Create session if none active
    if (!activeSessionId) {
      handleNewChat()
    }

    // Add user message to session
    const sessionId = activeSessionId || crypto.randomUUID()
    setSessions(prev => prev.map(session => {
      if (session.id !== sessionId) return session

      // Update title with first message
      const title = session.messages.length === 0
        ? query.slice(0, 50) + (query.length > 50 ? '...' : '')
        : session.title

      return {
        ...session,
        title,
        messages: [...session.messages, { role: 'user', content: query }]
      }
    }))

    // Send query
    await sendQuery(query)
  }, [input, isStreaming, activeSessionId, handleNewChat, sendQuery])

  // Initialize with first session
  useEffect(() => {
    if (sessions.length === 0) {
      handleNewChat()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="min-h-screen bg-slate-900 flex">
      {/* Sidebar */}
      <Sidebar
        user={user}
        sessions={sessions}
        activeSessionId={activeSessionId}
        onNewChat={handleNewChat}
        onSelectSession={handleSelectSession}
        onLogout={logout}
      />

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col">
        <MessageList
          messages={messages}
          currentResponse={currentResponse}
          currentSources={sources}
          isStreaming={isStreaming}
          isBlocked={isBlocked}
          blockReason={blockReason}
          messagesEndRef={messagesEndRef}
        />

        <QueryInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          isStreaming={isStreaming}
        />
      </div>
    </div>
  )
}

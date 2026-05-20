/**
 * useStream — SSE streaming hook for /query endpoint.
 * 
 * Reads tokens progressively via ReadableStream + getReader().
 * Never buffers full response — renders tokens as they arrive.
 */

import { useState, useRef, useCallback } from 'react'

export function useStream() {
  const [tokens, setTokens] = useState([])
  const [sources, setSources] = useState([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [isBlocked, setIsBlocked] = useState(false)
  const [blockReason, setBlockReason] = useState(null)
  const [error, setError] = useState(null)

  const readerRef = useRef(null)
  const sessionIdRef = useRef(crypto.randomUUID())

  /**
   * Send query and stream response.
   * Resets all state before starting.
   */
  const sendQuery = useCallback(async (query) => {
    // ── Reset state ────────────────────────────────────────────────
    setTokens([])
    setSources([])
    setIsStreaming(true)
    setIsBlocked(false)
    setBlockReason(null)
    setError(null)

    try {
      // ── POST /query with credentials ─────────────────────────────
      const response = await fetch('/query', {
        method: 'POST',
        credentials: 'include',  // ALWAYS include httpOnly cookies
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query,
          session_id: sessionIdRef.current,
        }),
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      // ── Read SSE stream ──────────────────────────────────────────
      const reader = response.body.getReader()
      readerRef.current = reader

      const decoder = new TextDecoder()
      let buffer = ''
      let tokenBuffer = []  // Batch tokens for fewer re-renders

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        // Parse SSE events (separated by \n\n)
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''  // Keep incomplete event in buffer

        for (const event of events) {
          if (!event.startsWith('data: ')) continue

          try {
            const data = JSON.parse(event.slice(6))

            switch (data.type) {
              case 'token':
                tokenBuffer.push(data.content)
                // Batch update every 5 tokens for performance
                if (tokenBuffer.length >= 5) {
                  setTokens(prev => [...prev, ...tokenBuffer])
                  tokenBuffer = []
                }
                break

              case 'sources':
                setSources(data.content || [])
                break

              case 'blocked':
                setIsBlocked(true)
                setBlockReason(data.content)
                break

              case 'error':
                setError(data.content)
                break

              case 'done':
                // Flush remaining tokens
                if (tokenBuffer.length > 0) {
                  setTokens(prev => [...prev, ...tokenBuffer])
                  tokenBuffer = []
                }
                break
            }
          } catch (parseError) {
            // Skip malformed JSON
            console.warn('SSE parse error:', parseError)
          }
        }
      }

      // Flush any remaining tokens
      if (tokenBuffer.length > 0) {
        setTokens(prev => [...prev, ...tokenBuffer])
      }

    } catch (err) {
      setError(err.message || 'Stream error')
      console.error('Stream error:', err)
    } finally {
      setIsStreaming(false)
      readerRef.current = null
    }
  }, [])

  /**
   * Abort current stream (if active).
   */
  const abort = useCallback(() => {
    if (readerRef.current) {
      readerRef.current.cancel()
      readerRef.current = null
    }
    setIsStreaming(false)
  }, [])

  return {
    tokens,
    sources,
    isStreaming,
    isBlocked,
    blockReason,
    error,
    sendQuery,
    abort,
  }
}

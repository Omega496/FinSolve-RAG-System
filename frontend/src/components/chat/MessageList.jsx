/**
 * MessageList — renders full conversation history.
 * 
 * Alternating UserMessage and AssistantMessage components.
 * Shows GuardrailBlockedMessage for blocked responses.
 * Shows StreamingIndicator while streaming.
 */

import UserMessage from './UserMessage.jsx'
import AssistantMessage from './AssistantMessage.jsx'
import GuardrailBlockedMessage from './GuardrailBlockedMessage.jsx'
import StreamingIndicator from './StreamingIndicator.jsx'

export default function MessageList({
  messages,
  currentResponse,
  currentSources,
  isStreaming,
  isBlocked,
  blockReason,
  messagesEndRef,
}) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4">
      {/* Past messages */}
      {messages.map((msg, i) => (
        <div key={i}>
          {msg.role === 'user' && (
            <UserMessage content={msg.content} />
          )}

          {msg.role === 'assistant' && msg.blocked && (
            <GuardrailBlockedMessage blockReason={msg.blockReason} />
          )}

          {msg.role === 'assistant' && !msg.blocked && (
            <AssistantMessage
              content={msg.content}
              sources={msg.sources}
              isStreaming={false}
            />
          )}
        </div>
      ))}

      {/* Current streaming response */}
      {isStreaming && !isBlocked && !currentResponse && (
        <StreamingIndicator />
      )}

      {isStreaming && !isBlocked && currentResponse && (
        <AssistantMessage
          content={currentResponse}
          sources={currentSources}
          isStreaming={true}
        />
      )}

      {isStreaming && isBlocked && (
        <GuardrailBlockedMessage blockReason={blockReason} />
      )}

      <div ref={messagesEndRef} />
    </div>
  )
}

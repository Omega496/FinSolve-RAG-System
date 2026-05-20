/**
 * GuardrailBlockedMessage — professional rejection message.
 * 
 * Styles per AGNNTS.md: red-900 background.
 * Messages based on block_reason.
 */

const BLOCK_MESSAGES = {
  off_topic: {
    title: 'Outside Scope',
    message: "I'm FinSolve's internal document assistant. I can only answer questions about company documents and policies.",
    icon: '🚫',
  },
  unauthorized: {
    title: 'Access Denied',
    message: "You don't have permission to access this information. Please contact HR or your manager if you need access to this data.",
    icon: '🔒',
  },
  pii_detected: {
    title: 'Content Filtered',
    message: "This response has been filtered as it may contain sensitive personal information. Please contact HR directly for personnel-related queries.",
    icon: '🛡️',
  },
  no_relevant_documents: {
    title: 'No Information Found',
    message: "I don't have enough information in the available documents to answer this. Please try rephrasing your question or ask about a different topic.",
    icon: '📄',
  },
  prompt_injection: {
    title: 'Request Blocked',
    message: "I cannot process that request. Please ask a question about company documents.",
    icon: '⚠️',
  },
}

export default function GuardrailBlockedMessage({ blockReason }) {
  const config = BLOCK_MESSAGES[blockReason] || {
    title: 'Request Blocked',
    message: 'Your request could not be processed. Please try again with a different question.',
    icon: '⚠️',
  }

  return (
    <div className="max-w-3xl mr-auto">
      <div className="bg-red-900/80 border border-red-700/50 rounded-lg p-4 mr-12">
        <div className="flex items-start gap-3">
          <span className="text-xl flex-shrink-0">{config.icon}</span>
          <div>
            <h3 className="text-red-200 font-medium mb-1">
              {config.title}
            </h3>
            <p className="text-red-300 text-sm">
              {config.message}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * UserMessage — simple bubble showing user query.
 * 
 * Blue-600 background per AGNNTS.md.
 */

export default function UserMessage({ content }) {
  return (
    <div className="max-w-3xl ml-auto">
      <div className="bg-blue-600 rounded-lg p-4 ml-12 text-white">
        {content}
      </div>
    </div>
  )
}

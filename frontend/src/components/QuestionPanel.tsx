import { useState } from 'react'

interface Props {
  documentLoaded: boolean
  onAnswer: (query: string) => void
  loading: boolean
}

export default function QuestionPanel({ documentLoaded, onAnswer, loading }: Props) {
  const [query, setQuery] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!query.trim() || !documentLoaded || loading) return
    onAnswer(query.trim())
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <textarea
        value={query}
        onChange={e => setQuery(e.target.value)}
        placeholder={documentLoaded ? 'Ask anything about this contract... e.g. "What is the monthly installment?" or "What are the late payment penalties?"' : 'Upload a contract PDF first'}
        disabled={!documentLoaded || loading}
        rows={3}
        className="w-full px-4 py-3 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
      />
      <button
        type="submit"
        disabled={!documentLoaded || !query.trim() || loading}
        className="px-5 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {loading ? 'Thinking...' : 'Ask'}
      </button>
    </form>
  )
}

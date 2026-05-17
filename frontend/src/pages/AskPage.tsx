import { useState } from 'react'
import QuestionPanel from '../components/QuestionPanel'
import AnswerCard from '../components/AnswerCard'
import PipelineLog from '../components/PipelineLog'
import { askQuestion } from '../services/api'
import type { AskResponse } from '../services/api'

interface Props {
  documentLoaded: boolean
}

export default function AskPage({ documentLoaded }: Props) {
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleAsk(query: string) {
    setLoading(true)
    setError(null)
    setAnswer(null)
    try {
      const result = await askQuestion(query)
      setAnswer(result)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Failed to get answer. Please try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <QuestionPanel
        documentLoaded={documentLoaded}
        onAnswer={handleAsk}
        loading={loading}
      />
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}
      {answer && (
        <>
          <PipelineLog steps={answer.steps} title="Agent Pipeline" />
          <AnswerCard response={answer} />
        </>
      )}
    </div>
  )
}

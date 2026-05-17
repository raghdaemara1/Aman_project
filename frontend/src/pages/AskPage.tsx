import { useState, useEffect } from 'react'
import QuestionPanel from '../components/QuestionPanel'
import AnswerCard from '../components/AnswerCard'
import PipelineLog from '../components/PipelineLog'
import { askQuestion, getLogs } from '../services/api'
import type { AskResponse } from '../services/api'

interface Props {
  documentLoaded: boolean
}

export default function AskPage({ documentLoaded }: Props) {
  const [answer, setAnswer] = useState<AskResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [liveSteps, setLiveSteps] = useState<string[]>([])

  // Poll /logs every 1.5 s while the agent is running
  useEffect(() => {
    if (!loading) return
    const interval = setInterval(async () => {
      try {
        const res = await getLogs()
        if (res.steps.length > 0) setLiveSteps(res.steps)
      } catch {
        // ignore transient poll errors
      }
    }, 1500)
    return () => clearInterval(interval)
  }, [loading])

  async function handleAsk(query: string) {
    setLoading(true)
    setError(null)
    setAnswer(null)
    setLiveSteps([])
    try {
      const result = await askQuestion(query)
      setAnswer(result)
      setLiveSteps(result.steps)
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
      {liveSteps.length > 0 && (
        <PipelineLog
          steps={liveSteps}
          title={loading ? 'Agent Pipeline (Live)' : 'Agent Pipeline'}
        />
      )}
      {answer && <AnswerCard response={answer} />}
    </div>
  )
}

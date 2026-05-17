import { useState, useEffect } from 'react'
import ExtractTable from '../components/ExtractTable'
import PipelineLog from '../components/PipelineLog'
import { extractPolicy, getLogs } from '../services/api'
import type { PolicyData } from '../services/api'

interface Props {
  documentLoaded: boolean
}

export default function ExtractPage({ documentLoaded }: Props) {
  const [data, setData] = useState<PolicyData | null>(null)
  const [steps, setSteps] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let interval: ReturnType<typeof setInterval>
    if (loading) {
      interval = setInterval(async () => {
        try {
          const res = await getLogs()
          if (res.steps && res.steps.length > 0) {
            setSteps(res.steps)
          }
        } catch (e) {
          // Ignore polling errors
        }
      }, 1500)
    }
    return () => {
      if (interval) clearInterval(interval)
    }
  }, [loading])

  async function handleExtract() {
    setLoading(true)
    setError(null)
    setData(null)
    setSteps([])
    try {
      const result = await extractPolicy()
      setData(result.data)
      setSteps(result.steps)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Extraction failed. Please try again.'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-5">
      <div>
        <button
          type="button"
          onClick={handleExtract}
          disabled={!documentLoaded || loading}
          className="px-5 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Extracting structured data...' : 'Extract Policy Data'}
        </button>
        {!documentLoaded && (
          <p className="mt-2 text-sm text-gray-400">Upload a document first to enable extraction.</p>
        )}
      </div>
      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
        </div>
      )}
      {steps?.length > 0 && <PipelineLog steps={steps} title="Extraction Pipeline (Live)" />}
      {data && <ExtractTable data={data} />}
    </div>
  )
}

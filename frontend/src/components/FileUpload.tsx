import { useState, useRef } from 'react'
import { uploadDoc } from '../services/api'
import type { UploadResponse } from '../services/api'

interface Props {
  onStart?: () => void
  onSuccess: (data: UploadResponse) => void
  onError: (msg: string) => void
}

export default function FileUpload({ onStart, onSuccess, onError }: Props) {
  const [loading, setLoading] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  async function handleFile(file: File) {
    if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
      onError('Only PDF files are accepted.')
      return
    }
    setLoading(true)
    if (onStart) onStart()
    try {
      const result = await uploadDoc(file)
      onSuccess(result)
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        'Upload failed. Please try again.'
      onError(msg)
    } finally {
      setLoading(false)
    }
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
    e.target.value = ''
  }

  return (
    <div>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={loading}
        className="w-full px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-center"
      >
        {loading ? 'Parsing and indexing document...' : 'Click to upload a PDF policy'}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,application/pdf"
        onChange={handleChange}
        className="hidden"
        disabled={loading}
      />
    </div>
  )
}

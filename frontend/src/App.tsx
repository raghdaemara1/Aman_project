import { useState } from 'react'
import FileUpload from './components/FileUpload'
import PipelineLog from './components/PipelineLog'
import AskPage from './pages/AskPage'
import ExtractPage from './pages/ExtractPage'
import type { UploadResponse } from './services/api'

type Tab = 'ask' | 'extract'

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('ask')
  const [uploadInfo, setUploadInfo] = useState<UploadResponse | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [showUploadLog, setShowUploadLog] = useState(false)

  function handleUploadSuccess(data: UploadResponse) {
    setUploadInfo(data)
    setUploadError(null)
    setShowUploadLog(true)
  }

  function handleUploadError(msg: string) {
    setUploadError(msg)
    setUploadInfo(null)
    setShowUploadLog(false)
  }

  const documentLoaded = uploadInfo !== null

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-72 bg-white border-r border-gray-200 flex flex-col p-5 gap-5 overflow-y-auto">
        <div>
          <h1 className="text-lg font-semibold text-gray-900">IntelliDoc</h1>
          <p className="text-xs text-gray-500 mt-0.5">Insurance Document Agent</p>
        </div>

        <div className="space-y-3">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Document</p>
          <FileUpload onSuccess={handleUploadSuccess} onError={handleUploadError} />

          {uploadError && (
            <p className="text-xs text-red-600">{uploadError}</p>
          )}

          {uploadInfo && (
            <div className="p-3 bg-green-50 border border-green-200 rounded-lg space-y-1">
              <p className="text-xs font-medium text-green-800">Document indexed</p>
              <p className="text-xs text-green-700">{uploadInfo.chunks_indexed} chunks indexed</p>
              {uploadInfo.metadata.pages > 0 && (
                <p className="text-xs text-green-700">{uploadInfo.metadata.pages} page{uploadInfo.metadata.pages !== 1 ? 's' : ''}</p>
              )}
              <button
                onClick={() => setShowUploadLog(v => !v)}
                className="text-xs text-green-600 underline mt-1"
              >
                {showUploadLog ? 'Hide' : 'Show'} ingestion log
              </button>
            </div>
          )}

          {showUploadLog && uploadInfo && uploadInfo.steps.length > 0 && (
            <PipelineLog steps={uploadInfo.steps} title="Ingestion Pipeline" />
          )}
        </div>

        <details className="text-xs text-gray-500 mt-auto">
          <summary className="cursor-pointer font-medium text-gray-600 hover:text-gray-800 select-none">
            How this works
          </summary>
          <div className="mt-2 space-y-1 leading-relaxed">
            <p>1. PDF is parsed and split into 500-token chunks.</p>
            <p>2. Chunks are embedded and stored in ChromaDB.</p>
            <p>3. A LangChain ReAct agent chooses between <strong>hybrid search</strong> (BM25 + vector + RRF) and <strong>structured extraction</strong> (Pydantic schema) to answer your question.</p>
            <p>4. Source chunks and the tool used are always shown.</p>
          </div>
        </details>
      </aside>

      {/* Main */}
      <main className="flex-1 p-8 max-w-3xl">
        {/* Tabs */}
        <div className="flex gap-1 border-b border-gray-200 mb-6">
          {(['ask', 'extract'] as Tab[]).map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors -mb-px ${
                activeTab === tab
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab === 'ask' ? 'Ask a Question' : 'Extract Policy Data'}
            </button>
          ))}
        </div>

        {activeTab === 'ask' && <AskPage documentLoaded={documentLoaded} />}
        {activeTab === 'extract' && <ExtractPage documentLoaded={documentLoaded} />}
      </main>
    </div>
  )
}

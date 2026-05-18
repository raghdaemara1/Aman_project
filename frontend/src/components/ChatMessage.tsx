import PipelineLog from './PipelineLog'

interface Props {
  role: 'human' | 'assistant'
  content: string
  agentUsed?: 'retrieval_agent' | 'extraction_agent'
  steps?: string[]
  sourceChunks?: string[]
  pageRefs?: number[]
}

const AGENT_LABEL: Record<string, string> = {
  retrieval_agent: 'Retrieval Agent',
  extraction_agent: 'Extraction Agent',
}

const AGENT_COLOR: Record<string, string> = {
  retrieval_agent: 'bg-blue-100 text-blue-700',
  extraction_agent: 'bg-purple-100 text-purple-700',
}

export default function ChatMessage({ role, content, agentUsed, steps, sourceChunks, pageRefs }: Props) {
  if (role === 'human') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[75%] bg-blue-600 text-white rounded-2xl rounded-br-sm px-4 py-2.5 text-sm">
          {content}
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <div className="flex justify-start">
        <div className="max-w-[85%] space-y-1.5">
          {agentUsed && (
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${AGENT_COLOR[agentUsed] ?? 'bg-gray-100 text-gray-600'}`}>
              {AGENT_LABEL[agentUsed] ?? agentUsed}
            </span>
          )}
          <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-800 shadow-sm whitespace-pre-wrap">
            {content}
          </div>
          {sourceChunks && sourceChunks.length > 0 && (
            <details className="text-xs text-gray-400">
              <summary className="cursor-pointer hover:text-gray-600 select-none px-1">
                {sourceChunks.length} source chunk(s)
              </summary>
              <div className="mt-1 space-y-1">
                {sourceChunks.map((chunk, i) => (
                  <div key={i} className="bg-gray-50 border border-gray-100 rounded p-2 text-gray-600">
                    {pageRefs?.[i] && (
                      <span className="text-xs font-medium text-gray-400 mr-1">p.{pageRefs[i]}</span>
                    )}
                    {chunk}
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      </div>

      {steps && steps.length > 0 && (
        <PipelineLog steps={steps} title="Agent Pipeline" />
      )}
    </div>
  )
}

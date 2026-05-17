import ToolBadge from './ToolBadge'
import SourceChunk from './SourceChunk'
import type { AskResponse } from '../services/api'

interface Props {
  response: AskResponse
}

export default function AnswerCard({ response }: Props) {
  return (
    <div className="mt-6 space-y-4">
      <div className="p-4 bg-white border border-gray-200 rounded-lg shadow-sm">
        <p className="text-gray-900 text-base leading-relaxed whitespace-pre-wrap">
          {response.answer}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-gray-500">Tool used:</span>
        <ToolBadge toolUsed={response.tool_used} />
      </div>
      <div className="space-y-2">
        {response.source_chunks.map((chunk, i) => (
          <SourceChunk
            key={i}
            chunk={chunk}
            pageRef={response.page_refs[i] ?? 1}
          />
        ))}
      </div>
    </div>
  )
}

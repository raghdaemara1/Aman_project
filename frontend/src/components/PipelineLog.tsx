interface Props {
  steps: string[]
  title?: string
}

const STEP_ICONS: Record<string, string> = {
  'Received:': '📄',
  'Parsing PDF': '⚙️',
  'Extracted text': '📑',
  'Splitting into chunks': '✂️',
  'Created': '✅',
  'Clearing': '🗑️',
  'Generating embeddings': '🧠',
  'Stored': '💾',
  'BM25': '🔑',
  'Document ready': '✅',
  'Query received': '❓',
  'Initializing': '🤖',
  'Agent reasoning': '💭',
  'Tool selected': '🛠️',
  'Retrieved': '📚',
  'Generating final answer': '✍️',
  'Done': '✅',
  'Starting structured': '🔍',
  'Retrieving': '📚',
  'Sending to': '📡',
  'Pydantic parser': '✅',
  'Extraction complete': '✅',
  'Fallback': '⚠️',
  'Session': '🗂️',
  'Supervisor Agent': '🧭',
  'Supervisor →': '➡️',
  'Supervisor correction': '🔁',
  'Supervisor fallback': '⚠️',
  'Retrieval Agent': '🔍',
  'Extraction Agent': '🏷️',
  'Answer generated': '✍️',
}

function getIcon(step: string): string {
  for (const [key, icon] of Object.entries(STEP_ICONS)) {
    if (step.includes(key)) return icon
  }
  return '›'
}

export default function PipelineLog({ steps, title = 'Pipeline Activity' }: Props) {
  if (!steps || steps.length === 0) return null

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-4 py-2 bg-gray-50 border-b border-gray-200 flex items-center gap-2">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{title}</span>
        <span className="ml-auto text-xs text-gray-400">{steps.length} steps</span>
      </div>
      <div className="divide-y divide-gray-100">
        {steps.map((step, i) => (
          <div key={i} className="flex items-start gap-3 px-4 py-2">
            <span className="text-base leading-5 mt-0.5 flex-shrink-0">{getIcon(step)}</span>
            <span className="text-xs text-gray-700 font-mono leading-5">{step}</span>
            <span className="ml-auto text-xs text-gray-300 flex-shrink-0">{i + 1}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

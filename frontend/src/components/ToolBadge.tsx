interface Props {
  toolUsed: 'hybrid_search' | 'structured_extract'
}

export default function ToolBadge({ toolUsed }: Props) {
  if (toolUsed === 'hybrid_search') {
    return (
      <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
        Hybrid Search
      </span>
    )
  }
  return (
    <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
      Structured Extraction
    </span>
  )
}

interface Props {
  chunk: string
  pageRef: number
}

export default function SourceChunk({ chunk, pageRef }: Props) {
  return (
    <details className="mt-2 border border-gray-200 rounded-lg">
      <summary className="px-4 py-2 cursor-pointer text-sm text-gray-600 hover:bg-gray-50 select-none">
        Source — Page {pageRef}
      </summary>
      <pre className="px-4 py-3 text-xs text-gray-700 bg-gray-50 overflow-x-auto whitespace-pre-wrap font-mono border-t border-gray-200">
        {chunk}
      </pre>
    </details>
  )
}

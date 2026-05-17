import type { PolicyData } from '../services/api'

interface Props {
  data: PolicyData
}

const FIELD_LABELS: [keyof PolicyData, string][] = [
  ['policy_number', 'Policy Number'],
  ['policy_holder', 'Policy Holder'],
  ['coverage_type', 'Coverage Type'],
  ['start_date', 'Start Date'],
  ['end_date', 'End Date / Expiry'],
  ['premium_amount', 'Premium Amount'],
  ['coverage_limit', 'Coverage Limit'],
  ['key_exclusions', 'Key Exclusions'],
]

export default function ExtractTable({ data }: Props) {
  return (
    <div className="overflow-hidden border border-gray-200 rounded-lg">
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600 w-44">Field</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Value</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {FIELD_LABELS.map(([field, label]) => (
            <tr key={field} className="hover:bg-gray-50">
              <td className="px-4 py-3 text-gray-500 font-medium align-top">{label}</td>
              <td className="px-4 py-3 text-gray-900">
                {field === 'key_exclusions' ? (
                  Array.isArray(data.key_exclusions) && data.key_exclusions.length > 0 ? (
                    <ul className="list-disc list-inside space-y-1">
                      {data.key_exclusions.map((ex, i) => (
                        <li key={i}>{ex}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-gray-400">Not specified</span>
                  )
                ) : (
                  <span
                    className={
                      !data[field] || data[field] === 'Not specified'
                        ? 'text-gray-400'
                        : ''
                    }
                  >
                    {(data[field] as string) || 'Not specified'}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

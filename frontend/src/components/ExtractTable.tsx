import type { ContractData } from '../services/api'

interface Props {
  data: ContractData
}

const FIELD_LABELS: [keyof ContractData, string][] = [
  ['contract_number', 'Contract Number'],
  ['customer_name', 'Customer Name'],
  ['product_financed', 'Product Financed'],
  ['total_amount', 'Total Financed Amount'],
  ['monthly_installment', 'Monthly Installment'],
  ['duration_months', 'Duration'],
  ['profit_rate', 'Profit Rate'],
  ['key_conditions', 'Key Conditions & Penalties'],
]

export default function ExtractTable({ data }: Props) {
  return (
    <div className="overflow-hidden border border-gray-200 rounded-lg">
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            <th className="px-4 py-3 text-left font-medium text-gray-600 w-52">Field</th>
            <th className="px-4 py-3 text-left font-medium text-gray-600">Value</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {FIELD_LABELS.map(([field, label]) => (
            <tr key={field} className="hover:bg-gray-50">
              <td className="px-4 py-3 text-gray-500 font-medium align-top">{label}</td>
              <td className="px-4 py-3 text-gray-900">
                {field === 'key_conditions' ? (
                  Array.isArray(data.key_conditions) && data.key_conditions.length > 0 ? (
                    <ul className="list-disc list-inside space-y-1">
                      {data.key_conditions.map((c, i) => (
                        <li key={i}>{c}</li>
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

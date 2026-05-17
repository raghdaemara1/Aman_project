import axios from 'axios'

export interface UploadMetadata {
  filename: string
  pages: number
  indexed_at: string
}

export interface UploadResponse {
  chunks_indexed: number
  metadata: UploadMetadata
  steps: string[]
}

export interface AskResponse {
  answer: string
  tool_used: 'hybrid_search' | 'structured_extract'
  source_chunks: string[]
  page_refs: number[]
  steps: string[]
}

export interface ContractData {
  contract_number: string
  customer_name: string
  product_financed: string
  total_amount: string
  monthly_installment: string
  duration_months: string
  profit_rate: string
  key_conditions: string[]
}

export interface ExtractResponse {
  data: ContractData
  steps: string[]
}

const api = axios.create({ baseURL: '/api/v1' })

export async function uploadDoc(file: File): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await api.post<UploadResponse>('/upload', form)
  return data
}

export async function askQuestion(query: string): Promise<AskResponse> {
  const { data } = await api.post<AskResponse>('/ask', { query })
  return data
}

export async function extractPolicy(): Promise<ExtractResponse> {
  const { data } = await api.post<ExtractResponse>('/extract')
  return data
}

export async function clearStore(): Promise<void> {
  await api.delete('/store')
}

export async function getLogs(): Promise<{ steps: string[] }> {
  const { data } = await api.get('/logs')
  return data
}
